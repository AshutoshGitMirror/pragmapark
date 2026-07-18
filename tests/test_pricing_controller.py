import os
import tempfile

from src.pipeline.pricing import PricingController


class TestPricingController:
    def test_agent_available_initial(self):
        pc = PricingController()
        assert pc.agent_available is False

    def test_ensure_does_not_crash(self, monkeypatch):
        monkeypatch.setattr(
            "src.pipeline.pricing.AGENT_PATH", os.path.join(tempfile.gettempdir(), "nonexistent_agent.joblib")
        )
        pc = PricingController()
        pc.ensure()
        assert pc._loaded is True
        assert pc.agent is None

    def test_get_price_heuristic_fallback(self, monkeypatch):
        monkeypatch.setattr(
            "src.pipeline.pricing.AGENT_PATH", os.path.join(tempfile.gettempdir(), "nonexistent_agent.joblib")
        )
        pc = PricingController()
        new_price, multiplier = pc.get_price(0.5, 10.0, 50.0)
        assert 0.0 <= new_price <= 50.0
        assert isinstance(multiplier, float)

    def test_get_price_at_high_occupancy(self, monkeypatch):
        monkeypatch.setattr(
            "src.pipeline.pricing.AGENT_PATH", os.path.join(tempfile.gettempdir(), "nonexistent_agent.joblib")
        )
        pc = PricingController()
        new_price, multiplier = pc.get_price(0.9, 10.0, 50.0)
        assert new_price >= 10.0

    def test_get_price_at_low_occupancy(self, monkeypatch):
        monkeypatch.setattr(
            "src.pipeline.pricing.AGENT_PATH", os.path.join(tempfile.gettempdir(), "nonexistent_agent.joblib")
        )
        pc = PricingController()
        new_price, multiplier = pc.get_price(0.1, 10.0, 50.0)
        assert new_price >= 0.0

    def test_get_price_respects_price_cap(self, monkeypatch):
        monkeypatch.setattr(
            "src.pipeline.pricing.AGENT_PATH", os.path.join(tempfile.gettempdir(), "nonexistent_agent.joblib")
        )
        pc = PricingController()
        new_price, multiplier = pc.get_price(1.0, 100.0, 30.0)
        assert new_price <= 30.0

    def test_ensure_is_idempotent(self, monkeypatch):
        monkeypatch.setattr(
            "src.pipeline.pricing.AGENT_PATH", os.path.join(tempfile.gettempdir(), "nonexistent_agent.joblib")
        )
        pc = PricingController()
        pc.ensure()
        pc.ensure()
        assert pc._loaded is True
