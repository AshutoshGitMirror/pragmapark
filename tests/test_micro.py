import time
import threading
import pytest
import numpy as np
from datetime import datetime, timezone, timedelta

from src.micro.state_engine import SlotStateEngine, RESERVATION_TTL_S, CLEANUP_INTERVAL_S
from src.micro.pricing import SlotPricing, DELTA_MAX_RATIO
from src.micro.predictor import SlotPredictor
from src.micro.models import SlotState, SlotType
from src.api.database import MicroSlot


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_slot(slot_id=1, slot_type: str = "regular", modifier_score=0.0, slot_index=1):
    type_map = {"regular": SlotType.REGULAR, "ev": SlotType.EV,
                "handicap": SlotType.HANDICAP, "covered": SlotType.COVERED,
                "premium": SlotType.PREMIUM}
    return MicroSlot(
        id=slot_id, lot_id="lot_1", slot_index=slot_index,
        micro_zone_id=1, row_label="A", position=slot_index,
        slot_type=type_map.get(slot_type, SlotType.REGULAR),
        base_modifier_score=modifier_score,
    )


@pytest.fixture(autouse=True)
def _reset_state_engine():
    from src.micro.state_engine import slot_state_engine
    slot_state_engine._states.clear()
    slot_state_engine._timestamps.clear()
    slot_state_engine._reservations.clear()
    slot_state_engine._reservation_expiry.clear()
    slot_state_engine._last_cleanup = 0.0


# ===================================================================
#  StateEngine unit tests
# ===================================================================

class TestSlotStateEngine:

    def test_initial_state_defaults_to_available(self):
        engine = SlotStateEngine()
        assert engine.get_state(1) == SlotState.AVAILABLE

    def test_set_state_transitions(self):
        engine = SlotStateEngine()
        engine.set_state(1, SlotState.OCCUPIED)
        assert engine.get_state(1) == SlotState.OCCUPIED
        engine.set_state(1, SlotState.AVAILABLE)
        assert engine.get_state(1) == SlotState.AVAILABLE
        engine.set_state(1, SlotState.MAINTENANCE)
        assert engine.get_state(1) == SlotState.MAINTENANCE

    def test_set_state_available_clears_reservation(self):
        engine = SlotStateEngine()
        engine.reserve(1, "driver_1")
        engine.set_state(1, SlotState.AVAILABLE)
        assert engine.is_reserved_by(1, "driver_1") is False

    def test_get_state_returns_correct_state(self):
        engine = SlotStateEngine()
        engine.set_state(1, SlotState.MAINTENANCE)
        assert engine.get_state(1) == SlotState.MAINTENANCE

    def test_reserve_succeeds_for_available_slot(self):
        engine = SlotStateEngine()
        assert engine.reserve(1, "driver_1") is True
        assert engine.get_state(1) == SlotState.RESERVED

    def test_reserve_fails_for_occupied_slot(self):
        engine = SlotStateEngine()
        engine.set_state(1, SlotState.OCCUPIED)
        assert engine.reserve(1, "driver_2") is False

    def test_reserve_fails_for_maintenance_slot(self):
        engine = SlotStateEngine()
        engine.set_state(1, SlotState.MAINTENANCE)
        assert engine.reserve(1, "driver_3") is False

    def test_reserve_rejects_expired_reservation(self):
        engine = SlotStateEngine()
        engine.reserve(1, "driver_1", ttl_s=0)
        time.sleep(0.01)
        assert engine.reserve(1, "driver_2", ttl_s=300) is True
        assert engine.get_state(1) == SlotState.RESERVED

    def test_release_succeeds_with_correct_driver_id(self):
        engine = SlotStateEngine()
        engine.reserve(1, "driver_1")
        assert engine.release(1, "driver_1") is True
        assert engine.is_reserved_by(1, "driver_1") is False
        assert engine.get_state(1) == SlotState.AVAILABLE

    def test_release_fails_with_wrong_driver_id(self):
        engine = SlotStateEngine()
        engine.reserve(1, "driver_1")
        assert engine.release(1, "driver_wrong") is False
        assert engine.get_state(1) == SlotState.RESERVED

    def test_is_reserved_by_returns_correctly(self):
        engine = SlotStateEngine()
        engine.reserve(1, "driver_1")
        assert engine.is_reserved_by(1, "driver_1") is True
        assert engine.is_reserved_by(1, "driver_2") is False
        assert engine.is_reserved_by(99, "driver_1") is False

    def test_bulk_set_occupied_marks_correct_slots(self):
        engine = SlotStateEngine()
        slots = [make_slot(i) for i in range(1, 5)]
        engine.bulk_set_occupied({1, 3}, slots)
        assert engine.get_state(1) == SlotState.OCCUPIED
        assert engine.get_state(2) == SlotState.AVAILABLE
        assert engine.get_state(3) == SlotState.OCCUPIED
        assert engine.get_state(4) == SlotState.AVAILABLE

    def test_bulk_set_occupied_preserves_reserved_slots(self):
        engine = SlotStateEngine()
        slots = [make_slot(1)]
        engine.reserve(1, "driver_1")
        engine.bulk_set_occupied(set(), slots)
        assert engine.get_state(1) == SlotState.RESERVED

    def test_occupancies_returns_correct_counts(self):
        engine = SlotStateEngine()
        slots = [make_slot(i) for i in range(1, 4)]
        engine.set_state(1, SlotState.OCCUPIED)
        engine.reserve(2, "driver_1")
        occ = engine.occupancies("lot_1", slots)
        assert occ["total_slots"] == 3
        assert occ["available_slots"] == 1
        assert occ["reserved_slots"] == 1
        assert occ["occupied_slots"] == 1
        assert occ["occupancy_rate"] == round(1 / 3, 4)

    def test_occupancies_with_empty_slots(self):
        engine = SlotStateEngine()
        occ = engine.occupancies("lot_1", [])
        assert occ["total_slots"] == 0
        assert occ["occupied_slots"] == 0
        assert occ["occupancy_rate"] == 0.0

    def test_concurrent_reservations_no_data_corruption(self):
        engine = SlotStateEngine()
        results = []

        def try_reserve(driver_id):
            ok = engine.reserve(1, driver_id)
            results.append((driver_id, ok))

        threads = [threading.Thread(target=try_reserve, args=(f"driver_{i}",)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        # Only first reserve succeeds; re-reserving RESERVED slots is rejected
        assert engine.get_state(1) == SlotState.RESERVED
        assert len(engine._reservations) == 1

    def test_reservation_expires_after_custom_ttl(self):
        engine = SlotStateEngine()
        engine.reserve(1, "driver_1", ttl_s=0)
        time.sleep(0.01)
        engine.cleanup_expired(force=True)
        assert engine.get_state(1) == SlotState.AVAILABLE

    def test_release_unreserved_slot_fails(self):
        engine = SlotStateEngine()
        assert engine.release(1, "driver_1") is False

    def test_reserve_on_already_reserved_by_self_fails(self):
        engine = SlotStateEngine()
        engine.reserve(1, "driver_1")
        assert engine.reserve(1, "driver_1") is False


# ===================================================================
#  Pricing unit tests
# ===================================================================

class TestSlotPricing:

    def test_compute_modifiers_returns_correct_length(self):
        pricing = SlotPricing()
        slots = [make_slot(i) for i in range(1, 6)]
        mods = pricing.compute_modifiers(slots)
        assert len(mods) == 5

    def test_compute_modifiers_empty(self):
        assert SlotPricing().compute_modifiers([]) == []

    def test_modifier_mean_approx_zero(self):
        pricing = SlotPricing()
        slots = [make_slot(i, modifier_score=i * 0.1) for i in range(1, 21)]
        mods = pricing.compute_modifiers(slots)
        assert abs(np.mean(mods)) < 1e-6

    def test_modifiers_within_bounds(self):
        pricing = SlotPricing()
        slots = [make_slot(i, modifier_score=i * 0.1) for i in range(1, 21)]
        mods = pricing.compute_modifiers(slots)
        assert all(-DELTA_MAX_RATIO - 1e-9 <= m <= DELTA_MAX_RATIO + 1e-9 for m in mods)

    def test_slot_price_with_modifiers(self):
        pricing = SlotPricing()
        slot = make_slot(1)
        mods = pricing.compute_modifiers([slot])
        price = pricing.slot_price(slot, 10.0, mods)
        assert price == 10.0

    def test_slot_price_without_modifiers_uses_current_modifier(self):
        pricing = SlotPricing()
        slot = make_slot(1)
        slot.current_modifier = 0.15
        assert pricing.slot_price(slot, 10.0) == 11.50

    def test_slot_price_without_modifiers_defaults_to_zero(self):
        pricing = SlotPricing()
        slot = make_slot(1, modifier_score=0.0)
        slot.current_modifier = 0.0
        assert pricing.slot_price(slot, 10.0) == 10.0

    def test_ev_slot_modifier_higher_than_regular(self):
        pricing = SlotPricing()
        ev_slots = [make_slot(1, "ev"), make_slot(2, "regular")]
        reg_slots = [make_slot(1, "regular"), make_slot(2, "regular")]
        ev_mods = pricing.compute_modifiers(ev_slots)
        reg_mods = pricing.compute_modifiers(reg_slots)
        assert ev_mods[0] > reg_mods[0]

    def test_handicap_slot_modifier_lower_than_regular(self):
        pricing = SlotPricing()
        hc_slots = [make_slot(1, "handicap"), make_slot(2, "regular")]
        reg_slots = [make_slot(1, "regular"), make_slot(2, "regular")]
        hc_mods = pricing.compute_modifiers(hc_slots)
        reg_mods = pricing.compute_modifiers(reg_slots)
        assert hc_mods[0] < reg_mods[0]

    def test_slot_price_zero_base(self):
        pricing = SlotPricing()
        assert pricing.slot_price(make_slot(1), 0.0, [0.0]) == 0.0

    def test_slot_price_large_base(self):
        pricing = SlotPricing()
        assert pricing.slot_price(make_slot(1), 100.0, [0.0]) == 100.0

    def test_slot_price_positive_modifier_increases_price(self):
        pricing = SlotPricing()
        assert pricing.slot_price(make_slot(1), 10.0, [0.10]) == 11.00

    def test_slot_price_negative_modifier_decreases_price(self):
        pricing = SlotPricing()
        assert pricing.slot_price(make_slot(1), 10.0, [-0.10]) == 9.00

# ===================================================================
#  Predictor unit tests
# ===================================================================

class TestSlotPredictor:

    def test_predict_zero_for_occupied(self):
        from src.micro.state_engine import slot_state_engine as e
        e.set_state(1, SlotState.OCCUPIED)
        assert SlotPredictor().predict(1) == 0.0

    def test_predict_zero_for_maintenance(self):
        from src.micro.state_engine import slot_state_engine as e
        e.set_state(1, SlotState.MAINTENANCE)
        assert SlotPredictor().predict(1) == 0.0

    def test_predict_positive_for_available(self):
        from src.micro.state_engine import slot_state_engine as e
        e.set_state(1, SlotState.AVAILABLE)
        prob = SlotPredictor().predict(1)
        assert 0.0 < prob <= 1.0

    def test_predict_returns_value_for_reserved(self):
        from src.micro.state_engine import slot_state_engine as e
        e.reserve(1, "driver_1", ttl_s=300)
        prob = SlotPredictor().predict(1)
        assert 0.0 <= prob <= 1.0

    def test_predict_far_future_returns_baseline(self):
        from src.micro.state_engine import slot_state_engine as e
        e.set_state(1, SlotState.AVAILABLE)
        future = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
        assert SlotPredictor().predict(1, future) == 0.5

    def test_predict_near_future_decays(self):
        from src.micro.state_engine import slot_state_engine as e
        e.set_state(1, SlotState.AVAILABLE)
        near = (datetime.now(timezone.utc) + timedelta(seconds=60)).isoformat()
        prob = SlotPredictor().predict(1, near)
        assert 0.0 < prob < 1.0

    def test_predict_zone_returns_dict(self):
        from src.micro.state_engine import slot_state_engine as e
        e.set_state(1, SlotState.AVAILABLE)
        e.set_state(2, SlotState.OCCUPIED)
        result = SlotPredictor().predict_zone([1, 2])
        assert isinstance(result, dict)
        assert len(result) == 2
        assert result[2] == 0.0

    def test_best_slots_returns_ranked_results(self):
        from src.micro.state_engine import slot_state_engine as e
        slots = [make_slot(i) for i in range(1, 6)]
        for s in slots:
            e.set_state(s.id, SlotState.AVAILABLE)
        results = SlotPredictor().best_slots(slots, 10.0, top_k=3)
        assert len(results) == 3
        scores = [r["score"] for r in results]
        assert all(scores[i] >= scores[i + 1] for i in range(len(scores) - 1))

    def test_best_slots_respects_top_k(self):
        from src.micro.state_engine import slot_state_engine as e
        slots = [make_slot(i) for i in range(1, 11)]
        for s in slots:
            e.set_state(s.id, SlotState.AVAILABLE)
        assert len(SlotPredictor().best_slots(slots, 10.0, top_k=5)) == 5
        assert len(SlotPredictor().best_slots(slots, 10.0, top_k=1)) == 1

    def test_best_slots_with_target_time(self):
        from src.micro.state_engine import slot_state_engine as e
        slots = [make_slot(i) for i in range(1, 4)]
        for s in slots:
            e.set_state(s.id, SlotState.AVAILABLE)
        future = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat()
        results = SlotPredictor().best_slots(slots, 10.0, top_k=3, target_time=future)
        assert len(results) == 3

    def test_best_slots_includes_required_fields(self):
        from src.micro.state_engine import slot_state_engine as e
        slots = [make_slot(1)]
        e.set_state(1, SlotState.AVAILABLE)
        result = SlotPredictor().best_slots(slots, 10.0, top_k=1)[0]
        assert "slot_id" in result
        assert "slot_label" in result
        assert "probability" in result
        assert "price" in result
        assert "score" in result

    def test_slot_state_log_model_exists(self):
        from src.api.database import SlotStateLog
        entry = SlotStateLog(
            slot_id=1, lot_id="lot_1",
            previous_state="available", new_state="occupied",
        )
        assert entry.slot_id == 1
        assert entry.lot_id == "lot_1"
        assert entry.previous_state == "available"
        assert entry.new_state == "occupied"

    def test_predictor_uses_historical_data(self):
        from src.micro.state_engine import slot_state_engine as e
        from src.micro.predictor import slot_predictor
        e.set_state(1, SlotState.AVAILABLE)
        p1 = slot_predictor.predict(1)
        e.set_state(1, SlotState.OCCUPIED)
        p2 = slot_predictor.predict(1)
        e.set_state(1, SlotState.AVAILABLE)
        p3 = slot_predictor.predict(1)
        assert p1 > 0.0
        assert p2 == 0.0
        assert 0.0 <= p3 <= 1.0


# ===================================================================
#  API integration tests
# ===================================================================

class TestMicroAPI:

    @pytest.fixture
    def seeded_lot(self, client, admin_headers):
        client.post("/api/v1/lots", json={
            "lot_id": "micro_test_lot",
            "name": "Micro Test Lot",
            "total_slots": 50,
            "base_price": 10.0,
        }, headers=admin_headers)
        client.post("/api/v1/micro/lots/micro_test_lot/slots/seed", headers=admin_headers)
        return "micro_test_lot"

    @pytest.fixture
    def alt_auth_headers(self, client):
        resp = client.post("/api/v1/auth/register", json={
            "email": "alt_driver_micro@pragma.io",
            "password": "AltPass123!",
            "full_name": "Alt Driver Micro",
        })
        assert resp.status_code == 200, resp.text
        token = resp.json().get("access_token", "")
        return {"Authorization": f"Bearer {token}"}

    def test_get_slots_returns_200_for_valid_lot(self, client, admin_headers, seeded_lot):
        resp = client.get(f"/api/v1/micro/lots/{seeded_lot}/slots", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["lot_id"] == seeded_lot
        assert "slots" in data
        assert data["total_slots"] > 0

    def test_get_slots_returns_404_for_nonexistent_lot(self, client, admin_headers):
        resp = client.get("/api/v1/micro/lots/nonexistent/slots", headers=admin_headers)
        assert resp.status_code == 404

    def test_get_slots_public(self, client, seeded_lot):
        resp = client.get(f"/api/v1/micro/lots/{seeded_lot}/slots")
        assert resp.status_code == 200

    def test_slot_probability_returns_valid(self, client, admin_headers, seeded_lot):
        resp = client.get(
            f"/api/v1/micro/lots/{seeded_lot}/slots/1/probability",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert 0.0 <= data["probability"] <= 1.0
        assert "current_state" in data
        assert data["slot_id"] is not None

    def test_slot_probability_returns_404_for_bad_slot(self, client, admin_headers, seeded_lot):
        resp = client.get(
            f"/api/v1/micro/lots/{seeded_lot}/slots/99999/probability",
            headers=admin_headers,
        )
        assert resp.status_code == 404

    def test_list_zones_returns_list(self, client, admin_headers, seeded_lot):
        resp = client.get(f"/api/v1/micro/lots/{seeded_lot}/zones", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_list_zones_requires_auth(self, client):
        resp = client.get("/api/v1/micro/lots/micro_test_lot/zones")
        assert resp.status_code in (401, 403)

    def test_reserve_succeeds(self, client, auth_headers, admin_headers, seeded_lot):
        resp = client.post("/api/v1/micro/reserve", json={
            "lot_id": seeded_lot,
            "slot_index": 2,
        }, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "active"
        assert data["reservation_id"] > 0

    def test_reserve_fails_for_occupied_slot(self, client, auth_headers, admin_headers, seeded_lot):
        from src.micro.state_engine import slot_state_engine
        slot_state_engine.set_state(3, SlotState.OCCUPIED)
        resp = client.post("/api/v1/micro/reserve", json={
            "lot_id": seeded_lot,
            "slot_index": 3,
        }, headers=auth_headers)
        assert resp.status_code == 409

    def test_reserve_requires_auth(self, client, admin_headers, seeded_lot):
        client.cookies.clear()
        resp = client.post("/api/v1/micro/reserve", json={
            "lot_id": seeded_lot,
            "slot_index": 4,
        })
        assert resp.status_code in (401, 403)

    def test_release_succeeds(self, client, auth_headers, admin_headers, seeded_lot):
        r = client.post("/api/v1/micro/reserve", json={
            "lot_id": seeded_lot,
            "slot_index": 5,
        }, headers=auth_headers)
        assert r.status_code == 200
        res_id = r.json()["reservation_id"]
        slot_id = r.json()["slot_id"]
        resp = client.post("/api/v1/micro/release", json={
            "slot_id": slot_id,
            "reservation_id": res_id,
        }, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "released"

    def test_release_requires_auth(self, client, admin_headers, seeded_lot):
        client.cookies.clear()
        resp = client.post("/api/v1/micro/release", json={
            "slot_id": 1,
            "reservation_id": 1,
        })
        assert resp.status_code in (401, 403)

    def test_seed_slots_requires_admin(self, client, admin_headers, auth_headers):
        client.post("/api/v1/lots", json={
            "lot_id": "micro_test_lot_admin",
            "name": "Micro Test Admin",
            "total_slots": 10,
            "base_price": 10.0,
        }, headers=admin_headers)
        resp = client.post(
            "/api/v1/micro/lots/micro_test_lot_admin/slots/seed",
            headers=auth_headers,
        )
        assert resp.status_code == 403

    def test_release_fails_for_nonexistent_reservation(self, client, auth_headers, admin_headers, seeded_lot):
        resp = client.post("/api/v1/micro/release", json={
            "slot_id": 999,
            "reservation_id": 99999,
        }, headers=auth_headers)
        assert resp.status_code == 404

    def test_reserve_release_cycle_full(self, client, auth_headers, admin_headers, seeded_lot):
        """reserve -> release -> re-reserve -> re-release (state engine resets)"""
        for i in range(3):
            r = client.post("/api/v1/micro/reserve", json={
                "lot_id": seeded_lot, "slot_index": 20 + i,
            }, headers=auth_headers)
            assert r.status_code == 200, f"Reserve {i} failed: {r.text}"
            slot_id = r.json()["slot_id"]
            res_id = r.json()["reservation_id"]
            rel = client.post("/api/v1/micro/release", json={
                "slot_id": slot_id, "reservation_id": res_id,
            }, headers=auth_headers)
            assert rel.status_code == 200, f"Release {i} failed: {rel.text}"

    def test_reserve_with_target_time(self, client, auth_headers, admin_headers, seeded_lot):
        from datetime import datetime, timezone, timedelta
        target = (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()
        resp = client.post("/api/v1/micro/reserve", json={
            "lot_id": seeded_lot, "slot_index": 7, "target_time": target,
        }, headers=auth_headers)
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["probability"] >= 0

    def test_release_wrong_driver_fails(self, client, auth_headers, alt_auth_headers, admin_headers, seeded_lot):
        """driver1 reserves; driver2 tries to release -> fails"""
        r = client.post("/api/v1/micro/reserve", json={
            "lot_id": seeded_lot, "slot_index": 8,
        }, headers=auth_headers)
        assert r.status_code == 200, r.text
        slot_id = r.json()["slot_id"]
        res_id = r.json()["reservation_id"]
        # Clear cookies so get_current_user picks alt_auth_headers (driver2) not cookie (driver1)
        client.cookies.clear()
        rel = client.post("/api/v1/micro/release", json={
            "slot_id": slot_id, "reservation_id": res_id,
        }, headers=alt_auth_headers)
        assert rel.status_code == 404

    def test_release_double_fails(self, client, auth_headers, admin_headers, seeded_lot):
        r = client.post("/api/v1/micro/reserve", json={
            "lot_id": seeded_lot, "slot_index": 9,
        }, headers=auth_headers)
        assert r.status_code == 200, r.text
        slot_id = r.json()["slot_id"]
        res_id = r.json()["reservation_id"]
        r1 = client.post("/api/v1/micro/release", json={
            "slot_id": slot_id, "reservation_id": res_id,
        }, headers=auth_headers)
        assert r1.status_code == 200
        r2 = client.post("/api/v1/micro/release", json={
            "slot_id": slot_id, "reservation_id": res_id,
        }, headers=auth_headers)
        assert r2.status_code == 400

    def test_slot_list_includes_pricing_and_type(self, client, admin_headers, seeded_lot):
        resp = client.get(f"/api/v1/micro/lots/{seeded_lot}/slots", headers=admin_headers)
        assert resp.status_code == 200
        slots = resp.json()["slots"]
        assert len(slots) > 0
        s = slots[0]
        assert "slot_index" in s
        assert "row_label" in s
        assert "position" in s
        assert "slot_type" in s
        assert "current_price" in s
        assert "probability" in s
        assert "probability_adjusted_price" in s
        assert "base_modifier_score" in s
        assert s["state"] in ("available", "occupied", "reserved", "maintenance", "prebooked")

    def test_reserve_updates_slot_state_in_list(self, client, auth_headers, admin_headers, seeded_lot):
        r = client.post("/api/v1/micro/reserve", json={
            "lot_id": seeded_lot, "slot_index": 10,
        }, headers=auth_headers)
        assert r.status_code == 200, r.text
        slot_id = r.json()["slot_id"]
        resp = client.get(f"/api/v1/micro/lots/{seeded_lot}/slots", headers=admin_headers)
        assert resp.status_code == 200
        slots = resp.json()["slots"]
        for s in slots:
            if s["id"] == slot_id:
                assert s["state"] == "reserved"
                break
        else:
            pytest.fail("Reserved slot not found in slot list")

    def test_slot_list_zones_returns_occupancy_data(self, client, admin_headers, seeded_lot):
        resp = client.get(f"/api/v1/micro/lots/{seeded_lot}/zones", headers=admin_headers)
        assert resp.status_code == 200
        zones = resp.json()
        assert isinstance(zones, list)
        for z in zones:
            assert "name" in z
            assert "slot_count" in z
            assert "available" in z
            assert "occupancy_rate" in z
            assert 0.0 <= z["occupancy_rate"] <= 1.0

    def test_slot_list_pagination(self, client, admin_headers, seeded_lot):
        r1 = client.get(f"/api/v1/micro/lots/{seeded_lot}/slots?offset=0&limit=5", headers=admin_headers)
        assert r1.status_code == 200
        assert len(r1.json()["slots"]) <= 5
        r2 = client.get(f"/api/v1/micro/lots/{seeded_lot}/slots?offset=5&limit=5", headers=admin_headers)
        assert r2.status_code == 200
        if len(r1.json()["slots"]) == 5 and len(r2.json()["slots"]) > 0:
            ids1 = [s["slot_index"] for s in r1.json()["slots"]]
            ids2 = [s["slot_index"] for s in r2.json()["slots"]]
            assert ids1 != ids2, "Paginated results should differ"
