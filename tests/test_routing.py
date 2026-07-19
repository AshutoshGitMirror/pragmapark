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
    G = ensure_graph()
    assert G.number_of_nodes() > 1000
    assert G.graph.get("_grid") is not None


def test_graph_fully_connected():
    """Any random pair must be routable -> the graph is one connected component."""
    G = ensure_graph()
    assert nx.is_connected(G), "routing graph must be a single connected component"


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
    pairs = _sample_node_pairs(G, 120)
    durations = []
    for origin, dest in pairs:
        t0 = time.perf_counter()
        res = route(origin, dest, "drive")
        durations.append(time.perf_counter() - t0)

        assert res["found"] is True, f"no route {origin}->{dest}"
        geom = res["geometry"]
        assert len(geom) >= 2

        # (a) path connects endpoints: geometry starts at origin node, ends at dest node
        assert abs(geom[0][0] - origin[0]) < 1e-6 and abs(geom[0][1] - origin[1]) < 1e-6
        assert abs(geom[-1][0] - dest[0]) < 1e-6 and abs(geom[-1][1] - dest[1]) < 1e-6

        # (c) ETA > 0 for distinct points
        assert res["duration_s"] > 0

        # (b) acyclic / shortest: route distance >= straight-line distance
        straight = _haversine_m(origin[0], origin[1], dest[0], dest[1])
        assert res["distance_m"] >= straight - 1e-6

        # (b) monotonic: cumulative segment lengths == reported distance
        cum = 0.0
        for (la, ln), (lb, lg) in zip(geom[:-1], geom[1:]):
            cum += _haversine_m(la, ln, lb, lg)
        assert abs(cum - res["distance_m"]) < max(1.0, res["distance_m"] * 0.05)

    # (d) p95 latency budget (grid routing is sub-100ms; generous ceiling)
    durations.sort()
    p95 = durations[int(0.95 * (len(durations) - 1))]
    assert p95 < 1.0, f"p95 route latency {p95 * 1000:.1f}ms exceeds 1000ms budget"


def test_osm_build_path_attaches_travel_times(monkeypatch):
    """Plan §3: the OSM build path must use osmnx add_edge_speeds +
    add_edge_travel_times to attach real road travel-time weights.

    Verified without network by injecting a fake ``osmnx`` module that
    returns a small OSM-like MultiDiGraph.
    """
    import types

    fake_graph = nx.MultiDiGraph()
    coords = [(19.000, 72.800), (19.001, 72.801), (19.002, 72.802)]
    for i, (y, x) in enumerate(coords):
        fake_graph.add_node(i, x=x, y=y)
    fake_graph.add_edge(0, 1, length=100.0, highway="residential")
    fake_graph.add_edge(1, 2, length=100.0, highway="residential")
    fake_graph.add_edge(0, 2, length=300.0, highway="primary")

    speeds = {"residential": 30.0, "primary": 50.0}

    class _FakeOx:
        def graph_from_bbox(self, *args, **kwargs):
            return fake_graph

        def add_edge_speeds(self, G, hwy_speeds=None):
            for u, v, k, d in G.edges(keys=True, data=True):
                d["speed_kph"] = speeds.get(d.get("highway"), 30.0)

        def add_edge_travel_times(self, G):
            for u, v, k, d in G.edges(keys=True, data=True):
                sp = d.get("speed_kph", 30.0)
                d["travel_time"] = float(d["length"]) / 1000.0 / sp * 3600.0

    fake = types.ModuleType("osmnx")
    inst = _FakeOx()
    fake.graph_from_bbox = inst.graph_from_bbox
    fake.add_edge_speeds = inst.add_edge_speeds
    fake.add_edge_travel_times = inst.add_edge_travel_times
    monkeypatch.setitem(sys.modules, "osmnx", fake)

    from src.routing.graph_builder import build_city_graph

    G = build_city_graph("Mumbai, India")
    assert G.number_of_nodes() == 3
    for u, v, k, d in G.edges(keys=True, data=True):
        assert "travel_time" in d and d["travel_time"] > 0
        # primary (50kph) edge must be faster than residential (30kph)
        if d.get("highway") == "primary":
            assert d["speed_kph"] == 50.0
        else:
            assert d["speed_kph"] == 30.0
