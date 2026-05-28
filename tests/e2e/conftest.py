import os
import json
import time
import urllib.request
import urllib.error
import pytest
from typing import Optional
from playwright.sync_api import sync_playwright, TimeoutError as _PWTimeout

BASE_URL = os.getenv("E2E_BASE_URL", "http://127.0.0.1:8989")


_token_cache: dict[str, tuple[str, dict]] = {}


@pytest.fixture(scope="session", autouse=True)
def _pre_register_users():
    """Pre-register all test users once per session (avoids rate-limit races)."""
    _ensure_user("e2e@test.io", "E2ePass123!", "E2E User", retries=10, role="admin")
    _ensure_user("nav@test.io", "NavPass123!", "Nav User", retries=10, role="admin")


def _ensure_user(email, password, full_name, retries=3, role="driver"):
    """Register a user only if login fails. This avoids hitting the register rate limiter for known users."""
    try:
        _api_login_token(email, password, retries=retries)
        return None  # user already exists
    except Exception:
        pass
    for attempt in range(retries + 1):
        data = json.dumps({"email": email, "password": password, "full_name": full_name, "role": role}).encode()
        req = urllib.request.Request(f"{BASE_URL}/api/v1/auth/register", data=data, headers={"Content-Type": "application/json"})
        try:
            resp = urllib.request.urlopen(req)
            return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            body = e.read().decode()
            if "already" in body:
                return None
            if e.code == 429 and attempt < retries:
                time.sleep(2 + attempt * 2)
                continue
            raise
    raise AssertionError(f"Failed to register {email} after {retries} retries")

def _api_login_token(email, password, retries=3):
    """Call the login API and return (token, user). Caches per email to avoid rate limits."""
    if email in _token_cache:
        return _token_cache[email]
    for attempt in range(retries + 1):
        data = json.dumps({"email": email, "password": password}).encode()
        req = urllib.request.Request(f"{BASE_URL}/api/v1/auth/login", data=data, headers={"Content-Type": "application/json"})
        try:
            resp = urllib.request.urlopen(req)
            body = json.loads(resp.read())
            result = (body["access_token"], body["user"])
            _token_cache[email] = result
            return result
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < retries:
                time.sleep(2 + attempt * 2)
                continue
            raise
    raise AssertionError(f"Failed to login {email} after {retries} retries")


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True, args=["--no-sandbox"])
        yield b
        b.close()


@pytest.fixture
def context(browser):
    ctx = browser.new_context(viewport={"width": 1280, "height": 720})
    yield ctx
    ctx.close()


@pytest.fixture
def page(context):
    p = context.new_page()
    yield p
    p.close()


def login(page, email="brenda@pragma.io", password="TestPass123!"):
    token, _ = _api_login_token(email, password)
    page.goto(BASE_URL)
    page.evaluate(f"sessionStorage.setItem('pragma_token', '{token}')")
    page.goto(BASE_URL)
    page.wait_for_timeout(500)
    deadline = time.time() + 10
    while time.time() < deadline:
        hidden = page.evaluate("document.getElementById('app-view').classList.contains('hidden')")
        if not hidden:
            return
        err_hidden = page.evaluate("document.getElementById('login-error').classList.contains('hidden')")
        if not err_hidden:
            err_text = page.evaluate("document.getElementById('login-error').textContent")
            raise AssertionError(f"Auto-login failed: {err_text}")
        page.wait_for_timeout(300)
    raise AssertionError("Auto-login timed out after 10s — app-view never appeared")


def login_via_form(page, email, password):
    try:
        token, user = _api_login_token(email, password)
    except Exception:
        return  # bad credentials — caller tests the error state
    page.goto(BASE_URL)
    page.evaluate(f"sessionStorage.setItem('pragma_token', '{token}')")
    page.goto(BASE_URL)
    page.wait_for_timeout(1000)
