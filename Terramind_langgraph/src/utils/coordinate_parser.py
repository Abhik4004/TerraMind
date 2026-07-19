import re
from typing import Optional, Dict

def extract_coordinates(query: str) -> Optional[Dict[str, float]]:
    """
    Extract latitude and longitude from a query string.
    Always assumes (latitude, longitude) order.

    Args:
        query: User query string

    Returns:
        Dictionary with 'latitude' and 'longitude' keys, or None if not found
    """
    # Pattern for decimal degrees with optional N/S/E/W
    patterns = [
        # Pattern: 22.5726° N, 88.3639° E or 22.5726°N, 88.3639°E
        r'(-?\d+\.?\d*)\s*°?\s*[NS],?\s*(-?\d+\.?\d*)\s*°?\s*[EW]',
        # Labeled: "Lat: 22.5726, Lng: 88.3639" / "latitude=.. longitude=.."
        # (also matches the frontend's "(Lat: .., Lng: ..)" format).
        r'lat(?:itude)?\s*[:=]?\s*(-?\d+\.?\d*)[^\d\-]+?(?:lng|long|lon(?:gitude)?)\s*[:=]?\s*(-?\d+\.?\d*)',
        # Pattern: 22.5726, 88.3639
        r'(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)',
    ]

    for pattern in patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            val1 = float(match.group(1))
            val2 = float(match.group(2))

            # Determine which is lat and which is lon
            # Latitude range: -90 to 90 (smaller absolute values typically)
            # Longitude range: -180 to 180
            if abs(val1) <= 90 and abs(val2) <= 180:
                # Likely correct order: lat, lon
                lat, lon = val1, val2
            elif abs(val2) <= 90 and abs(val1) <= 180:
                # Swapped order: lon, lat
                lat, lon = val2, val1
                print(f"[WARN] Coordinates corrected from ({val1}, {val2}) to (lat: {lat}, lon: {lon})")
            else:
                # Invalid coordinates
                print(f"[WARN] Invalid coordinate values: ({val1}, {val2})")
                return None

            # Validate ranges
            if -90 <= lat <= 90 and -180 <= lon <= 180:
                return {
                    "latitude": lat,
                    "longitude": lon
                }

    return None

def validate_coordinates(lat: float, lon: float) -> bool:
    """
    Validate that coordinates are within valid ranges.

    Args:
        lat: Latitude value
        lon: Longitude value

    Returns:
        True if valid, False otherwise
    """
    return -90 <= lat <= 90 and -180 <= lon <= 180

def format_coordinates(coords: Dict[str, float]) -> str:
    """
    Format coordinates for display.

    Args:
        coords: Dictionary with 'latitude' and 'longitude'

    Returns:
        Formatted string
    """
    lat = coords["latitude"]
    lon = coords["longitude"]

    lat_dir = "N" if lat >= 0 else "S"
    lon_dir = "E" if lon >= 0 else "W"

    return f"{abs(lat)}° {lat_dir}, {abs(lon)}° {lon_dir}"