import time
import pytest
from conftest import BASE_URL, login


def test_dashboard_shows_stats(page):
    login(page, "nav@test.io", "NavPass123!")
    deadline = time.time() + 15
    while time.time() < deadline:
        h1 = page.evaluate("document.querySelector('h1')?.textContent || ''")
        if "Dashboard" in h1:
            break
        page.wait_for_timeout(500)
    h1 = page.evaluate("document.querySelector('h1')?.textContent || ''")
    assert "Dashboard" in h1, f"expected 'Dashboard', got '{h1}'"


def _nav_to(page, page_name):
    page.evaluate(f"window.location.hash = '#/app/{page_name}'")
    page.wait_for_timeout(1500)


def test_navigate_lots(page):
    login(page, "nav@test.io", "NavPass123!")
    _nav_to(page, "lots")
    h1 = page.evaluate("document.querySelector('h1')?.textContent || ''")
    assert h1 == "Parking Lots", f"expected 'Parking Lots', got '{h1}'"


def test_navigate_analytics(page):
    login(page, "nav@test.io", "NavPass123!")
    _nav_to(page, "analytics")
    h1 = page.evaluate("document.querySelector('h1')?.textContent || ''")
    assert h1 == "Analytics", f"expected 'Analytics', got '{h1}'"


def test_navigate_map(page):
    login(page, "nav@test.io", "NavPass123!")
    _nav_to(page, "map")
    h1 = page.evaluate("document.querySelector('h1')?.textContent || ''")
    assert h1 == "Map", f"expected 'Map', got '{h1}'"


def test_navigate_settings(page):
    login(page, "nav@test.io", "NavPass123!")
    _nav_to(page, "settings")
    h1 = page.evaluate("document.querySelector('h1')?.textContent || ''")
    assert h1 == "Settings", f"expected 'Settings', got '{h1}'"


def test_navigate_alerts(page):
    login(page, "nav@test.io", "NavPass123!")
    _nav_to(page, "alerts")
    h1 = page.evaluate("document.querySelector('h1')?.textContent || ''")
    assert h1 == "Alerts", f"expected 'Alerts', got '{h1}'"
