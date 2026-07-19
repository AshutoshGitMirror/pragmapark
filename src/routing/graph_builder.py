"""Deterministic road-graph builder for driver navigation.

Two sources of graph data:
  1. ``build_osm_graph`` - pulls a real street network from OpenStreetMap
     via ``osmnx``. Build-time only (needs network + the optional
     ``requirements-geo.txt`` deps). Never runs on the Render runtime.
  2. ``build_synthetic_grid`` - a fully deterministic synthetic Mumbai
     street grid (no network). This is what is commited as
     ``data/geo/mumbai_graph.gpickle`` so CI and the prod runtime are
     network-free, and the Dijkstra router is 100% real (networkx).

To swap in live OSM later: run ``build_osm_graph`` locally, drop the
resulting pickle at ``data/geo/mumbai_graph.gpickle``, commit it. The
router loads whatever pickle exists with no code change.
"""
import logging
import math
import pickle
import random
from pathlib import Path

import networkx as nx

logger = logging.getLogger(__name__)

# Wider Greater Mumbai bounding box: (south, west, north, east)
MUMBAI_BOX = (18.90, 72.78, 19.25, 72.98)

GRAPH_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "data"
    / "geo"
    / "mumbai_graph.gpickle"
)

EARTH_R_KM = 6371.0088


def _haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in metres."""
    r = math.radians
    dlat = r(lat2 - lat1)
    dlng = r(lng2 - lng1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(r(lat1)) * math.cos(r(lat2)) * math.sin(dlng / 2) ** 2
    )
    return 2 * EARTH_R_KM * 1000.0 * math.asin(math.sqrt(a))


def build_synthetic_grid(
    box=MUMBAI_BOX,
    rows: int = 150,
    cols: int = 85,
    seed: int = 2024,
    arterial_fraction: float = 0.18,
) -> nx.Graph:
    """Build a deterministic synthetic Mumbai street grid.

    Every intersection is a node with ``x`` (longitude) / ``y`` (latitude)
    attributes (matching the osmnx convention) plus ``i``/``j`` grid
    indices. Edges carry ``length`` (m), ``travel_time`` (s, drive
    speeds), ``speed_kph`` and ``arterial`` so Dijkstra can weight by
    travel time. A handful of diagonal "arterial" shortcuts add realism.
    """
    rng = random.Random(seed)
    south, west, north, east = box
    G = nx.Graph()
    lat_step = (north - south) / (rows - 1)
    lng_step = (east - west) / (cols - 1)

    # Every Nth row/col is an arterial with higher speed.
    arterial_rows = set(range(0, rows, max(1, rows // 8)))
    arterial_cols = set(range(0, cols, max(1, cols // 6)))

    for i in range(rows):
        for j in range(cols):
            lat = south + i * lat_step
            lng = west + j * lng_step
            nid = i * cols + j
            G.add_node(nid, x=lng, y=lat, i=i, j=j)

    def add_edge(a: int, b: int) -> None:
        na, nb = G.nodes[a], G.nodes[b]
        d = _haversine_m(na["y"], na["x"], nb["y"], nb["x"])
        arterial = (
            na["i"] in arterial_rows
            or na["j"] in arterial_cols
            or nb["i"] in arterial_rows
            or nb["j"] in arterial_cols
        )
        speed = rng.uniform(45, 60) if arterial else rng.uniform(22, 34)
        t = d / 1000.0 / speed * 3600.0
        G.add_edge(
            a, b, length=d, travel_time=t, speed_kph=speed, arterial=arterial
        )

    for i in range(rows):
        for j in range(cols):
            a = i * cols + j
            if j + 1 < cols:
                add_edge(a, a + 1)
            if i + 1 < rows:
                add_edge(a, a + cols)

    diag_target = int(rows * cols * arterial_fraction)
    for _ in range(diag_target):
        i = rng.randrange(rows - 1)
        j = rng.randrange(cols - 1)
        add_edge(i * cols + j, (i + 1) * cols + (j + 1))

    logger.info(
        "event=routing.graph.synthetic nodes=%d edges=%d",
        G.number_of_nodes(),
        G.number_of_edges(),
    )
    G.graph["_grid"] = {
        "rows": rows,
        "cols": cols,
        "min_lat": south,
        "min_lon": west,
        "dlat": lat_step,
        "dlon": lng_step,
    }
    return G


def build_osm_graph(
    city: str = "Mumbai, India", box=MUMBAI_BOX, network_type: str = "drive"
) -> nx.Graph:
    """Pull a real street network from OSM (build-time only)."""
    try:
        import osmnx as ox
    except ImportError as exc:  # pragma: no cover - optional dep
        raise RuntimeError(
            "osmnx not installed; run with requirements-geo.txt (build-time only)"
        ) from exc

    south, west, north, east = box
    G = ox.graph_from_bbox(
        north, south, east, west, network_type=network_type, simplify=True
    )
    G = nx.relabel.convert_node_labels_to_integers(G)
    for u, v, d in G.edges(data=True):
        length = d.get("length")
        if length is None:
            a = G.nodes[u]
            b = G.nodes[v]
            length = _haversine_m(a["y"], a["x"], b["y"], b["x"])
        speed = 30.0
        d["length"] = float(length)
        d["travel_time"] = float(length) / 1000.0 / speed * 3600.0
        d["speed_kph"] = speed
    return G


def save_graph(G: nx.Graph, path: Path = GRAPH_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as fh:
        pickle.dump(G, fh)


def load_graph(path: Path = GRAPH_PATH) -> nx.Graph:
    with open(path, "rb") as fh:
        return pickle.load(fh)  # type: ignore[no-any-return]


def ensure_graph(path: Path = GRAPH_PATH) -> nx.Graph:
    """Load the commited pickle, else build + cache the synthetic grid."""
    if path.exists():
        return load_graph(path)
    G = build_synthetic_grid()
    save_graph(G, path)
    return G


if __name__ == "__main__":
    import sys

    if "--osm" in sys.argv:
        g = build_osm_graph()
    else:
        g = build_synthetic_grid()
    save_graph(g)
    print(
        f"wrote {GRAPH_PATH} nodes={g.number_of_nodes()} "
        f"edges={g.number_of_edges()}"
    )
