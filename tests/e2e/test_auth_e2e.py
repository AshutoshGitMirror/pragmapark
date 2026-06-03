import time
import pytest
from conftest import BASE_URL, login_via_form


def test_login_shows_dashboard(page):
    login_via_form(page, "e2e@test.io", "E2ePass123!")
    assert "/dashboard" in page.url, f"Expected /dashboard in URL, got {page.url}"


def test_logout_returns_to_login(page):
    login_via_form(page, "e2e@test.io", "E2ePass123!")
    page.evaluate("document.getElementById('logout-btn').click()")
    page.wait_for_timeout(1000)
    email_input = page.evaluate("document.getElementById('login-email') !== null")
    assert email_input, "login-email input should be visible after logout"


@pytest.mark.skip(reason="Register form not available in React admin SPA")
def test_register_new_user(page):
    pass


def test_invalid_login_shows_error(page):
    page.goto(f"{BASE_URL}/#/login")
    page.wait_for_timeout(500)
    page.fill("#login-email", "wrong@test.io")
    page.fill("#login-password", "wrong")
    page.click("#login-submit-btn")
    page.wait_for_timeout(2000)
    error_el = page.evaluate("document.getElementById('login-error')")
    assert error_el is not None, "login-error should exist"
    error_text = page.evaluate("document.getElementById('login-error').textContent")
    assert len(error_text) > 0, f"login-error should have text, got '{error_text}'"
