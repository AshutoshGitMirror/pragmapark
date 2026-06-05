"""Playwright E2E: Infrastructure health check (P1)."""

import json
import urllib.request
import urllib.error
from conftest import BASE_URL


def test_health_endpoint():
    """GET /api/v1/health returns 200 with expected fields."""
    try:
        resp = urllib.request.urlopen(f"{BASE_URL}/api/v1/health", timeout=10)
        assert resp.status == 200, f"Health endpoint returned {resp.status}"
        body = json.loads(resp.read())
        # Should have at least status field
        assert "status" in body, f"Health response missing 'status': {body}"
        # Should indicate ok
        assert body["status"] == "ok", f"Health status not ok: {body}"
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        raise AssertionError(f"GET /api/v1/health -> {e.code}: {body}")
    except urllib.error.URLError as e:
        raise AssertionError(f"Health endpoint unreachable: {e}")
