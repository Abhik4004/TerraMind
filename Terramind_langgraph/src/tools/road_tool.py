"""
Real road network tool using the Overpass API (OpenStreetMap) — no API key needed.

Public endpoint: https://overpass-api.de/api/interpreter
Usage policy: avoid more than 1 request/second; respect timeout limits.
Results are cached via cache_manager.
"""
import time
import httpx
import math
from typing import Dict, Any, List, Tuple
from src.config.settings import settings
from src.utils.cache_manager import cache_manager

# Overpass mirrors, tried in order. The main endpoint rate-limits and, without a
# descriptive User-Agent, answers 406 Not Acceptable — so a UA is mandatory.
_OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]
_OVERPASS_URL = _OVERPASS_URLS[0]  # kept for backwards compatibility
_TIMEOUT = settings.TOOL_TIMEOUT

_HEADERS = {
    "User-Agent": "TerraMind/1.0 (academic project; geospatial land analysis)",
    "Accept": "application/json",
    "Content-Type": "application/x-www-form-urlencoded",
}

# Road type hierarchy for classification
_ROAD_HIERARCHY = [
    "motorway", "trunk", "primary", "secondary",
    "tertiary", "residential", "unclassified", "service",
    "motorway_link", "trunk_link", "primary_link", "secondary_link",
]


class RoadToolError(Exception):
    pass


def _overpass_query(query: str) -> dict:
    """
    POST an Overpass QL query, falling back across mirrors.

    Overpass answers 406 without a descriptive User-Agent, and 429/504 when
    the public instance is busy, so every mirror is retried before giving up.
    """
    last_err = None
    for url in _OVERPASS_URLS:
        for attempt in range(2):
            try:
                resp = httpx.post(url, data={"data": query}, timeout=_TIMEOUT, headers=_HEADERS)
                resp.raise_for_status()
                return resp.json()
            except httpx.HTTPStatusError as e:
                code = e.response.status_code
                last_err = RoadToolError(f"Overpass API error {code} at {url}")
                # 429 (rate limit) and 504 (gateway timeout) are worth a retry;
                # anything else on this mirror, move to the next one.
                if code not in (429, 504):
                    break
                time.sleep(1.5 * (attempt + 1))
            except Exception as e:
                last_err = RoadToolError(f"Overpass request failed at {url}: {e}")
                break
    raise last_err if last_err else RoadToolError("Overpass: all mirrors failed")


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _estimate_way_length_km(nodes_by_id: dict, node_refs: list) -> float:
    total = 0.0
    for i in range(len(node_refs) - 1):
        n1 = nodes_by_id.get(node_refs[i])
        n2 = nodes_by_id.get(node_refs[i + 1])
        if n1 and n2:
            total += _haversine_km(n1["lat"], n1["lon"], n2["lat"], n2["lon"])
    return total


def get_road_network_data(lat: float, lon: float, radius_m: int = 1000) -> Dict[str, Any]:
    """
    Query Overpass API for roads within `radius_m` metres of (lat, lon).

    Returns road type counts and estimated total length.
    """
    cache_key = cache_manager._generate_cache_key(
        {"tool": "get_road_network_data", "lat": round(lat, 3), "lon": round(lon, 3), "r": radius_m}
    )
    cached = cache_manager.get(cache_key, cache_type="tool")
    if cached:
        cached["from_cache"] = True
        return cached

    query = f"""
[out:json][timeout:{_TIMEOUT}];
(
  way["highway"](around:{radius_m},{lat},{lon});
);
out body;
>;
out skel qt;
"""
    data = _overpass_query(query)
    elements = data.get("elements", [])

    nodes_by_id = {e["id"]: e for e in elements if e["type"] == "node"}
    ways = [e for e in elements if e["type"] == "way"]

    road_types: Dict[str, int] = {}
    total_length_km = 0.0

    for way in ways:
        hw = way.get("tags", {}).get("highway", "other")
        road_types[hw] = road_types.get(hw, 0) + 1
        total_length_km += _estimate_way_length_km(nodes_by_id, way.get("nodes", []))

    result = {
        "total_roads": len(ways),
        "road_types": road_types,
        "total_length_km": round(total_length_km, 3),
        "search_radius_m": radius_m,
        "from_cache": False,
    }
    cache_manager.set(cache_key, result, cache_type="tool")
    return result


def get_detailed_road_network_data(lat: float, lon: float, radius_m: int = 2000) -> Dict[str, Any]:
    """
    Extended road network analysis: adds intersection count, road density, and connectivity score.
    """
    cache_key = cache_manager._generate_cache_key(
        {"tool": "get_detailed_road_network_data", "lat": round(lat, 3), "lon": round(lon, 3), "r": radius_m}
    )
    cached = cache_manager.get(cache_key, cache_type="tool")
    if cached:
        cached["from_cache"] = True
        return cached

    query = f"""
[out:json][timeout:{_TIMEOUT}];
(
  way["highway"](around:{radius_m},{lat},{lon});
);
out body;
>;
out skel qt;
"""
    data = _overpass_query(query)
    elements = data.get("elements", [])

    nodes_by_id = {e["id"]: e for e in elements if e["type"] == "node"}
    ways = [e for e in elements if e["type"] == "way"]

    # Count how many ways each node appears in (degree)
    node_degree: Dict[int, int] = {}
    road_types: Dict[str, int] = {}
    total_length_km = 0.0

    for way in ways:
        hw = way.get("tags", {}).get("highway", "other")
        road_types[hw] = road_types.get(hw, 0) + 1
        total_length_km += _estimate_way_length_km(nodes_by_id, way.get("nodes", []))
        for nid in way.get("nodes", []):
            node_degree[nid] = node_degree.get(nid, 0) + 1

    intersections = sum(1 for deg in node_degree.values() if deg >= 3)
    area_km2 = math.pi * (radius_m / 1000) ** 2
    road_density = round(total_length_km / area_km2, 3) if area_km2 > 0 else 0

    # Simple connectivity score 0–10
    connectivity = min(10, round((intersections / max(len(ways), 1)) * 5, 1))

    result = {
        "total_roads": len(ways),
        "road_types": road_types,
        "total_length_km": round(total_length_km, 3),
        "intersections": intersections,
        "road_density_km_per_km2": road_density,
        "connectivity_score": connectivity,
        "search_radius_m": radius_m,
        "area_km2": round(area_km2, 3),
        "from_cache": False,
    }
    cache_manager.set(cache_key, result, cache_type="tool")
    return result


def get_road_types_analysis(lat: float, lon: float, radius_m: int = 1000) -> Dict[str, Any]:
    """Breakdown of road types with percentages and hierarchy classification."""
    base = get_road_network_data(lat, lon, radius_m)
    road_types = base.get("road_types", {})
    total = base.get("total_roads", 0)

    breakdown = {}
    for rtype, count in road_types.items():
        tier = (
            "major" if rtype in ("motorway", "trunk", "primary")
            else "secondary" if rtype in ("secondary", "tertiary")
            else "local" if rtype in ("residential", "unclassified", "service")
            else "link/other"
        )
        breakdown[rtype] = {
            "count": count,
            "percentage": round(count / total * 100, 1) if total else 0,
            "tier": tier,
        }

    return {
        "total_roads": total,
        "breakdown": breakdown,
        "search_radius_m": radius_m,
    }


def compare_road_networks(locations: List[Tuple[float, float]], radius_m: int = 1000) -> Dict[str, Any]:
    """Compare road networks across multiple (lat, lon) pairs."""
    comparison = {}
    for idx, (lat, lon) in enumerate(locations):
        label = f"location_{idx + 1}"
        try:
            comparison[label] = get_road_network_data(lat, lon, radius_m)
        except RoadToolError as e:
            comparison[label] = {"error": str(e)}
    return {"comparison": comparison, "location_count": len(locations)}
