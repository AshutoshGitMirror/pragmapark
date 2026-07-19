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


def _parse_maxspeed(v) -> float | None:
    """Safely parse an OSM ``maxspeed`` tag into kph (None if unknown).

    OSM values are wildly typed: ``"50"``, ``"30;40"`` (per-lane),
    ``"30 mph"``, ``None``, or even a float ``NaN`` (which is what
    breaks ``osmnx.add_edge_speeds`` under pandas 3.x — it shoves the
    NaN straight into ``re.split``). We parse defensively and never
    raise, defaulting to ``None`` so the caller can fall back.
    """
    if v is None:
        return None
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v) if (v and not math.isnan(v)) else None
    if isinstance(v, (list, tuple)):
        for item in v:
            s = _parse_maxspeed(item)
            if s:
                return s
        return None
    txt = str(v).split(";")[0].strip().lower().replace("mph", "").strip()
    try:
        return float(txt)
    except ValueError:
        return None


def _strip_attrs(G: nx.Graph) -> None:
    """Keep only what the router reads; drop heavy OSM tags.

    The committed pickle is served by the Render runtime, so we shave off
    every non-essential node/edge attribute (highway, name, lanes,
    oneway, surface, geometry, ref, ...) to keep the artifact lean on
    storage. The router only needs node ``x``/``y`` and edge
    ``length``/``travel_time``/``speed_kph``.
    """
    keep_node = {"x", "y"}
    keep_edge = {"length", "travel_time", "speed_kph"}
    for _, d in G.nodes(data=True):
        for k in [kk for kk in d if kk not in keep_node]:
            del d[k]
    for _, _, d in G.edges(data=True):
        for k in [kk for kk in d if kk not in keep_edge]:
            del d[k]


def build_city_graph(
    city: str = "Mumbai, India",
    bbox: tuple = MUMBAI_BOX,
    network_type: str = "drive",
) -> nx.Graph:
    """Pull a real street network from OpenStreetMap (build-time only).

    Downloads the drive network for ``bbox`` via ``osmnx``, collapses the
    resulting ``MultiDiGraph`` to a simple ``DiGraph`` (so the router's
    ``G[u][v]["length"]`` access pattern holds and one-way streets stay
    directional), then attaches real road travel-time weights computed in
    house from the OSM ``length`` + ``maxspeed`` tags. Never runs on
    the Render runtime (osmnx is build-only via ``requirements-geo.txt``).
    """
    try:
        import osmnx as ox
    except ImportError as exc:  # pragma: no cover - optional dep
        raise RuntimeError(
            "osmnx not installed; run `pip install -r requirements-geo.txt` "
            "(build-time only, needs network)"
        ) from exc

    south, west, north, east = bbox
    G = ox.graph_from_bbox(
        north, south, east, west, network_type=network_type, simplify=True
    )
    G = nx.relabel.convert_node_labels_to_integers(G)
    # Collapse any residual parallel edges -> simple DiGraph. Keeps one-way
    # directionality (correct for driving) and the router's edge access.
    G = nx.DiGraph(G)
    # Real travel-time weights inferred from OSM length + maxspeed.
    for u, v, d in G.edges(data=True):
        length = d.get("length")
        if length is None or (isinstance(length, float) and math.isnan(length)):
            a, b = G.nodes[u], G.nodes[v]
            length = _haversine_m(a["y"], a["x"], b["y"], b["x"])
        speed = _parse_maxspeed(d.get("maxspeed")) or 30.0
        d["length"] = float(length)
        d["speed_kph"] = float(speed)
        d["travel_time"] = float(length) / 1000.0 / speed * 3600.0
    # Lean pickle: drop every attribute the router does not read.
    _strip_attrs(G)
    logger.info(
        "event=routing.graph.osm city=%s nodes=%d edges=%d",
        city,
        G.number_of_nodes(),
        G.number_of_edges(),
    )
    return G


# Plan §3 names the builder `build_city_graph`; keep the OSM alias.
build_osm_graph = build_city_graph


def save_graph(G: nx.Graph, path: Path = GRAPH_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as fh:
        pickle.dump(G, fh)  # nosec B301 - trusted, app-generated graph artifact


def load_graph(path: Path = GRAPH_PATH) -> nx.Graph:
    with open(path, "rb") as fh:
        return pickle.load(fh)  # nosec B301 - trusted, app-generated graph artifact; type: ignore[no-any-return]


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
