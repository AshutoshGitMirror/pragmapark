import pytest
from fastapi import HTTPException
from src.api.utils import RateLimiter, require_role, require_admin, driver_id


class TestRateLimiter:
    def test_accepts_first_request(self):
        limiter = RateLimiter(max_calls=3, window=60.0)
        assert limiter.check("key1") is True

    def test_exceeds_limit(self):
        limiter = RateLimiter(max_calls=2, window=60.0)
        assert limiter.check("key1") is True
        assert limiter.check("key1") is True
        assert limiter.check("key1") is False

    def test_different_keys_independent(self):
        limiter = RateLimiter(max_calls=1, window=60.0)
        assert limiter.check("a") is True
        assert limiter.check("b") is True
        assert limiter.check("a") is False

    def test_cleanup_does_not_break_checking(self):
        limiter = RateLimiter(max_calls=2, window=60.0, cleanup_interval=0.0)
        assert limiter.check("x") is True
        assert limiter.check("x") is True


class TestRequireRole:
    def test_allows_matching_role(self):
        require_role({"role": "admin"}, {"admin"})

    def test_allows_city_planner(self):
        require_role({"role": "city_planner"})

    def test_raises_for_driver(self):
        with pytest.raises(HTTPException) as exc:
            require_role({"role": "driver"})
        assert exc.value.status_code == 403

    def test_custom_allowed_set(self):
        require_role({"role": "sensor"}, {"admin", "sensor"})

    def test_raises_for_role_not_in_custom_set(self):
        with pytest.raises(HTTPException):
            require_role({"role": "driver"}, {"admin"})

    def test_default_allowed_is_admin_roles(self):
        require_role({"role": "city_planner"})


class TestRequireAdmin:
    def test_allows_admin(self):
        require_admin({"role": "admin"})

    def test_allows_city_planner(self):
        require_admin({"role": "city_planner"})

    def test_raises_for_driver(self):
        with pytest.raises(HTTPException) as exc:
            require_admin({"role": "driver"})
        assert exc.value.status_code == 403

    def test_raises_for_missing_role(self):
        with pytest.raises(HTTPException):
            require_admin({})


class TestDriverId:
    def test_returns_sub_when_present(self):
        assert (
            driver_id({"sub": "user@test.io", "email": "other@test.io"})
            == "user@test.io"
        )

    def test_falls_back_to_email(self):
        assert driver_id({"email": "user@test.io"}) == "user@test.io"

    def test_falls_back_to_unknown(self):
        assert driver_id({}) == "unknown"
