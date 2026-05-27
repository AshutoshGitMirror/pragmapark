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


def test_register_new_user(page):
    ts = time.time_ns()
    email = f"new{ts}@test.io"
    page.goto(BASE_URL)
    page.fill("#login-email", email)
    page.fill("#login-password", "NewPass123!")
    page.click("#register-btn")
    page.wait_for_timeout(3000)
    assert not _is_hidden(page, "app-view"), f"app-view should be visible after register"
    name_text = _get_text(page, "user-name")
    assert email.split("@")[0] in name_text, f"Expected {email.split('@')[0]} in user-name, got {name_text}"


def test_invalid_login_shows_error(page):
    page.goto(BASE_URL)
    page.fill("#login-email", "wrong@test.io")
    page.fill("#login-password", "wrong")
    page.click("#login-submit-btn")
    page.wait_for_timeout(1000)
    assert not _is_hidden(page, "login-error"), "login-error should be visible"
    error_text = _get_text(page, "login-error")
    assert len(error_text) > 0, f"login-error should have text, got '{error_text}'"
