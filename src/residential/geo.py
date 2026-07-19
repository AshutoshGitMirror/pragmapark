"""Residential geospatial utilities (no external deps).

Provides a pure-python geohash for stable spatial bucketing of residential
slots, plus a PLACEHOLDER availability predictor. Phase 3 trains a real
model from observed signals (share-listing status, active bookings, the
resident's own platform allocation events, neighborhood aggregates, learned
time/weekday patterns); this stub is only here so the map layer has something
to draw until then.
"""

import math
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple

# Geohash alphabet (RFC 4648 base32, bitwise order).
_GEOHASH_ALPHABET = "0123456789bcdefghjkmnpqrstuvwxyz"

# Wider Greater Mumbai bounding box (south, west, north, east).
MUMBAI_BBOX: Tuple[float, float, float, float] = (18.90, 72.78, 19.25, 72.98)

_DEFAULT_PRECISION = 7  # ~150m x 150m bucket


def geohash_encode(lat: float, lng: float, precision: int = _DEFAULT_PRECISION) -> str:
    """Encode WGS84 lat/lng to a geohash string at the given precision."""
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lng <= 180.0):
        raise ValueError("lat/lng out of range")
    lat_range = (-90.0, 90.0)
    lng_range = (-180.0, 180.0)
    bits: list[int] = []
    is_even = True  # alternate lng / lat
    while len(bits) < precision * 5:
        if is_even:
            mid = (lng_range[0] + lng_range[1]) / 2
            if lng >= mid:
                bits.append(1)
                lng_range = (mid, lng_range[1])
            else:
                bits.append(0)
                lng_range = (lng_range[0], mid)
        else:
            mid = (lat_range[0] + lat_range[1]) / 2
            if lat >= mid:
                bits.append(1)
                lat_range = (mid, lat_range[1])
            else:
                bits.append(0)
                lat_range = (lat_range[0], mid)
        is_even = not is_even
    out = []
    for i in range(0, len(bits), 5):
        chunk = bits[i : i + 5]
        val = 0
        for b in chunk:
            val = (val << 1) | b
        out.append(_GEOHASH_ALPHABET[val])
    return "".join(out)


def spatial_id(lat: float, lng: float, precision: int = _DEFAULT_PRECISION) -> str:
    """Stable spatial bucket id for a residential slot (geohash)."""
    return geohash_encode(lat, lng, precision)


def decode_center(geohash: str) -> Tuple[float, float]:
    """Approximate center lat/lng of a geohash (for map pinning)."""
    lat_range = (-90.0, 90.0)
    lng_range = (-180.0, 180.0)
    is_even = True
    for ch in geohash:
        val = _GEOHASH_ALPHABET.index(ch)
        for mask in (16, 8, 4, 2, 1):
            bit = 1 if (val & mask) else 0
            if is_even:
                mid = (lng_range[0] + lng_range[1]) / 2
                lng_range = (mid, lng_range[1]) if bit else (lng_range[0], mid)
            else:
                mid = (lat_range[0] + lat_range[1]) / 2
                lat_range = (mid, lat_range[1]) if bit else (lat_range[0], mid)
            is_even = not is_even
    return ((lat_range[0] + lat_range[1]) / 2, (lng_range[0] + lng_range[1]) / 2)


def slot_geo(lat: float, lng: float, precision: int = _DEFAULT_PRECISION) -> Dict[str, object]:
    """Geospatial descriptor for a residential slot.

    `spatial_id` is the canonical parking-grid id: a "PK_" namespace prefix
    wrapping the geohash bucket so it is recognizable across services.
    """
    return {
        "latitude": lat,
        "longitude": lng,
        "spatial_id": f"PK_{spatial_id(lat, lng, precision)}",
        "precision": precision,
    }


def predict_availability(
    lat: float, lng: float, dt: Optional[datetime] = None
) -> Dict[str, object]:
    """PLACEHOLDER predictor (Phase 3 trains a real model).

    Returns P(available) at +15m and +60m from a smooth time-of-day curve.
    Home slots are most available during office hours. This is NOT a trained
    model — it is replaced by observed signals (share-listing status, active
    bookings, neighborhood aggregates, learned time patterns).
    """
    dt = dt or datetime.now(timezone.utc)
    hour = dt.hour + dt.minute / 60.0
    office = max(0.0, math.sin((hour - 7) / 10.0 * math.pi))  # 0..1 over ~07-17
    base = min(0.97, max(0.05, 0.35 + 0.55 * office))
    return {
        "p_available_15m": round(base, 3),
        "p_available_60m": round(min(0.97, base * 0.92 + 0.03), 3),
        "model": "stub_time_of_day",
    }


def in_mumbai(
    lat: float, lng: float, bbox: Tuple[float, float, float, float] = MUMBAI_BBOX
) -> bool:
    south, west, north, east = bbox
    return south <= lat <= north and west <= lng <= east
