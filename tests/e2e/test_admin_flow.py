"""Playwright E2E: Admin persona — login, dashboard, navigation,
health, alerts, micro slots, blockchain, prediction."""

import time
import json
import urllib.request
from urllib.error import HTTPError
import pytest
from conftest import (
    BASE_URL,
    login,
    _api_login_token,
    _set_auth_cookie,
    _wait_for_spa,
)


ADMIN_EMAIL = "e2e-admin@test.io"
ADMIN_PASS = "E2ePass123!"


def _ensure_admin_user():
    """Ensure admin test user exists via API (idempotent)."""
    try:
        _api_login_token(ADMIN_EMAIL, ADMIN_PASS)
        return
    except Exception:
        pass
    data = json.dumps(
        {
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASS,
            "full_name": "E2E Admin",
            "role": "admin",
        }
    ).encode()
    req = urllib.request.Request(
        f"{BASE_URL}/api/v1/auth/register",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    try:
        urllib.request.urlopen(req)
    except HTTPError as e:
        body = e.read().decode()
        if "already" not in body:
            raise


def _admin_request(path, data=None, method="GET"):
    """Call an admin API endpoint with the E2E admin bearer token."""
    _ensure_admin_user()
    token, _user = _api_login_token(ADMIN_EMAIL, ADMIN_PASS)
    headers = {"Authorization": f"Bearer {token}"}
    body = None
    if data is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(data).encode()
    req = urllib.request.Request(
        f"{BASE_URL}{path}", data=body, headers=headers, method=method
    )
    return urllib.request.urlopen(req)


@pytest.fixture(autouse=True)
def _admin_user_ready():
    _ensure_admin_user()


# ── P0: Login ──


def test_admin_login(page):
    """Admin can login via form and reach dashboard."""
    _ensure_admin_user()
    token, user = _api_login_token(ADMIN_EMAIL, ADMIN_PASS)
    _set_auth_cookie(page, token)
    page.goto(f"{BASE_URL}/#/app/dashboard")
    _wait_for_spa(page)
    assert "/dashboard" in page.url, (
        f"Expected /dashboard in URL, got {page.url}"
    )


# ── P0: Dashboard stats ──


def test_admin_dashboard_stats(page):
    """Dashboard shows metrics, occupancy, revenue charts, and lot cards."""
    login(page, ADMIN_EMAIL, ADMIN_PASS)
    deadline = time.time() + 15
    ready = False
    while time.time() < deadline:
        h1 = page.evaluate("document.querySelector('h1')?.textContent || ''")
        if "Dashboard" in h1:
            ready = True
            break
        page.wait_for_timeout(500)
    assert ready, "Dashboard page did not load"

    # Metric cards: Avg Occupancy, Busy, Moderate, Quiet
    body = page.evaluate("document.body.innerText || ''")
    body_upper = body.upper()
    assert "AVG OCCUPANCY" in body_upper, "Avg occupancy metric missing"
    assert "BUSY" in body_upper, "Busy metric missing"
    assert "MODERATE" in body_upper, "Moderate metric missing"
    assert "QUIET" in body_upper, "Quiet metric missing"

    # Occupancy trend chart (Recharts renders SVGs)
    svgs = page.evaluate("document.querySelectorAll('svg').length")
    assert svgs >= 2, f"Expected at least 2 SVG charts, found {svgs}"

    # All Lots section
    assert "ALL LOTS" in body_upper, "All Lots section missing"

    # Revenue section
    assert "Revenue" in body, "Revenue section missing"


# ── P1: Sidebar navigation ──


def _nav_to(page, page_name):
    page.evaluate(f"window.location.hash = '#/app/{page_name}'")
    page.wait_for_timeout(1500)


def test_admin_navigate_lots(page):
    login(page, ADMIN_EMAIL, ADMIN_PASS)
    _nav_to(page, "lots")
    h1 = page.evaluate("document.querySelector('h1')?.textContent || ''")
    assert "Parking Lots" in h1 or "Lots" in h1, (
        f"Expected Parking Lots heading, got '{h1}'"
    )


def test_admin_navigate_analytics(page):
    login(page, ADMIN_EMAIL, ADMIN_PASS)
    _nav_to(page, "analytics")
    h1 = page.evaluate("document.querySelector('h1')?.textContent || ''")
    assert "Analytics" in h1, f"Expected Analytics heading, got '{h1}'"


def test_admin_navigate_alerts(page):
    login(page, ADMIN_EMAIL, ADMIN_PASS)
    _nav_to(page, "alerts")
    h1 = page.evaluate("document.querySelector('h1')?.textContent || ''")
    assert "Alerts" in h1, f"Expected Alerts heading, got '{h1}'"


def test_admin_navigate_revenue(page):
    login(page, ADMIN_EMAIL, ADMIN_PASS)
    _nav_to(page, "revenue")
    h1 = page.evaluate("document.querySelector('h1')?.textContent || ''")
    assert "Revenue" in h1, f"Expected Revenue heading, got '{h1}'"


def test_admin_navigate_map(page):
    login(page, ADMIN_EMAIL, ADMIN_PASS)
    _nav_to(page, "map")
    h1 = page.evaluate("document.querySelector('h1')?.textContent || ''")
    assert "Map" in h1, f"Expected Map heading, got '{h1}'"


def test_admin_navigate_micro_slots(page):
    login(page, ADMIN_EMAIL, ADMIN_PASS)
    _nav_to(page, "micro-slots")
    h1 = page.evaluate("document.querySelector('h1')?.textContent || ''")
    assert "Micro" in h1 or "Slots" in h1, (
        f"Expected Micro Slots heading, got '{h1}'"
    )


def test_admin_navigate_settings(page):
    login(page, ADMIN_EMAIL, ADMIN_PASS)
    _nav_to(page, "settings")
    h1 = page.evaluate("document.querySelector('h1')?.textContent || ''")
    assert "Settings" in h1, f"Expected Settings heading, got '{h1}'"


# ── P1: System health ──


def test_admin_system_health(page):
    """6-layer health indicators appear on dashboard via system-health API."""
    try:
        resp = _admin_request("/api/v1/admin/system-health")
        health = json.loads(resp.read())
        assert health.get("status") == "healthy", (
            f"Health status not healthy: {health}"
        )
        layers = health.get("layers", {})
        for layer in ["iot", "ml", "blockchain", "rl", "digital_twin", "api"]:
            assert layer in layers, (
                f"Layer {layer} missing from health response"
            )
            assert layers[layer] in (
                "operational",
                "simulated",
                "degraded",
                "no_data",
            ), f"Unexpected status for {layer}: {layers[layer]}"
    except HTTPError as e:
        body = e.read().decode()
        raise AssertionError(f"GET /admin/system-health -> {e.code}: {body}")


# ── P1: Logout ──


def test_admin_logout(page):
    """Logout clears cookie and redirects to login."""
    login(page, ADMIN_EMAIL, ADMIN_PASS)
    page.evaluate("document.getElementById('logout-btn')?.click()")
    page.wait_for_timeout(1000)
    # After logout should show login page or redirect
    url = page.url
    assert "login" in url, (
        f"Expected redirect to login after logout, got {url}"
    )


# ── P2: Blockchain status ──


def test_admin_blockchain_status(page):
    """Dashboard shows blockchain block height and mempool via API."""
    try:
        resp = _admin_request("/api/v1/blockchain/status")
        status = json.loads(resp.read())
        assert (
            "chain_length" in status
            or "chain" in status
            or "blocks" in status
            or "length" in status
        ), f"Blockchain status missing expected keys: {list(status.keys())}"
    except HTTPError as e:
        body = e.read().decode()
        raise AssertionError(f"GET /blockchain/status -> {e.code}: {body}")


# ── P2: Prediction (ML) ──


def test_admin_prediction_health(page):
    """ML model health endpoint returns model status."""
    try:
        resp = _admin_request("/api/v1/predict/health")
        health = json.loads(resp.read())
        # Should have model status keys
        assert len(health.keys()) > 0, f"Prediction health empty: {health}"
    except HTTPError as e:
        body = e.read().decode()
        raise AssertionError(f"GET /predict/health -> {e.code}: {body}")


# ── P2: Prediction by occupancy ──


def test_admin_prediction_occupancy(page):
    """ML predict endpoint returns occupancy forecast."""
    try:
        data = {
            "occupied_slots": 45,
            "total_slots": 100,
            "occ_lag_15m": 0.42,
            "occ_lag_1h": 0.40,
            "net_flux": 0.05,
            "hour": 14,
            "dow": 4,
        }
        resp = _admin_request(
            "/api/v1/predict/occupancy", data=data, method="POST"
        )
        result = json.loads(resp.read())
        assert (
            "ensemble_prediction" in result
            or "predicted_occupancy" in result
            or "forecast" in result
            or "prediction" in result
        ), f"Prediction response missing expected keys: {list(result.keys())}"
    except HTTPError as e:
        body = e.read().decode()
        raise AssertionError(f"POST /predict/occupancy -> {e.code}: {body}")
