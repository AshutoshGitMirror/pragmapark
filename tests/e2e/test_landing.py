"""Playwright E2E: Anonymous visitor — SPA portal selector (P0)."""

from conftest import BASE_URL


def test_landing_page_loads(page):
    """Validate the SPA entry point exposes both admin and driver portals."""
    page.goto(f"{BASE_URL}/#/")
    page.wait_for_timeout(2000)

    body = page.evaluate("document.body.innerText || ''")
    body_upper = body.upper()
    assert "Pragma" in body, f"Portal selector missing brand: {body[:200]}"
    assert "SMART PARKING ECOSYSTEM" in body_upper, f"Portal selector missing subtitle: {body[:200]}"
    assert "Driver Portal" in body, f"Driver portal missing: {body[:200]}"
    assert "Operator & Admin Portal" in body, f"Admin portal missing: {body[:200]}"
    assert "AI · MARL · BLOCKCHAIN · CITY-SCALE" in body_upper, f"Architecture tagline missing: {body[:200]}"
