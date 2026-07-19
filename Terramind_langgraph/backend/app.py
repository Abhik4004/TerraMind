from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import os
import sys
from pathlib import Path
import uuid
import time
import json
import json as _json
import asyncio
import bcrypt
from datetime import datetime

# MongoDB for user auth + session persistence (JSON/in-memory fallback).
# Connection string comes from .env (MONGO_URI); initialised after settings
# import below.
_USERS_FILE = Path(__file__).parent.parent / "data" / "users.json"
MONGO_AVAILABLE = False
_users_col = None
_sessions_col = None


# ── JSON file fallback helpers ────────────────────────────────────────────────
def _load_users() -> dict:
    """Load users from the JSON file store."""
    try:
        _USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
        if _USERS_FILE.exists():
            return _json.loads(_USERS_FILE.read_text())
    except Exception:
        pass
    return {}


def _save_users(users: dict) -> None:
    """Persist users to the JSON file store."""
    _USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _USERS_FILE.write_text(_json.dumps(users, indent=2))


def _file_get_user(username: str) -> Optional[dict]:
    return _load_users().get(username)


def _file_create_user(username: str, pw_hash: str) -> None:
    """Raise ValueError if username already taken."""
    users = _load_users()
    if username in users:
        raise ValueError("Username already exists")
    users[username] = {
        "username": username,
        "pw_hash": pw_hash,
        "created_at": datetime.now().isoformat(),
    }
    _save_users(users)


# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import socketio
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from src.graph.workflow import land_analysis_graph
from src.config.settings import settings
from src.rag.rag_pipeline import RAGPipeline, RAGCONFIG
from src.utils.cache_manager import cache_manager
from src.tools.tool_selector import tool_selector
from src.utils.pii_filter import redact_pii, redact_history

# ── MongoDB init (URI from .env) ──────────────────────────────────────────────
if settings.MONGO_URI:
    try:
        from pymongo import MongoClient
        _mongo = MongoClient(settings.MONGO_URI, serverSelectionTimeoutMS=2000)
        _mongo.admin.command("ping")
        _users_col = _mongo["terramind"]["users"]
        _users_col.create_index("username", unique=True)
        _sessions_col = _mongo["terramind"]["sessions"]
        _sessions_col.create_index("session_id", unique=True)
        MONGO_AVAILABLE = True
        print("[DB] MongoDB connected: auth + session persistence enabled")
    except Exception as e:
        print(f"[DB] MongoDB unavailable ({e}); using JSON/in-memory fallbacks")

# ── Rate limiter ──────────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)

# ── Socket.IO server ──────────────────────────────────────────────────────────
sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")

# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="TerraMind Land Analysis API",
    description="AI-powered geospatial land analysis with Self-RAG",
    version="1.0.0",
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS middleware — allow_credentials=True requires explicit origins, not "*"
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://[::1]:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Socket.IO — the ASGI wrapper exposes WS at /socket.io/
socket_app = socketio.ASGIApp(sio, app)

# ── Module-level singletons ───────────────────────────────────────────────────
rag_pipeline = RAGPipeline(RAGCONFIG)
sessions: Dict[str, Dict[str, Any]] = {}
startup_time = time.time()


# ── Background cache sweep ────────────────────────────────────────────────────
# Expired .pkl cache entries were only deleted when the manual endpoint was
# called; on disk they accumulated forever. Sweep on startup and every
# CACHE_SWEEP_INTERVAL_MIN minutes.
async def _cache_sweeper():
    while True:
        try:
            removed = cache_manager.clear_expired()
            if removed:
                print(f"[MEM] cache sweep removed {removed} expired entr(ies)")
        except Exception as e:
            print(f"[MEM] cache sweep failed: {e}")
        await asyncio.sleep(settings.CACHE_SWEEP_INTERVAL_MIN * 60)


@app.on_event("startup")
async def _start_background_tasks():
    asyncio.create_task(_cache_sweeper())


# ── Socket.IO events ──────────────────────────────────────────────────────────
@sio.event
async def connect(sid, environ):
    pass


@sio.event
async def disconnect(sid):
    pass


@sio.event
async def join_session(sid, data):
    """Client sends { session_id } to subscribe to that session's node events."""
    session_id = data.get("session_id")
    if session_id:
        await sio.enter_room(sid, session_id)


async def emit_node_status(session_id: str, node: str, message: str):
    """Broadcast a node-execution status event to all clients in the session room."""
    await sio.emit(
        "node_status",
        {"node": node, "message": message, "timestamp": datetime.now().isoformat()},
        room=session_id,
    )


# ── Pydantic models ───────────────────────────────────────────────────────────
class QueryRequest(BaseModel):
    query: str = Field(..., description="User's query about land analysis")
    session_id: Optional[str] = Field(None, description="Session ID for conversation history")
    use_cache: bool = Field(True, description="Whether to use cached responses")


class QueryResponse(BaseModel):
    session_id: str
    query: str
    answer: str
    sources: List[Dict[str, Any]]
    tools_used: List[str]
    from_cache: bool
    processing_time: float
    timestamp: str


class SessionInfo(BaseModel):
    session_id: str
    created_at: str
    message_count: int
    chat_history: List[Dict[str, str]]


class CacheStats(BaseModel):
    response_cache: int
    embedding_cache: int
    tool_cache: int
    total_entries: int
    total_size_mb: float


class AuthRequest(BaseModel):
    username: str
    password: str


class ToolInfo(BaseModel):
    name: str
    description: str
    use_cases: List[str]


class SystemHealth(BaseModel):
    status: str
    vector_store_ready: bool
    cache_operational: bool
    llm_available: bool
    total_sessions: int
    uptime_seconds: float


# ── Helper: build graph inputs ────────────────────────────────────────────────
def _build_inputs(query: str, chat_history: list, use_cache: bool = True) -> dict:
    # Security: redact personal information before anything reaches the LLM.
    # Geographic coordinates are preserved (they are not PII).
    return {
        "question": redact_pii(query),
        "use_cache": use_cache,
        "chat_history": redact_history(chat_history),
        "documents": [],
        "generation": "",
        "coordinates": {},
        "location_context": {},
        "tool_results": {},
        "selected_tools": [],
        "relevance_score": "",
        "hallucination_score": "",
        "answer_score": "",
        "retry_count": 0,
        "cache_key": "",
        "cached_response": {},
        "sources": [],
        "final_answer": "",
    }


# ── Memory management ─────────────────────────────────────────────────────────
# The in-memory session store is bounded: stale sessions expire after
# SESSION_TTL_HOURS, and when MAX_SESSIONS is exceeded the least-recently-used
# sessions are evicted. Per-session chat history is capped so a long-running
# conversation cannot grow without bound.

def _evict_sessions():
    now = time.time()
    ttl = settings.SESSION_TTL_HOURS * 3600

    # Drop expired sessions.
    expired = [sid for sid, s in sessions.items() if now - s.get("last_used", now) > ttl]
    for sid in expired:
        del sessions[sid]

    # LRU-evict beyond the cap.
    if len(sessions) > settings.MAX_SESSIONS:
        by_age = sorted(sessions.items(), key=lambda kv: kv[1].get("last_used", 0))
        for sid, _ in by_age[: len(sessions) - settings.MAX_SESSIONS]:
            del sessions[sid]

    if expired:
        print(f"[MEM] evicted {len(expired)} expired session(s); {len(sessions)} live")


def _mongo_load_session(sid: str) -> Optional[dict]:
    """Hydrate a session from MongoDB (survives process restarts)."""
    if not MONGO_AVAILABLE:
        return None
    try:
        doc = _sessions_col.find_one({"session_id": sid}, {"_id": 0})
        if doc:
            return {
                "created_at": doc.get("created_at", datetime.now().isoformat()),
                "chat_history": doc.get("chat_history", []),
                "message_count": doc.get("message_count", 0),
            }
    except Exception as e:
        print(f"[DB] session load failed: {e}")
    return None


def _mongo_save_session(sid: str, session: dict):
    """Write-through: persist the (capped) session state to MongoDB."""
    if not MONGO_AVAILABLE:
        return
    try:
        _sessions_col.update_one(
            {"session_id": sid},
            {"$set": {
                "session_id": sid,
                "created_at": session["created_at"],
                "chat_history": session["chat_history"],
                "message_count": session["message_count"],
                "updated_at": datetime.now().isoformat(),
            }},
            upsert=True,
        )
    except Exception as e:
        print(f"[DB] session save failed: {e}")


def _get_or_create_session(session_id: Optional[str]) -> tuple[str, dict]:
    sid = session_id or str(uuid.uuid4())
    if sid not in sessions:
        # Try MongoDB first so history survives restarts; else fresh session.
        sessions[sid] = _mongo_load_session(sid) or {
            "created_at": datetime.now().isoformat(),
            "chat_history": [],
            "message_count": 0,
        }
    sessions[sid]["last_used"] = time.time()
    # Evict after insert: the new session is the most recently used, so the
    # LRU pass can never remove it, and the store ends at most MAX_SESSIONS.
    _evict_sessions()
    return sid, sessions[sid]


def _update_session(session: dict, query: str, answer: str, sid: str = None):
    session["chat_history"].append({"role": "user", "content": query})
    session["chat_history"].append({"role": "assistant", "content": answer})
    session["message_count"] += 1
    session["last_used"] = time.time()
    # Cap stored history — keep only the most recent messages.
    cap = settings.MAX_HISTORY_MESSAGES
    if len(session["chat_history"]) > cap:
        session["chat_history"] = session["chat_history"][-cap:]
    if sid:
        _mongo_save_session(sid, session)


def _llm_history(session: dict) -> list:
    """Only the last few turns go to the model — bounds prompt size and RAM."""
    return session["chat_history"][-settings.LLM_HISTORY_MESSAGES:]


# ── Auth endpoints ────────────────────────────────────────────────────────────

@app.post("/signup")
async def signup(body: AuthRequest):
    username = body.username.strip()
    if not username or len(body.password) < 6:
        raise HTTPException(
            status_code=400,
            detail="Username required and password must be at least 6 characters",
        )

    pw_hash = bcrypt.hashpw(body.password.encode(), bcrypt.gensalt()).decode()

    if MONGO_AVAILABLE:
        try:
            _users_col.insert_one({
                "username": username,
                "pw_hash": pw_hash,
                "created_at": datetime.now().isoformat(),
            })
        except Exception:
            raise HTTPException(status_code=409, detail="Username already exists")
    else:
        # Fallback: persist to local JSON file
        try:
            _file_create_user(username, pw_hash)
        except ValueError:
            raise HTTPException(status_code=409, detail="Username already exists")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Could not create user: {e}")

    return {"message": "Signup successful", "username": username}


@app.post("/login")
async def login(body: AuthRequest):
    username = body.username.strip()

    if MONGO_AVAILABLE:
        user = _users_col.find_one({"username": username})
    else:
        user = _file_get_user(username)

    if not user or not bcrypt.checkpw(body.password.encode(), user["pw_hash"].encode()):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token = f"tm-{uuid.uuid4().hex}"
    return {"access_token": token, "username": username}


# ── Core endpoints ────────────────────────────────────────────────────────────

_STATIC_DIR_ROOT = Path(os.getenv("STATIC_DIR", str(Path(__file__).parent.parent / "static")))


@app.get("/api")
async def api_info():
    return {
        "name": "TerraMind Land Analysis API",
        "version": "1.0.0",
        "status": "operational",
        "docs": "/docs",
        "user_store": "mongodb" if MONGO_AVAILABLE else "json_file",
        "endpoints": {
            "query": "/api/query",
            "query_stream": "/api/query/stream",
            "session": "/api/session/{session_id}",
            "sessions_search": "/api/sessions/search",
            "cache": "/api/cache/stats",
            "tools": "/api/tools",
            "health": "/api/health",
        },
    }


# "/" serves the built frontend when it's present (single-container deploy);
# falls back to the API info JSON when running the backend standalone (dev).
if not _STATIC_DIR_ROOT.exists():
    @app.get("/")
    async def root():
        return await api_info()


@app.post("/api/query", response_model=QueryResponse)
@limiter.limit(f"{settings.RATE_LIMIT_PER_MINUTE}/minute")
async def analyze_query(request: Request, body: QueryRequest):
    """Analyze a land-related query using the LangGraph workflow."""
    start_time = time.time()
    session_id, session = _get_or_create_session(body.session_id)

    try:
        result = land_analysis_graph.invoke(
            _build_inputs(body.query, _llm_history(session), body.use_cache)
        )
        final_answer = result.get("final_answer", result.get("generation", ""))
        _update_session(session, body.query, final_answer, session_id)

        return QueryResponse(
            session_id=session_id,
            query=body.query,
            answer=final_answer,
            sources=result.get("sources", []),
            tools_used=result.get("selected_tools", []),
            from_cache=bool(result.get("cached_response")),
            processing_time=time.time() - start_time,
            timestamp=datetime.now().isoformat(),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")


@app.post("/api/query/stream")
@limiter.limit(f"{settings.RATE_LIMIT_STREAM_PER_MINUTE}/minute")
async def stream_query(request: Request, body: QueryRequest):
    """
    Stream query processing status + final answer via Server-Sent Events.

    The graph runs in a thread pool (synchronous LangGraph).
    SSE events:
      { "type": "status", "node": "...", "message": "..." }
      { "type": "token",  "content": "..." }          <- simulated per-word streaming
      { "type": "done",   "session_id": "...", "processing_time": 1.5 }
      { "type": "error",  "detail": "..." }
    """
    session_id, session = _get_or_create_session(body.session_id)

    async def event_generator():
        start = time.time()

        node_messages = {
            "parse_query": "Understanding your request...",
            "check_cache": "Checking response cache...",
            "select_tools": "Selecting the best analysis tools...",
            "retrieve": "Retrieving relevant geospatial documents...",
            "grade_documents": "Grading document relevance...",
            "execute_tools": "Executing geospatial tools...",
            "generate": "Generating your answer...",
            "check_hallucination": "Verifying answer accuracy...",
            "check_answer": "Validating answer quality...",
            "format_final": "Formatting final response...",
        }

        result_holder: Dict[str, Any] = {}

        async def run_graph():
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                land_analysis_graph.invoke,
                _build_inputs(body.query, _llm_history(session), body.use_cache),
            )
            result_holder["result"] = result

        graph_task = asyncio.create_task(run_graph())

        for node, msg in node_messages.items():
            if graph_task.done():
                break
            yield f"data: {json.dumps({'type': 'status', 'node': node, 'message': msg})}\n\n"
            try:
                await asyncio.wait_for(asyncio.shield(graph_task), timeout=2.0)
                break
            except asyncio.TimeoutError:
                pass

        await graph_task

        result = result_holder.get("result", {})
        final_answer = result.get("final_answer", result.get("generation", ""))

        words = final_answer.split(" ")
        for word in words:
            yield f"data: {json.dumps({'type': 'token', 'content': word + ' '})}\n\n"
            await asyncio.sleep(0.01)

        _update_session(session, body.query, final_answer, session_id)

        yield f"data: {json.dumps({'type': 'done', 'session_id': session_id, 'tools_used': result.get('selected_tools', []), 'from_cache': bool(result.get('cached_response')), 'processing_time': round(time.time() - start, 2)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/sessions/search")
async def search_sessions(q: str, limit: int = 20):
    """Search chat history content across all in-memory sessions."""
    query_lower = q.strip().lower()
    if not query_lower:
        return {"query": q, "total_results": 0, "results": []}

    results = []
    for session_id, session in sessions.items():
        matched = [
            msg
            for msg in session.get("chat_history", [])
            if query_lower in msg.get("content", "").lower()
        ]
        if matched:
            results.append(
                {
                    "session_id": session_id,
                    "created_at": session["created_at"],
                    "message_count": session["message_count"],
                    "matched_messages": matched[:3],
                    "match_count": len(matched),
                }
            )

    results.sort(key=lambda x: x["match_count"], reverse=True)
    return {
        "query": q,
        "total_results": len(results),
        "results": results[:limit],
    }


@app.get("/api/session/{session_id}", response_model=SessionInfo)
async def get_session(session_id: str):
    """Get session information and chat history."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    session = sessions[session_id]
    return SessionInfo(
        session_id=session_id,
        created_at=session["created_at"],
        message_count=session["message_count"],
        chat_history=session["chat_history"],
    )


@app.delete("/api/session/{session_id}")
async def delete_session(session_id: str):
    """Delete a session and its history."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    del sessions[session_id]
    return {"message": "Session deleted successfully", "session_id": session_id}


@app.get("/api/sessions")
async def list_sessions():
    """List all active sessions (includes chat_history for client-side search)."""
    return {
        "total_sessions": len(sessions),
        "sessions": [
            {
                "session_id": sid,
                "created_at": session["created_at"],
                "message_count": session["message_count"],
                "chat_history": session.get("chat_history", []),
            }
            for sid, session in sessions.items()
        ],
    }


@app.get("/api/cache/stats", response_model=CacheStats)
async def get_cache_stats():
    stats = cache_manager.get_cache_stats()
    return CacheStats(**stats)


@app.post("/api/cache/clear")
async def clear_cache(cache_type: Optional[str] = None):
    try:
        count = cache_manager.clear_all(cache_type)
        return {"message": f"Cleared {count} cache entries", "cache_type": cache_type or "all"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error clearing cache: {str(e)}")


@app.post("/api/cache/clear-expired")
async def clear_expired_cache():
    try:
        count = cache_manager.clear_expired()
        return {"message": f"Cleared {count} expired cache entries"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error clearing expired cache: {str(e)}")


@app.get("/api/tools", response_model=List[ToolInfo])
async def list_tools():
    return [
        ToolInfo(name=name, description=info["description"], use_cases=info["use_for"])
        for name, info in tool_selector.AVAILABLE_TOOLS.items()
    ]


@app.post("/api/tools/select")
async def select_tools_for_query(query: str):
    try:
        result = tool_selector.select_tools(query)
        return {
            "query": query,
            "selected_tools": result["selected_tools"],
            "reasoning": result["reasoning"],
            "requires_coordinates": result["requires_coordinates"],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error in tool selection: {str(e)}")


# ── Map overlay endpoint ──────────────────────────────────────────────────────
# Serves point layers the frontend colors on the map: soil condition, hazard
# risk, or live weather. Weather values come from Open-Meteo via the cached
# weather tool, so repeated loads within the TTL cost zero API calls.

_OVERLAY_SOIL_FILES = ["north_bengal_data_fixed.geojson", "sundarbans_land_data.geojson"]
_OVERLAY_RISK_FILES = ["north_bengal_risk_data.geojson", "sundarban_risk.geojson"]


def _load_features(filenames: list) -> list:
    feats = []
    for name in filenames:
        fp = Path(settings.DATA_DIR) / name
        if not fp.exists():
            continue
        try:
            data = _json.loads(fp.read_text(encoding="utf-8"))
            feats.extend(data.get("features", []))
        except Exception as e:
            print(f"overlay: failed to read {name}: {e}")
    return feats


def _soil_color(productivity: str) -> str:
    p = productivity.lower()
    if "high" in p:
        return "#2b9348"
    if "moderate" in p or "medium" in p:
        return "#e9c46a"
    if "low" in p or "poor" in p:
        return "#e76f51"
    return "#8d99ae"


def _risk_color(flood: str) -> str:
    r = flood.lower()
    if "very high" in r:
        return "#9b2226"
    if "high" in r:
        return "#e63946"
    if "moderate" in r:
        return "#e9c46a"
    if "very low" in r:
        return "#2b9348"
    if "low" in r:
        return "#2a9d8f"
    return "#8d99ae"


def _temp_color(t) -> str:
    if t is None:
        return "#8d99ae"
    if t < 20:
        return "#457b9d"
    if t < 28:
        return "#2a9d8f"
    if t < 33:
        return "#e9c46a"
    if t < 38:
        return "#f4a261"
    return "#e63946"


@app.get("/api/map/overlay")
async def map_overlay(layer: str = "soil"):
    """
    GeoJSON FeatureCollection for map coloring.
    layer = soil | risk | weather. Each feature carries a precomputed `color`.
    """
    layer = layer.lower().strip()
    out = []

    if layer == "soil":
        for f in _load_features(_OVERLAY_SOIL_FILES):
            p = f.get("properties", {})
            out.append({
                "type": "Feature",
                "geometry": f.get("geometry"),
                "properties": {
                    "place": p.get("place_name") or p.get("location", "Unknown"),
                    "soil_productivity": str(p.get("soil productivity", p.get("soil_productivity", "Unknown"))).title(),
                    "soil_texture": p.get("soil texture", p.get("soil_texture", "Unknown")),
                    "land_type": p.get("land type", p.get("land_type", "Unknown")),
                    "land_degradation": p.get("land degradation", p.get("land_degradation", "Unknown")),
                    "color": _soil_color(str(p.get("soil productivity", p.get("soil_productivity", "")))),
                },
            })
    elif layer == "risk":
        # The Sundarban risk file stores name="Unknown" (its source used
        # 'location', not 'place_name'), so join names from the land layer
        # by rounded coordinate.
        name_by_coord = {}
        for f in _load_features(_OVERLAY_SOIL_FILES):
            g = (f.get("geometry") or {}).get("coordinates") or []
            p = f.get("properties", {})
            nm = p.get("place_name") or p.get("location")
            if len(g) >= 2 and nm:
                name_by_coord[(round(g[0], 4), round(g[1], 4))] = nm
        for f in _load_features(_OVERLAY_RISK_FILES):
            p = f.get("properties", {})
            g = (f.get("geometry") or {}).get("coordinates") or []
            name = p.get("name", "")
            if (not name or name == "Unknown") and len(g) >= 2:
                name = name_by_coord.get((round(g[0], 4), round(g[1], 4)), "")
            # A DMS coordinate string is not a place name — blank it out and
            # let the frontend label show just the risk value.
            if "°" in name or "''" in name or name == "Unknown":
                name = ""
            out.append({
                "type": "Feature",
                "geometry": f.get("geometry"),
                "properties": {
                    "place": name,
                    "flood_risk": str(p.get("flood_risk", "Unknown")).title(),
                    "earthquake": p.get("earthquake_category", "Unknown"),
                    "heat_stress": p.get("heat_stress", "Unknown"),
                    "wind_risk": p.get("wind_risk", "Unknown"),
                    "color": _risk_color(str(p.get("flood_risk", ""))),
                },
            })
    elif layer == "weather":
        from src.tools import weather_tool
        for f in _load_features(_OVERLAY_SOIL_FILES):
            geom = f.get("geometry") or {}
            coords = geom.get("coordinates") or []
            if len(coords) < 2:
                continue
            lon, lat = coords[0], coords[1]
            p = f.get("properties", {})
            props = {"place": p.get("place_name") or p.get("location", "Unknown")}
            try:
                w = weather_tool.get_weather_data(lat, lon)  # cached per point
                props.update({
                    "temp_c": w.get("temp_c"),
                    "humidity_pct": w.get("humidity_pct"),
                    "wind_speed_ms": w.get("wind_speed_ms"),
                    "description": w.get("description"),
                    "color": _temp_color(w.get("temp_c")),
                })
            except Exception as e:
                props["error"] = str(e)[:80]
                props["color"] = "#8d99ae"
            out.append({"type": "Feature", "geometry": geom, "properties": props})
    else:
        raise HTTPException(status_code=400, detail="layer must be soil, risk, or weather")

    return {"type": "FeatureCollection", "layer": layer, "features": out}


@app.get("/api/health", response_model=SystemHealth)
async def health_check():
    vector_store_ready = rag_pipeline.vector_store_exists()
    return SystemHealth(
        status="healthy" if vector_store_ready else "degraded",
        vector_store_ready=vector_store_ready,
        cache_operational=True,
        llm_available=True,
        total_sessions=len(sessions),
        uptime_seconds=time.time() - startup_time,
    )


@app.post("/api/initialize")
async def initialize_system(background_tasks: BackgroundTasks):
    if rag_pipeline.vector_store_exists():
        return {"message": "Vector store already exists", "status": "ready"}

    data_dir = Path(settings.DATA_DIR)
    geojson_files = list(data_dir.glob("*.geojson"))
    if not geojson_files:
        raise HTTPException(
            status_code=400,
            detail=f"No GeoJSON files found in {data_dir}. Please add data files first.",
        )

    def init_vector_store():
        try:
            rag_pipeline.ingestion_vs()
        except Exception as e:
            print(f"Error during vector store initialization: {e}")

    background_tasks.add_task(init_vector_store)
    return {
        "message": f"Vector store initialization started with {len(geojson_files)} files",
        "status": "initializing",
        "files_count": len(geojson_files),
    }


@app.get("/api/settings")
async def get_settings():
    return {
        "llm_model": settings.LLM_MODEL,
        "embedding_model": settings.EMBEDDING_MODEL,
        "retrieval_k": settings.RETRIEVAL_K,
        "cache_enabled": settings.ENABLE_CACHE,
        "cache_ttl_hours": settings.CACHE_TTL_HOURS,
        "max_retries": settings.MAX_GENERATION_RETRIES,
        "hallucination_check_enabled": settings.HALLUCINATION_CHECK_ENABLED,
        "answer_check_enabled": settings.ANSWER_CHECK_ENABLED,
    }


# ── Static frontend (single-origin deploys, e.g. HF Spaces) ──────────────────
# If a built React bundle exists (frontend/dist copied into the image at
# STATIC_DIR), serve it from this process: API stays under /api and /login,
# everything else falls through to the SPA's index.html.
_STATIC_DIR = Path(os.getenv("STATIC_DIR", str(Path(__file__).parent.parent / "static")))
if _STATIC_DIR.exists():
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse

    app.mount("/assets", StaticFiles(directory=_STATIC_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        candidate = _STATIC_DIR / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_STATIC_DIR / "index.html")

    print(f"[WEB] serving frontend from {_STATIC_DIR}")


# Run with:
#   Windows: python.exe -m uvicorn backend.app:socket_app --reload --port 8000
#   Mac/Linux: uvicorn backend.app:socket_app --reload --port 8000
# (use socket_app, not app, to enable WebSocket support)
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(socket_app, host="0.0.0.0", port=8000)