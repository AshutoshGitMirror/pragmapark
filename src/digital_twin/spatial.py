"""Real spatial grounding for the digital twin.

This module replaces the previous random-embedding "spatial" model. It builds
a *sparse, persisted* adjacency graph between parking lots using:

  * real ``lat``/``lng`` coordinates (from ``ParkingLot``),
  * road-network travel time from the committed OSM graph
    (``data/geo/mumbai_graph.gpickle``) when available,
  * straight-line distance as a fallback when the road graph is absent.

No synthetic data is treated as evidence. The graph is persisted to
``data/geo/lot_adjacency.json`` so it survives restarts (P3: "persisted sparse
adjacency graph"). Distance bands let callers ask "nearby vs unrelated".

All functions are pure / stateless; the only in-memory cache is the loaded
adjacency JSON (re-loaded on each call to stay correct after a restart).
"""
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

ADJ_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "data"
    / "geo"
    / "lot_adjacency.json"
)

# Distance bands (metres). Anything beyond ``FAR_M`` is treated as "unrelated"
# for spatial coupling (no edge).
NEAR_M = 1500.0
MID_M = 5000.0
FAR_M = 12000.0


def _haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    import math

    r = 6371008.8
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


def _road_distance_m(a: Tuple[float, float], b: Tuple[float, float]) -> Optional[float]:
    """Road-network distance via the committed OSM graph.

    Returns ``None`` if the graph/routing is unavailable (caller falls back
    to straight-line). The road graph is build-time only and lazy-loaded.
    """
    try:
        from src.routing.router import route

        res = route(a, b, mode="drive")
        if res.get("found"):
            return float(res.get("distance_m") or 0.0) or None
        return None
    except Exception as e:  # pragma: no cover - runtime graph optional
        logger.debug("event=spatial.road_distance_unavailable error=%s", e)
        return None


def _lot_coords() -> Dict[str, Tuple[float, float]]:
    """Real parking-lot coordinates from the database (source of truth)."""
    from src.api.database import get_db_cm, ParkingLot

    coords: Dict[str, Tuple[float, float]] = {}
    try:
        with get_db_cm() as db:
            for lot in db.query(ParkingLot).all():
                if lot.latitude is not None and lot.longitude is not None:
                    coords[lot.lot_id] = (float(lot.latitude), float(lot.longitude))
    except Exception as e:  # pragma: no cover
        logger.warning("event=spatial.lot_coords_failed error=%s", e)
    return coords


def distance_band(m: float) -> str:
    if m <= NEAR_M:
        return "near"
    if m <= MID_M:
        return "mid"
    if m <= FAR_M:
        return "far"
    return "unrelated"


def build_adjacency(recompute: bool = False) -> Dict[str, Dict[str, float]]:
    """Build (and persist) the sparse lot adjacency graph.

    Edge weight = road distance (metres) when available, else straight-line
    distance. Edges are stored only for pairs within ``FAR_M``. The result is
    persisted to ``ADJ_PATH`` and returned.

    This must ONLY be called from an offline/build step or a thin admin
    endpoint. It does NOT auto-actuate anything.
    """
    coords = _lot_coords()
    adj: Dict[str, Dict[str, float]] = {lid: {} for lid in coords}
    ids = list(coords.keys())
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            a, b = ids[i], ids[j]
            road = _road_distance_m(coords[a], coords[b])
            d = road if road is not None else _haversine_m(
                coords[a][0], coords[a][1], coords[b][0], coords[b][1]
            )
            if d <= FAR_M:
                adj[a][b] = d
                adj[b][a] = d
    _persist(adj)
    return adj


def _persist(adj: Dict[str, Dict[str, float]]) -> None:
    try:
        ADJ_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = ADJ_PATH.with_suffix(".json.tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(adj, fh)
        tmp.replace(ADJ_PATH)
    except Exception as e:  # pragma: no cover
        logger.warning("event=spatial.persist_failed error=%s", e)


def load_adjacency() -> Dict[str, Dict[str, float]]:
    """Load persisted adjacency. Falls back to empty graph if missing."""
    if not ADJ_PATH.exists():
        return {}
    try:
        with open(ADJ_PATH, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception as e:  # pragma: no cover
        logger.warning("event=spatial.load_failed error=%s", e)
        return {}


def neighbors(lot_id: str, max_band: str = "far") -> List[Tuple[str, float, str]]:
    """Return (neighbor_id, distance_m, band) for spatially coupled lots."""
    order = {"near": 0, "mid": 1, "far": 2, "unrelated": 3}
    cap = order.get(max_band, 2)
    adj = load_adjacency()
    out: List[Tuple[str, float, str]] = []
    for nid, d in adj.get(lot_id, {}).items():
        band = distance_band(d)
        if order.get(band, 3) <= cap:
            out.append((nid, d, band))
    out.sort(key=lambda t: t[1])
    return out


def coupling_strength(lot_a: str, lot_b: str) -> float:
    """Spatial coupling in [0, 1]: 1 = co-located, 0 = unrelated/far.

    Based on real distance, not a learned embedding. Deterministic and
    explainable.
    """
    adj = load_adjacency()
    d = adj.get(lot_a, {}).get(lot_b)
    if d is None:
        ca = load_adjacency().get(lot_a, {})
        cb = load_adjacency().get(lot_b, {})
        # If adjacency missing entirely, use straight-line from coords.
        coords = _lot_coords()
        if lot_a in coords and lot_b in coords:
            d = _haversine_m(*coords[lot_a], *coords[lot_b])
        else:
            return 0.0
    if d is None:
        return 0.0
    if d <= 0.0:
        return 1.0
    return float(max(0.0, 1.0 - d / FAR_M))
