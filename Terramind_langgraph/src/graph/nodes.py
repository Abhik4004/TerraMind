from typing import Any, Dict, Optional
from concurrent.futures import ThreadPoolExecutor
from src.graph.state import GraphState
from src.rag.rag_pipeline import RAGPipeline, RAGCONFIG
from src.chains.retrieval_grader import retrieval_grader
from src.chains.hallucination_grader import hallucination_grader
from src.chains.answer_grader import answer_grader
from src.chains.generator import generator
from src.utils.coordinate_parser import extract_coordinates
from src.utils.cache_manager import cache_manager
from src.utils.source_tracking import SourceTracker
from src.tools.tool_selector import tool_selector
from src.tools import weather_tool, road_tool
from src.config.settings import settings
import re

# Initialize RAG pipeline
rag_pipeline = RAGPipeline(RAGCONFIG)

# ── Small-talk fast path ──────────────────────────────────────────────────────
# Greetings and trivial small-talk should NOT trigger the full retrieval +
# grading + generation pipeline. We classify them cheaply (no LLM) and answer
# with a canned response, skipping ~9 model calls per message.

_GREETING_TOKENS = {
    "hi", "hii", "hiii", "hello", "helloo", "hey", "heyy", "hiya", "yo",
    "hola", "namaste", "greetings", "sup", "howdy",
}

# Filler/small-talk words that, combined with greetings, still don't constitute
# a real geospatial question (e.g. "hey, how are you doing?").
_SMALLTALK_TOKENS = _GREETING_TOKENS | {
    "how", "are", "you", "u", "doing", "is", "it", "going", "hows",
    "what", "whats", "up", "good", "morning", "evening", "afternoon",
    "night", "day", "nice", "to", "meet", "there", "thanks", "thank",
    "thankyou", "ty", "thx", "cheers", "bye", "goodbye", "cya", "see",
    "later", "who", "can", "do", "help", "me", "your", "name", "and",
    "the", "a", "please", "ok", "okay", "cool", "great", "so", "much",
    "lot", "very", "of", "hi", "yes", "no",
}

_SMALLTALK_REPLIES = {
    "greeting": (
        "👋 Hi! I'm **TerraMind**, your geospatial land-analysis assistant.\n\n"
        "Pick a location on the map and ask me about terrain, soil, weather, "
        "roads, flood risk, air quality, or construction suitability."
    ),
    "capabilities": (
        "🌍 I'm **TerraMind** — I analyze land and locations. Here's what I can do:\n\n"
        "- **Terrain & soil** characteristics for a selected point\n"
        "- **Weather** (current and recent) and **air quality**\n"
        "- **Road network** connectivity and infrastructure\n"
        "- **Flood risk** and **construction suitability**\n\n"
        "Select a spot on the map and ask away!"
    ),
    "thanks": "You're welcome! 🌱 Ask me anything else about a location whenever you like.",
    "bye": "👋 Take care! Come back anytime you need a land or location analysis.",
}


# The frontend appends a location block to every query when location sharing is
# on, e.g. "hi\n\nLocation: Kolkata (Lat: 22.573000, Lng: 88.363000)".
# Intent must be judged on what the USER actually typed, not on that block,
# otherwise a bare "hi" with a pin dropped runs the whole retrieval pipeline.
_LOCATION_BLOCK = re.compile(
    r"\n*\s*Location\s*:\s*.*?\(?\s*Lat(?:itude)?\s*[:=]?\s*-?\d+\.?\d*.*?"
    r"(?:lng|long|lon(?:gitude)?)\s*[:=]?\s*-?\d+\.?\d*\s*\)?\s*$",
    re.IGNORECASE | re.DOTALL,
)


def strip_location_block(text: str) -> str:
    """
    Remove the trailing 'Location: <place> (Lat: .., Lng: ..)' block that the
    frontend appends, returning only what the user typed. Falls back to the
    original text when no block is present.
    """
    if not text:
        return text
    stripped = _LOCATION_BLOCK.sub("", text).strip()
    return stripped if stripped else text.strip()


def _classify_smalltalk(question: str) -> Optional[str]:
    """
    Return a small-talk category ('greeting'|'capabilities'|'thanks'|'bye')
    if the user's message is trivial small-talk, else None.

    The appended location block is stripped first, so "hi" with a pin dropped
    is still a greeting. Uses token matching (no LLM) so it's instant, and it
    never misfires on real queries like "hi, what's the soil like here?"
    ('soil'/'here' aren't in the vocabulary, so it falls through).
    """
    core = strip_location_block(question)
    cleaned = re.sub(r"[^\w\s]", " ", core.lower())
    tokens = cleaned.split()

    if not tokens or len(tokens) > 6:
        return None
    if not all(tok in _SMALLTALK_TOKENS for tok in tokens):
        return None

    if any(tok in {"thanks", "thank", "thankyou", "ty", "thx", "cheers"} for tok in tokens):
        return "thanks"
    if any(tok in {"bye", "goodbye", "cya", "later"} for tok in tokens):
        return "bye"
    if any(tok in {"what", "who", "help", "can", "name", "do"} for tok in tokens):
        return "capabilities"
    return "greeting"

def _canonical_cache_key(question: str) -> str:
    """
    Build a cache key that survives cosmetic differences between requests.

    The raw query embeds pin coordinates at 6-decimal precision (~0.11 m), so
    re-dropping a pin on the same spot never produced the same string and the
    response cache almost never hit across sessions. Canonical form:
      - user text: location block stripped, lowercased, whitespace collapsed,
        trailing punctuation dropped
      - location: coordinates rounded to 3 decimals (~110 m grid)
    Same question near the same marker → same key, any user, any session.
    """
    core = strip_location_block(question)
    core = re.sub(r"\s+", " ", core.lower()).strip().rstrip("?!. ")

    coords = extract_coordinates(question)
    if coords:
        geo = f"{round(coords['latitude'], 3)},{round(coords['longitude'], 3)}"
    else:
        geo = "none"

    return cache_manager._generate_cache_key({"q": core, "geo": geo})


def check_cache(state: GraphState) -> Dict[str, Any]:
    """
    Check if query response is cached.
    """
    print("---CHECK CACHE---")
    question = state["question"]

    # Canonical key: normalized text + ~110 m coordinate grid.
    cache_key = _canonical_cache_key(question)

    # Per-request opt-out and global switch both disable the read.
    if not state.get("use_cache", True) or not settings.ENABLE_CACHE:
        print("---CACHE BYPASSED (use_cache=False or ENABLE_CACHE=false)---")
        return {"cached_response": {}, "cache_key": cache_key}

    # Try to get cached response
    cached = cache_manager.get(cache_key, cache_type="response")

    if cached:
        print("---CACHE HIT---")
        return {
            "cached_response": cached,
            "cache_key": cache_key,
            "final_answer": cached.get("answer", "")
        }
    else:
        print("---CACHE MISS---")
        return {
            "cached_response": {},
            "cache_key": cache_key
        }

def parse_query(state: GraphState) -> Dict[str, Any]:
    """
    Parse the user query to extract coordinates and context.
    """
    print("---PARSE QUERY (INTENT FIRST)---")
    question = state["question"]

    # Coordinates come from the FULL text (the appended location block is where
    # they live); intent is judged on the user's own words only.
    coordinates = extract_coordinates(question)
    user_message = strip_location_block(question)

    # Detect trivial small-talk (greetings, thanks, "what can you do") so the
    # router can short-circuit the pipeline. No LLM call involved.
    smalltalk_type = _classify_smalltalk(question)
    if smalltalk_type:
        print(f"---INTENT: {smalltalk_type} → immediate reply, pipeline skipped---")
    else:
        print("---INTENT: geospatial query → retrieval chain---")

    return {
        "coordinates": coordinates or {},
        "location_context": {
            "is_greeting": smalltalk_type == "greeting",
            "smalltalk_type": smalltalk_type,
            "user_message": user_message,
        },
    }


def direct_response(state: GraphState) -> Dict[str, Any]:
    """
    Instant canned reply for greetings / small-talk — bypasses retrieval,
    tool execution, generation and all grader LLM calls.
    """
    print("---DIRECT RESPONSE (small-talk)---")
    smalltalk_type = state.get("location_context", {}).get("smalltalk_type", "greeting")
    answer = _SMALLTALK_REPLIES.get(smalltalk_type, _SMALLTALK_REPLIES["greeting"])
    return {
        "generation": answer,
        "final_answer": answer,
        "sources": [],
        "selected_tools": [],
    }

# Keyword → tool map for the rule-based fast path. When the intent is obvious
# we skip the tool-selection LLM call entirely (saves one round-trip per query).
_TOOL_KEYWORDS = [
    ({"weather", "temperature", "temp", "rain", "rainfall", "climate",
      "humidity", "wind", "forecast", "hot", "cold"}, "get_weather_data"),
    ({"history", "historical", "past", "recent", "trend", "seasonal"}, "get_recent_weather_data"),
    ({"road", "roads", "highway", "street", "infrastructure", "connectivity",
      "access", "accessibility", "transport"}, "get_road_network_data"),
    ({"pollution", "aqi", "air", "smog", "pm2", "pm10"}, "get_pollution_data"),
    ({"flood", "flooding", "waterlogging", "inundation", "drainage"}, "analyze_flood_risk"),
    ({"construction", "build", "building", "house", "housing", "apartment",
      "residential", "foundation"}, "analyze_construction_suitability"),
]
_GEO_KEYWORDS = {
    "soil", "terrain", "land", "geomorphology", "erosion", "texture", "depth",
    "productivity", "degradation", "groundwater", "suitability", "agriculture",
    "farming", "crop", "site", "plot",
    # construction always needs the soil/terrain layer alongside the risk tool
    "construction", "build", "building", "house", "housing", "residential",
    "apartment", "foundation",
}


def _fast_select_tools(question: str):
    """
    Rule-based tool selection. Returns a tool list when the query clearly names
    a domain, else None so the LLM selector can decide.
    """
    tokens = set(re.sub(r"[^\w\s]", " ", question.lower()).split())
    selected = []
    for keys, tool in _TOOL_KEYWORDS:
        if tokens & keys:
            selected.append(tool)
    if tokens & _GEO_KEYWORDS or not selected:
        if "query_geospatial_index" not in selected:
            selected.insert(0, "query_geospatial_index")
    return selected or None


def select_tools(state: GraphState) -> Dict[str, Any]:
    """
    Select appropriate tools for the query.
    """
    print("---TOOL SELECTION---")
    question = state["question"]
    coordinates = state.get("coordinates", {})

    # Fast path: obvious keywords → skip the tool-selection LLM call.
    fast = _fast_select_tools(question)
    if fast:
        print(f"---TOOL SELECTION (rule-based, no LLM): {fast}---")
        return {
            "selected_tools": fast,
            "location_context": {
                **state.get("location_context", {}),
                "tool_selection_reasoning": "Rule-based keyword match (LLM selector skipped).",
            },
        }

    # Use tool selector
    selection_result = tool_selector.select_tools(question, coordinates)

    print(f"Selected tools: {selection_result['selected_tools']}")
    print(f"Reasoning: {selection_result['reasoning']}")

    return {
        "selected_tools": selection_result["selected_tools"],
        "location_context": {
            **state.get("location_context", {}),
            "tool_selection_reasoning": selection_result["reasoning"]
        }
    }

def retrieve(state: GraphState) -> Dict[str, Any]:
    """
    Retrieve documents from the vector store with caching.
    """
    print("---RETRIEVE---")
    question = state["question"]
    coordinates = state.get("coordinates", {})

    # Location-aware cache key: the same question at a different location must
    # not reuse a cached (geo-filtered) retrieval from elsewhere. Keyed on the
    # canonical text (location block stripped, normalized) plus a ~110 m
    # coordinate grid, so re-dropped pins still hit.
    lat = coordinates.get("latitude")
    lon = coordinates.get("longitude")
    core_text = re.sub(r"\s+", " ", strip_location_block(question).lower()).strip().rstrip("?!. ")

    # Domain-aware radius: soil varies at km scale, hazards are district-scale,
    # weather is regional. Pick the tightest radius the query's domain allows.
    tokens = set(core_text.split())
    if tokens & {"soil", "texture", "erosion", "productivity", "fertility",
                 "geomorphology", "agriculture", "farming", "crop", "cultivation"}:
        radius_km = settings.GEO_BOUNDS_RADIUS_SOIL_KM
    elif tokens & {"flood", "flooding", "risk", "hazard", "earthquake", "seismic",
                   "construction", "build", "building", "suitability"}:
        radius_km = settings.GEO_BOUNDS_RADIUS_RISK_KM
    else:
        radius_km = settings.GEO_BOUNDS_RADIUS_KM
    if lat is not None:
        print(f"---GEO RADIUS: {radius_km} km (domain-aware)---")

    geo_key = f"{round(lat, 3)},{round(lon, 3)},r{radius_km}" if lat is not None else "none"

    # Create source tracker
    tracker = SourceTracker()

    # Check embedding cache first
    def retrieve_with_cache(q, geo=None):
        result = rag_pipeline.retreival_vs(q, coordinates=coordinates, radius_km=radius_km)
        documents = result["documents"]

        # Track vector search
        tracker.add_vector_search_source(q, len(documents))

        # Track each document
        for doc in documents:
            tracker.add_document_source(
                doc.page_content,
                metadata=doc.metadata
            )

        return {
            "documents": documents,
            "tracker": tracker
        }

    cached_result = cache_manager.get_or_compute(
        core_text,
        retrieve_with_cache,
        cache_type="embedding",
        geo=geo_key,
    )

    if cached_result.get("from_cache"):
        tracker.add_cache_source(state.get("cache_key", ""), "embedding")

    return {
        "documents": [doc.page_content for doc in cached_result["documents"]],
        "sources": cached_result.get("tracker", tracker).get_sources()
    }

def grade_documents(state: GraphState) -> Dict[str, Any]:
    """
    Grade document relevance to the question.
    """
    print("---CHECK DOCUMENT RELEVANCE---")
    question = state["question"]
    documents = state["documents"]
    sources = state.get("sources", [])

    if not documents:
        return {"documents": [], "sources": [], "relevance_score": "fail"}

    # Grade all documents concurrently — these are independent LLM calls, so
    # running them in parallel turns K sequential round-trips into ~1.
    def _grade(doc):
        try:
            return retrieval_grader.invoke({"question": question, "document": doc}).binary_score
        except Exception as e:
            print(f"---GRADE ERROR (keeping doc): {e}---")
            return "yes"  # fail open: don't drop a doc because grading errored

    with ThreadPoolExecutor(max_workers=min(len(documents), 5)) as executor:
        grades = list(executor.map(_grade, documents))

    filtered_docs = []
    filtered_sources = []
    for idx, (doc, grade) in enumerate(zip(documents, grades)):
        if grade == "yes":
            print(f"---GRADE: DOCUMENT {idx+1} RELEVANT---")
            filtered_docs.append(doc)
            if idx < len(sources) and sources[idx].get("type") == "document":
                sources[idx]["relevance_grade"] = "relevant"
                filtered_sources.append(sources[idx])
        else:
            print(f"---GRADE: DOCUMENT {idx+1} NOT RELEVANT---")
            if idx < len(sources) and sources[idx].get("type") == "document":
                sources[idx]["relevance_grade"] = "not_relevant"

    return {
        "documents": filtered_docs,
        "sources": filtered_sources,
        "relevance_score": "pass" if filtered_docs else "fail"
    }

def execute_tools(state: GraphState) -> Dict[str, Any]:
    """
    Execute selected tools using real API implementations where available.
    Falls back gracefully if APIs are unavailable or coordinates are missing.
    """
    print("---EXECUTE TOOLS---")
    selected_tools = state.get("selected_tools", [])
    coordinates = state.get("coordinates", {})

    lat = coordinates.get("latitude")
    lon = coordinates.get("longitude")
    has_coords = lat is not None and lon is not None

    tool_results = {}
    sources = state.get("sources", [])
    tracker = SourceTracker()
    tracker.sources = list(sources)

    # Tool dispatch map — maps tool names to callables
    def _call(tool_name: str):
        if tool_name == "query_geospatial_index":
            # Handled by the retrieve/grade_documents nodes
            return None

        if not has_coords:
            return {"status": "skipped", "reason": "No coordinates extracted from query"}

        if tool_name == "get_weather_data":
            return weather_tool.get_weather_data(lat, lon)
        if tool_name == "get_recent_weather_data":
            return weather_tool.get_recent_weather_data(lat, lon)
        if tool_name == "get_weather_comparison":
            return weather_tool.get_weather_data(lat, lon)  # single-location fallback
        if tool_name == "get_road_network_data":
            return road_tool.get_road_network_data(lat, lon)
        if tool_name == "get_detailed_road_network_data":
            return road_tool.get_detailed_road_network_data(lat, lon)
        if tool_name == "compare_road_networks":
            return road_tool.get_road_network_data(lat, lon)  # single-location fallback
        if tool_name == "get_road_types_analysis":
            return road_tool.get_road_types_analysis(lat, lon)
        if tool_name == "analyze_flood_risk":
            # Uses road + terrain data as proxy until a dedicated flood API is integrated
            return road_tool.get_detailed_road_network_data(lat, lon)
        if tool_name == "analyze_construction_suitability":
            return road_tool.get_road_network_data(lat, lon)
        if tool_name == "get_pollution_data":
            # Open-Meteo Air Quality API — free, open, no API key.
            return weather_tool.get_air_quality_data(lat, lon)

        return {"status": "unknown_tool", "tool": tool_name}

    for tool_name in selected_tools:
        print(f"Executing tool: {tool_name}")
        try:
            result = _call(tool_name)
            if result is None:
                continue  # skipped (e.g. query_geospatial_index)
            tool_results[tool_name] = {"status": "success", "data": result}
            tracker.add_tool_source(tool_name, {"lat": lat, "lon": lon}, result, success=True)
        except Exception as e:
            print(f"Tool {tool_name} failed: {e}")
            tool_results[tool_name] = {"status": "error", "error": str(e)}
            tracker.add_tool_source(tool_name, {"lat": lat, "lon": lon}, str(e), success=False)

    return {
        "tool_results": tool_results,
        "sources": tracker.get_sources(),
    }

def generate(state: GraphState) -> Dict[str, Any]:
    """
    Generate answer using the documents and tool results.
    """
    print("---GENERATE---")
    question = state["question"]
    documents = state.get("documents", [])
    tool_results = state.get("tool_results", {})
    chat_history = state.get("chat_history", [])

    # Format inputs
    docs_text = "\n\n".join(documents) if documents else "No documents retrieved."
    tools_text = str(tool_results) if tool_results else "No tool results available."
    history_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in chat_history])

    # Generate answer
    generation = generator.invoke({
        "question": question,
        "documents": docs_text,
        "tool_results": tools_text,
        "chat_history": history_text
    })

    return {"generation": generation}

def check_hallucination(state: GraphState) -> Dict[str, Any]:
    """
    Check if the generation is grounded in documents or tool results.
    Falls back to tool_results when retrieved documents were all filtered out.
    """
    print("---CHECK HALLUCINATION---")
    if not settings.HALLUCINATION_CHECK_ENABLED:
        print("---HALLUCINATION CHECK DISABLED (settings)---")
        return {"hallucination_score": "pass"}

    documents  = state.get("documents", [])
    generation = state["generation"]
    tool_results = state.get("tool_results", {})

    # If the relevance grader filtered everything out, use tool results as
    # the grounding source instead — otherwise docs_text is empty and the
    # grader will always return "not grounded".
    if documents:
        docs_text = "\n\n".join(documents)
    elif tool_results:
        docs_text = "\n\n".join(
            f"{k}: {v}" for k, v in tool_results.items() if v
        )
    else:
        # Nothing to grade against — pass through to avoid infinite retries
        print("---HALLUCINATION CHECK SKIPPED: no source material---")
        return {"hallucination_score": "pass"}

    score = hallucination_grader.invoke({
        "documents": docs_text,
        "generation": generation
    })

    grade = score["binary_score"]

    # Handle both string ("yes") and bool (True) from the LLM JSON output
    if grade == "yes" or grade is True:
        print("---DECISION: GENERATION IS GROUNDED---")
        return {"hallucination_score": "pass"}
    else:
        print("---DECISION: GENERATION IS NOT GROUNDED---")
        return {"hallucination_score": "fail"}

def check_answer(state: GraphState) -> Dict[str, Any]:
    """
    Check if the answer addresses the question.
    """
    print("---CHECK ANSWER---")
    if not settings.ANSWER_CHECK_ENABLED:
        print("---ANSWER CHECK DISABLED (settings)---")
        return {"answer_score": "pass"}

    question = state["question"]
    generation = state["generation"]

    score = answer_grader.invoke({
        "question": question,
        "generation": generation
    })

    grade = score.binary_score

    if grade:
        print("---DECISION: ANSWER ADDRESSES QUESTION---")
        return {"answer_score": "pass"}
    else:
        print("---DECISION: ANSWER DOES NOT ADDRESS QUESTION---")
        return {"answer_score": "fail"}

def format_final_answer(state: GraphState) -> Dict[str, Any]:
    """
    Format the final answer with sources.
    """
    print("---FORMAT FINAL ANSWER---")
    generation = state["generation"]
    sources = state.get("sources", [])

    # Create source tracker from sources list
    tracker = SourceTracker()
    tracker.sources = sources

    # Format sources
    sources_text = tracker.format_sources_for_display()

    # Combine generation with sources
    final_answer = f"{generation}\n\n{sources_text}"

    # Cache the response
    cache_key = state.get("cache_key")
    if cache_key:
        cache_manager.set(
            cache_key,
            {
                "answer": final_answer,
                "generation": generation,
                "sources": sources
            },
            cache_type="response"
        )

    return {
        "final_answer": final_answer
    }

def increment_retry(state: GraphState) -> Dict[str, Any]:
    """
    Increment retry counter.
    """
    retry_count = state.get("retry_count", 0) + 1
    print(f"---RETRY COUNT: {retry_count}---")
    return {"retry_count": retry_count}