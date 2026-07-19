"""Dijkstra routing over the Mumbai road graph.

Loads the commited ``data/geo/mumbai_graph.gpickle`` (synthetic, but a
real networkx graph) and computes shortest paths by travel time. Swap in a
live-OSM pickle with no code change - the API shape is identical.
"""
import logging
from typing import Optional

import networkx as nx

from src.routing.graph_builder import ensure_graph, _haversine_m

logger = logging.getLogger(__name__)

_graph: Optional[nx.Graph] = None

# max drive speed in the synthetic graph (60 kph) -> fastest possible m/s.
# Used as the A* heuristic bound (admissible: real travel time is
# always >= straight-line-distance / max-speed).
_MAX_DRIVE_MS = 60.0 * 1000.0 / 3600.0


def _get_graph() -> nx.Graph:
    global _graph
    if _graph is None:
        _graph = ensure_graph()
    return _graph


def _haversine_h(u: int, v: int) -> float:
    """Admissible A* heuristic: straight-line seconds at max drive speed."""
    G = _graph
    if G is None:
        return 0.0
    nu, nv = G.nodes[u], G.nodes[v]
    return _haversine_m(nu["y"], nu["x"], nv["y"], nv["x"]) / _MAX_DRIVE_MS


def nearest_node(lat: float, lng: float, G: Optional[nx.Graph] = None) -> int:
    """Nearest graph node to a (lat, lng) point.

    For the committed synthetic grid the node layout is regular, so we map
    (lat, lng) -> grid cell in O(1) and jump straight to the node id
    (``nid = row*cols + col``). Only the OSM path (no grid metadata)
    falls back to a linear scan over the ~12k nodes, which is still
    sub-millisecond and avoids pulling in scipy on the runtime image.
    """
    G = G or _get_graph()
    grid = G.graph.get("_grid")
    if grid:
        r = int(round((lat - grid["min_lat"]) / grid["dlat"]))
        c = int(round((lng - grid["min_lon"]) / grid["dlon"]))
        r = max(0, min(r, grid["rows"] - 1))
        c = max(0, min(c, grid["cols"] - 1))
        nid = r * grid["cols"] + c
        if G.has_node(nid):
            return nid
    best: int = next(iter(G.nodes))
    best_d = float("inf")
    for n, d in G.nodes(data=True):
        dd = (d["y"] - lat) ** 2 + (d["x"] - lng) ** 2
        if dd < best_d:
            best_d = dd
            best = n
    return best


def route(
    origin: tuple[float, float],
    destination: tuple[float, float],
    mode: str = "drive",
    G: Optional[nx.Graph] = None,
) -> dict:
    """Shortest path between two (lat, lng) points.

    Returns a dict: ``found``, ``distance_m``, ``duration_s``, ``geometry``
    (list of ``(lat, lng)``), optional ``message``. ``mode`` only scales
    the walk speed (drive uses stored edge speeds).
    """
    G = G or _get_graph()
    o = nearest_node(origin[0], origin[1], G)
    d = nearest_node(destination[0], destination[1], G)

    if o == d:
        return {
            "found": True,
            "distance_m": _metrics(origin, destination),
            "duration_s": 0.0,
            "geometry": [origin, destination],
        }

    try:
        path = nx.astar_path(G, o, d, heuristic=_haversine_h, weight="travel_time")
    except nx.NetworkXNoPath:
        return {
            "found": False,
            "distance_m": 0.0,
            "duration_s": 0.0,
            "geometry": [],
            "message": "No route between the selected points",
        }

    speed_factor = {"drive": 1.0, "walk": 0.4}.get(mode, 1.0)
    distance = 0.0
    duration = 0.0
    geom: list[tuple[float, float]] = []
    for u, v in zip(path[:-1], path[1:]):
        e = G[u][v]
        distance += float(e["length"])
        duration += float(e["travel_time"]) / speed_factor
        geom.append((G.nodes[u]["y"], G.nodes[u]["x"]))
    geom.append((G.nodes[path[-1]]["y"], G.nodes[path[-1]]["x"]))

    return {
        "found": True,
        "distance_m": distance,
        "duration_s": duration,
        "geometry": geom,
    }


def _metrics(a: tuple[float, float], b: tuple[float, float]) -> float:
    from src.routing.graph_builder import _haversine_m

    return _haversine_m(a[0], a[1], b[0], b[1])
