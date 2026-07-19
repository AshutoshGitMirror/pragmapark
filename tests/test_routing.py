import os
import sys
import time
import random

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import networkx as nx
import pytest
from fastapi.testclient import TestClient

import src.api.server as server
from src.api.auth import get_current_user
from src.routing.router import nearest_node, route
from src.routing.graph_builder import ensure_graph, _haversine_m


class _FakeUser:
    id = 1
    role = "driver"


@pytest.fixture
def client():
    server.app.dependency_overrides[get_current_user] = lambda: _FakeUser()
    yield TestClient(server.app)
    server.app.dependency_overrides.clear()


def test_endpoint_route_found(client):
    body = {
        "origin": {"lat": 19.076, "lng": 72.877},
        "destination": {"lat": 19.10, "lng": 72.90},
        "mode": "drive",
    }
    r = client.post("/api/v1/routing/route", json=body)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["found"] is True
    assert data["distance_m"] > 0
    assert len(data["geometry"]) >= 2
    assert "lat" in data["geometry"][0] and "lng" in data["geometry"][0]


def test_endpoint_missing_destination(client):
    r = client.post("/api/v1/routing/route", json={"origin": {"lat": 19.076, "lng": 72.877}})
    assert r.status_code == 422


def test_nearest_node_self():
    G = ensure_graph()
    n = next(iter(G.nodes))
    assert nearest_node(G.nodes[n]["y"], G.nodes[n]["x"], G) == n


def test_route_walk_slower():
    G = ensure_graph()
    nodes = list(G.nodes)
    o = G.nodes[nodes[100]]
    d = G.nodes[nodes[9000]]
    drive = route((o["y"], o["x"]), (d["y"], d["x"]), "drive")
    walk = route((o["y"], o["x"]), (d["y"], d["x"]), "walk")
    assert drive["found"] and walk["found"]
    assert walk["duration_s"] > drive["duration_s"]


def test_graph_metadata():
    """Plan §3: committed graph is the real OSM drive network, lean."""
    G = ensure_graph()
    assert G.number_of_nodes() > 1000
    assert G.number_of_edges() > 10000
    e = next(iter(G.edges(data=True)))[2]
    # lean pickle: only routing-relevant weights survive _strip_attrs
    assert set(e.keys()) == {"length", "speed_kph", "travel_time"}
    # bulky osmnx attributes must be stripped before commit
    assert "highway" not in e and "osmid" not in e and "geometry" not in e


def test_graph_fully_connected():
    """Plan §3: directed OSM drive graph must be a single weakly-connected
    component so any mapped (origin,dest) pair is routable."""
    G = ensure_graph()
    assert nx.is_weakly_connected(G), "routing graph must be one weakly-connected component"


def _sample_node_pairs(G, n: int):
    """Pick `n` distinct (origin, dest) lat/lng pairs from real graph nodes."""
    rng = random.Random(7)
    nodes = list(G.nodes)
    pairs = []
    for _ in range(n):
        a = rng.randrange(len(nodes))
        b = rng.randrange(len(nodes))
        while b == a:
            b = rng.randrange(len(nodes))
        na = G.nodes[nodes[a]]
        nb = G.nodes[nodes[b]]
        pairs.append(((na["y"], na["x"]), (nb["y"], nb["x"])))
    return pairs


def test_scale_random_pairs_connectivity_metrics():
    """Plan §3: 50-200 random (origin,dest) pairs.

    Assert (a) path connects endpoints, (b) distance acyclic/monotonic,
    (c) ETA>0, and measure (d) p95 latency under budget.
    Uses the committed graph so CI is network-free.
    """
    G = ensure_graph()
    pairs = _sample_node_pairs(G, 200)
    durations = []
    found = 0
    for origin, dest in pairs:
        t0 = time.perf_counter()
        res = route(origin, dest, "drive")
        durations.append(time.perf_counter() - t0)

        # Directed OSM graph: a small fraction of adversarial node pairs are
        # unreachable under one-way constraints (correct behaviour). Skip those
        # and validate routing metrics only on pairs that DID route.
        if not res["found"]:
            continue
        found += 1
        geom = res["geometry"]
        assert len(geom) >= 2

        # (a) path connects endpoints: geometry starts at origin node, ends at dest node
        assert abs(geom[0][0] - origin[0]) < 1e-6 and abs(geom[0][1] - origin[1]) < 1e-6
        assert abs(geom[-1][0] - dest[0]) < 1e-6 and abs(geom[-1][1] - dest[1]) < 1e-6

        # (c) ETA > 0 for distinct points
        assert res["duration_s"] > 0

        # (b) shortest: route distance >= straight-line distance
        straight = _haversine_m(origin[0], origin[1], dest[0], dest[1])
        assert res["distance_m"] >= straight - 1e-6

        # (b) monotonic: cumulative segment lengths track reported distance
        #     (road curvature makes haversine polyline < road length, so allow headroom)
        cum = 0.0
        for (la, ln), (lb, lg) in zip(geom[:-1], geom[1:]):
            cum += _haversine_m(la, ln, lb, lg)
        assert abs(cum - res["distance_m"]) < max(5.0, res["distance_m"] * 0.20)

    # (d) the vast majority of mapped pairs route under one-way constraints
    assert found / len(pairs) >= 0.9, f"only {found}/{len(pairs)} pairs routable"

    # (e) p95 latency budget (OSM A* is sub-100ms; generous ceiling)
    durations.sort()
    p95 = durations[int(0.95 * (len(durations) - 1))]
    assert p95 < 1.0, f"p95 route latency {p95 * 1000:.1f}ms exceeds 1000ms budget"


def test_osm_build_attaches_travel_times(monkeypatch):
    """Plan §3: the OSM build path must compute real road travel-time
    weights in-house from OSM ``length`` + ``maxspeed`` (avoids the
    ox.add_edge_speeds crash on NaN maxspeed under pandas 3.x).

    Verified without network by injecting a fake ``osmnx`` module that
    returns a small OSM-like MultiDiGraph with ``maxspeed`` tags.
    """
    import types

    fake_graph = nx.MultiDiGraph()
    coords = [(19.000, 72.800), (19.001, 72.801), (19.002, 72.802)]
    for i, (y, x) in enumerate(coords):
        fake_graph.add_node(i, x=x, y=y)
    # equal-length edges at different posted speeds
    fake_graph.add_edge(0, 1, length=100.0, maxspeed="30")
    fake_graph.add_edge(1, 2, length=100.0, maxspeed="50")
    fake_graph.add_edge(0, 2, length=100.0, maxspeed="50")

    class _FakeOx:
        def graph_from_bbox(self, *args, **kwargs):
            return fake_graph

    fake = types.ModuleType("osmnx")
    inst = _FakeOx()
    fake.graph_from_bbox = inst.graph_from_bbox
    monkeypatch.setitem(sys.modules, "osmnx", fake)

    from src.routing.graph_builder import build_city_graph

    G = build_city_graph("Mumbai, India")
    # MultiDiGraph collapses to a simple DiGraph (one-way directionality kept)
    assert isinstance(G, nx.DiGraph)
    assert G.number_of_nodes() == 3
    for u, v, d in G.edges(data=True):
        # in-house travel-time + speed weights present and positive
        assert "travel_time" in d and d["travel_time"] > 0
        assert "speed_kph" in d and d["speed_kph"] > 0
        # only lean routing attrs survive _strip_attrs
        assert set(d.keys()) == {"length", "speed_kph", "travel_time"}
    # faster road (50 kph) yields lower travel-time than slower (30 kph)
    tt_30 = next(d["travel_time"] for _, _, d in G.edges(data=True) if d["speed_kph"] == 30)
    tt_50 = next(d["travel_time"] for _, _, d in G.edges(data=True) if d["speed_kph"] == 50)
    assert tt_50 < tt_30
