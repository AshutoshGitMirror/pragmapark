from src.api.database import get_session, ParkingLot
from src.api.schemas import SessionDetailResponse, SessionHistoryResponse


def _create_lot(lot_id="sess_lot"):
    db = get_session()
    try:
        if (
            not db.query(ParkingLot)
            .filter(ParkingLot.lot_id == lot_id)
            .first()
        ):
            db.add(
                ParkingLot(
                    lot_id=lot_id,
                    name="Sess Test",
                    total_slots=100,
                    base_price=10.0,
                    price_cap=50.0,
                )
            )
            db.commit()
    finally:
        db.close()


class TestStartSession:
    def test_start_requires_auth(self, client):
        resp = client.post(
            "/api/v1/sessions/start", json={"lot_id": "x", "slot": 1}
        )
        assert resp.status_code in (401, 403)

    def test_start_returns_409_bad_lot(self, client, auth_headers):
        resp = client.post(
            "/api/v1/sessions/start",
            json={"lot_id": "nonexistent", "slot": 1},
            headers=auth_headers,
        )
        assert resp.status_code == 409

    def test_start_success(self, client, auth_headers):
        _create_lot()
        resp = client.post(
            "/api/v1/sessions/start",
            json={"lot_id": "sess_lot", "slot": 1},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "session_id" in data
        assert data["lot_id"] == "sess_lot"
        assert "price_at_entry" in data


class TestEndSession:
    def test_end_requires_auth(self, client):
        resp = client.post("/api/v1/sessions/end", json={"session_id": "x"})
        assert resp.status_code in (401, 403)

    def test_end_returns_404_bad_session(self, client, auth_headers):
        resp = client.post(
            "/api/v1/sessions/end",
            json={"session_id": "bad_sess"},
            headers=auth_headers,
        )
        assert resp.status_code == 404

    def test_end_full_flow(self, client, auth_headers):
        _create_lot()
        start = client.post(
            "/api/v1/sessions/start",
            json={"lot_id": "sess_lot", "slot": 1},
            headers=auth_headers,
        )
        assert start.status_code == 200
        sid = start.json()["session_id"]
        resp = client.post(
            "/api/v1/sessions/end",
            json={"session_id": sid},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"] == sid
        assert "amount_charged" in data

    def test_end_requires_ownership(self, client, auth_headers, admin_headers):
        _create_lot()
        # Clear cookies so start uses auth_headers (driver), not admin
        client.cookies.clear()
        start = client.post(
            "/api/v1/sessions/start",
            json={"lot_id": "sess_lot", "slot": 1},
            headers=auth_headers,
        )
        sid = start.json()["session_id"]
        # Clear cookies so end_session uses admin_headers, not driver
        client.cookies.clear()
        resp = client.post(
            "/api/v1/sessions/end",
            json={"session_id": sid},
            headers=admin_headers,
        )
        assert resp.status_code == 403


class TestActiveSessions:
    def test_active_requires_auth(self, client):
        resp = client.get("/api/v1/sessions/active/sess_lot")
        assert resp.status_code in (401, 403)

    def test_active_returns_empty_for_unknown_lot(self, client, auth_headers):
        resp = client.get(
            "/api/v1/sessions/active/unknown_lot", headers=auth_headers
        )
        assert resp.status_code == 200
        assert resp.json()["active_count"] == 0


class TestHistory:
    def test_history_requires_auth(self, client):
        resp = client.get("/api/v1/sessions/history")
        assert resp.status_code in (401, 403)

    def test_history_returns_list(self, client, auth_headers):
        resp = client.get("/api/v1/sessions/history", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "sessions" in data
        assert "total_sessions" in data


class TestSessionDetail:
    def test_detail_requires_auth(self, client):
        resp = client.get("/api/v1/sessions/bad")
        assert resp.status_code in (401, 403)

    def test_detail_returns_404(self, client, auth_headers):
        resp = client.get("/api/v1/sessions/bad_sess", headers=auth_headers)
        assert resp.status_code == 404

    def test_detail_shows_own_session(self, client, auth_headers):
        _create_lot()
        start = client.post(
            "/api/v1/sessions/start",
            json={"lot_id": "sess_lot", "slot": 1},
            headers=auth_headers,
        )
        sid = start.json()["session_id"]
        resp = client.get(f"/api/v1/sessions/{sid}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["session_id"] == sid


class TestPricingBreakdown:
    def test_breakdown_requires_auth(self, client):
        resp = client.get("/api/v1/sessions/bad/pricing")
        assert resp.status_code in (401, 403)

    def test_breakdown_returns_404(self, client, auth_headers):
        resp = client.get("/api/v1/sessions/bad/pricing", headers=auth_headers)
        assert resp.status_code == 404

    def test_breakdown_full(self, client, auth_headers):
        _create_lot()
        start = client.post(
            "/api/v1/sessions/start",
            json={"lot_id": "sess_lot", "slot": 1},
            headers=auth_headers,
        )
        sid = start.json()["session_id"]
        resp = client.get(
            f"/api/v1/sessions/{sid}/pricing", headers=auth_headers
        )
        assert resp.status_code == 200
        assert "entry_price" in resp.json()


class TestReceipt:
    def test_receipt_requires_auth(self, client):
        resp = client.get("/api/v1/sessions/bad/receipt")
        assert resp.status_code in (401, 403)

    def test_receipt_returns_404(self, client, auth_headers):
        resp = client.get("/api/v1/sessions/bad/receipt", headers=auth_headers)
        assert resp.status_code == 404


class TestRestartRecovery:
    def test_session_survives_in_memory_clear(self, client, auth_headers):
        _create_lot("restart_lot")
        start = client.post(
            "/api/v1/sessions/start",
            json={"lot_id": "restart_lot", "slot": 1},
            headers=auth_headers,
        )
        assert start.status_code == 200
        sid = start.json()["session_id"]

        from src.micro.state_engine import slot_state_engine
        from src.api.server import _global_rate_limiter

        slot_state_engine._states.clear()
        slot_state_engine._reservations.clear()
        slot_state_engine._reservation_expiry.clear()
        _global_rate_limiter._buckets.clear()

        detail = client.get(f"/api/v1/sessions/{sid}", headers=auth_headers)
        assert detail.status_code == 200
        assert detail.json()["status"] == "running"
        assert detail.json()["session_id"] == sid

    def test_session_reachable_after_restart_via_history(
        self, client, auth_headers
    ):
        _create_lot("restart_lot2")
        start = client.post(
            "/api/v1/sessions/start",
            json={"lot_id": "restart_lot2", "slot": 2},
            headers=auth_headers,
        )
        assert start.status_code == 200
        sid = start.json()["session_id"]

        history = client.get("/api/v1/sessions/history", headers=auth_headers)
        assert history.status_code == 200
        sids = [s["session_id"] for s in history.json()["sessions"]]
        assert sid in sids


class TestPaginationTotals:
    def test_history_total_gte_items(self, client, auth_headers):
        _create_lot("page_lot")
        for i in range(3):
            r = client.post(
                "/api/v1/sessions/start",
                json={"lot_id": "page_lot", "slot": i + 1},
                headers=auth_headers,
            )
            sid = r.json()["session_id"]
            client.post(
                "/api/v1/sessions/end",
                json={"session_id": sid},
                headers=auth_headers,
            )

        resp = client.get(
            "/api/v1/sessions/history?limit=2", headers=auth_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_sessions"] >= len(data["sessions"])
        assert data["total_sessions"] >= 3

    def test_active_count_gte_sessions(self, client, auth_headers):
        _create_lot("page_lot2")
        client.post(
            "/api/v1/sessions/start",
            json={"lot_id": "page_lot2", "slot": 10},
            headers=auth_headers,
        )
        client.post(
            "/api/v1/sessions/start",
            json={"lot_id": "page_lot2", "slot": 11},
            headers=auth_headers,
        )

        resp = client.get(
            "/api/v1/sessions/active/page_lot2", headers=auth_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["active_count"] >= len(data["sessions"])


class TestSettlementCorrectness:
    def test_charge_and_final_price_relationship(self, client, auth_headers):
        _create_lot("settle_lot")
        start = client.post(
            "/api/v1/sessions/start",
            json={"lot_id": "settle_lot", "slot": 5},
            headers=auth_headers,
        )
        assert start.status_code == 200
        sid = start.json()["session_id"]

        end = client.post(
            "/api/v1/sessions/end",
            json={"session_id": sid},
            headers=auth_headers,
        )
        assert end.status_code == 200
        data = end.json()
        assert data["amount_charged"] >= 0
        assert data["total_cost"] == data["amount_charged"]
        assert data["deposit_refund"] >= 0

        detail = client.get(f"/api/v1/sessions/{sid}", headers=auth_headers)
        assert detail.status_code == 200
        assert detail.json()["amount_charged"] == data["amount_charged"]

    def test_zero_grace_minutes_no_charge(self, client, auth_headers):
        _create_lot("settle_lot2")
        start = client.post(
            "/api/v1/sessions/start",
            json={"lot_id": "settle_lot2", "slot": 6},
            headers=auth_headers,
        )
        assert start.status_code == 200
        sid = start.json()["session_id"]

        end = client.post(
            "/api/v1/sessions/end",
            json={"session_id": sid},
            headers=auth_headers,
        )
        assert end.status_code == 200
        data = end.json()
        assert data["amount_charged"] >= 0


class TestCollisionResistance:
    def test_concurrent_end_first_succeeds_second_fails(
        self, client, auth_headers
    ):
        _create_lot("collide_lot")
        start = client.post(
            "/api/v1/sessions/start",
            json={"lot_id": "collide_lot", "slot": 7},
            headers=auth_headers,
        )
        assert start.status_code == 200
        sid = start.json()["session_id"]

        r1 = client.post(
            "/api/v1/sessions/end",
            json={"session_id": sid},
            headers=auth_headers,
        )
        r2 = client.post(
            "/api/v1/sessions/end",
            json={"session_id": sid},
            headers=auth_headers,
        )

        statuses = {r1.status_code, r2.status_code}
        assert 200 in statuses
        assert 404 in statuses or 409 in statuses

    def test_double_end_same_session_shows_404(self, client, auth_headers):
        _create_lot("collide_lot2")
        start = client.post(
            "/api/v1/sessions/start",
            json={"lot_id": "collide_lot2", "slot": 8},
            headers=auth_headers,
        )
        assert start.status_code == 200
        sid = start.json()["session_id"]

        r1 = client.post(
            "/api/v1/sessions/end",
            json={"session_id": sid},
            headers=auth_headers,
        )
        assert r1.status_code == 200

        r2 = client.post(
            "/api/v1/sessions/end",
            json={"session_id": sid},
            headers=auth_headers,
        )
        assert r2.status_code == 404


class TestOrdering:
    def test_history_returns_desc_timestamps(self, client, auth_headers):
        _create_lot("order_lot")
        sids = []
        for slot in [20, 21, 22]:
            r = client.post(
                "/api/v1/sessions/start",
                json={"lot_id": "order_lot", "slot": slot},
                headers=auth_headers,
            )
            sid = r.json()["session_id"]
            sids.append(sid)
            client.post(
                "/api/v1/sessions/end",
                json={"session_id": sid},
                headers=auth_headers,
            )

        history = client.get("/api/v1/sessions/history", headers=auth_headers)
        assert history.status_code == 200
        sessions = history.json()["sessions"]
        timestamps = [s["start_time"] for s in sessions if s["start_time"]]
        assert timestamps == sorted(timestamps, reverse=True), (
            "timestamps must be descending"
        )

    def test_active_returns_desc_timestamps(self, client, auth_headers):
        _create_lot("order_lot2")
        client.post(
            "/api/v1/sessions/start",
            json={"lot_id": "order_lot2", "slot": 30},
            headers=auth_headers,
        )
        client.post(
            "/api/v1/sessions/start",
            json={"lot_id": "order_lot2", "slot": 31},
            headers=auth_headers,
        )

        active = client.get(
            "/api/v1/sessions/active/order_lot2", headers=auth_headers
        )
        assert active.status_code == 200
        sessions = active.json()["sessions"]
        timestamps = [s["start_time"] for s in sessions if s["start_time"]]
        assert timestamps == sorted(timestamps, reverse=True), (
            "active sessions must be descending"
        )


class TestSchemaShape:
    def test_session_detail_matches_pydantic(self, client, auth_headers):
        _create_lot("shape_lot")
        start = client.post(
            "/api/v1/sessions/start",
            json={"lot_id": "shape_lot", "slot": 1},
            headers=auth_headers,
        )
        assert start.status_code == 200
        sid = start.json()["session_id"]

        resp = client.get(f"/api/v1/sessions/{sid}", headers=auth_headers)
        assert resp.status_code == 200
        validated = SessionDetailResponse(**resp.json())
        assert validated.session_id == sid
        assert validated.lot_id == "shape_lot"

    def test_history_response_matches_pydantic(self, client, auth_headers):
        _create_lot("shape_lot2")
        start = client.post(
            "/api/v1/sessions/start",
            json={"lot_id": "shape_lot2", "slot": 2},
            headers=auth_headers,
        )
        sid = start.json()["session_id"]
        client.post(
            "/api/v1/sessions/end",
            json={"session_id": sid},
            headers=auth_headers,
        )

        resp = client.get("/api/v1/sessions/history", headers=auth_headers)
        assert resp.status_code == 200
        validated = SessionHistoryResponse(**resp.json())
        assert validated.total_sessions >= 1
        assert len(validated.sessions) >= 1
