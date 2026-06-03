import time
import pytest
from conftest import BASE_URL, login_via_form


def _get_text(page, element_id):
    return page.evaluate(f"document.getElementById('{element_id}').textContent")


def _is_hidden(page, element_id):
    return page.evaluate(f"document.getElementById('{element_id}').classList.contains('hidden')")


def test_login_shows_dashboard(page):
    login_via_form(page, "e2e@test.io", "E2ePass123!")
    assert not _is_hidden(page, "app-view"), "app-view should be visible after login"


def test_logout_returns_to_login(page):
    login_via_form(page, "e2e@test.io", "E2ePass123!")
    page.evaluate("document.getElementById('logout-btn').click()")
    page.wait_for_timeout(1000)
    assert not _is_hidden(page, "login-view"), "login-view should be visible after logout"
    assert _is_hidden(page, "app-view"), "app-view should be hidden after logout"


def _goto_spa(page):
    """Navigate to the SPA directly, bypassing the loading page."""
    page.goto(f"{BASE_URL}/app/")


def test_register_new_user(page):
    ts = time.time_ns()
    email = f"new{ts}@test.io"
    _goto_spa(page)
    page.fill("#login-email", email)
    page.fill("#login-password", "NewPass123!")
    page.click("#register-btn")
    page.wait_for_timeout(3000)
    # Register creates driver role → redirects to /app/driver
    assert "/app/driver" in page.url, f"Expected redirect to /app/driver, got {page.url}"
    assert not _is_hidden(page, "screen-find"), "driver find screen should be visible"


def test_invalid_login_shows_error(page):
    _goto_spa(page)
    page.fill("#login-email", "wrong@test.io")
    page.fill("#login-password", "wrong")
    page.click("#login-submit-btn")
    page.wait_for_timeout(1000)
    assert not _is_hidden(page, "login-error"), "login-error should be visible"
    error_text = _get_text(page, "login-error")
    assert len(error_text) > 0, f"login-error should have text, got '{error_text}'"
