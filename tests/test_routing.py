import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import pytest
from fastapi.testclient import TestClient

import src.api.server as server
from src.api.auth import get_current_user
from src.routing.router import nearest_node, route
from src.routing.graph_builder import ensure_graph


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
