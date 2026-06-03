import os
import json
import time
import urllib.request
import urllib.error
import pytest
from typing import Optional
from playwright.sync_api import sync_playwright, TimeoutError as _PWTimeout

@pytest.fixture(autouse=True)
def setup_db():
    """Override tests/conftest.py setup_db — do NOT drop the shared e2e server DB."""
    yield

BASE_URL = os.getenv("E2E_BASE_URL", "http://127.0.0.1:8989")


_token_cache: dict[str, tuple[str, dict]] = {}


@pytest.fixture(scope="session", autouse=True)
def _pre_register_users():
    """Pre-register all test users once per session (avoids rate-limit races)."""
    with open("/tmp/login_via_form_debug.log", "a") as f:
        f.write("_pre_register_users starting\n")
    _ensure_user("e2e@test.io", "E2ePass123!", "E2E User", retries=10, role="admin")
    with open("/tmp/login_via_form_debug.log", "a") as f:
        f.write("_ensure_user e2e done\n")
    _ensure_user("nav@test.io", "NavPass123!", "Nav User", retries=10, role="admin")
    with open("/tmp/login_via_form_debug.log", "a") as f:
        f.write("_pre_register_users done\n")


def _ensure_user(email, password, full_name, retries=3, role="driver"):
    """Register a user only if login fails. This avoids hitting the register rate limiter for known users."""
    with open("/tmp/login_via_form_debug.log", "a") as f:
        f.write(f"  _ensure_user({email}) login attempt...\n")
    try:
        _api_login_token(email, password, retries=retries)
        with open("/tmp/login_via_form_debug.log", "a") as f:
            f.write(f"  _ensure_user({email}) already exists\n")
        return None  # user already exists
    except Exception as ex:
        with open("/tmp/login_via_form_debug.log", "a") as f:
            f.write(f"  _ensure_user({email}) login failed: {ex}, registering...\n")
    for attempt in range(retries + 1):
        data = json.dumps({"email": email, "password": password, "full_name": full_name, "role": role}).encode()
        req = urllib.request.Request(f"{BASE_URL}/api/v1/auth/register", data=data, headers={"Content-Type": "application/json"})
        try:
            resp = urllib.request.urlopen(req)
            with open("/tmp/login_via_form_debug.log", "a") as f:
                f.write(f"  _ensure_user({email}) registered OK\n")
            return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            body = e.read().decode()
            with open("/tmp/login_via_form_debug.log", "a") as f:
                f.write(f"  _ensure_user({email}) register attempt {attempt}: {e.code} {body[:100]}\n")
            if "already" in body:
                return None
            if e.code == 429 and attempt < retries:
                continue
            raise
    raise AssertionError(f"Failed to register {email} after {retries} retries")

def _api_login_token(email, password, retries=3):
    """Call the login API and return (token, user). Caches per email to avoid rate limits."""
    if email in _token_cache:
        with open("/tmp/login_via_form_debug.log", "a") as f:
            f.write(f"    _api_login_token({email}) cache hit\n")
        return _token_cache[email]
    for attempt in range(retries + 1):
        data = json.dumps({"email": email, "password": password}).encode()
        req = urllib.request.Request(f"{BASE_URL}/api/v1/auth/login", data=data, headers={"Content-Type": "application/json"})
        try:
            resp = urllib.request.urlopen(req)
            body = json.loads(resp.read())
            result = (body["access_token"], body["user"])
            _token_cache[email] = result
            with open("/tmp/login_via_form_debug.log", "a") as f:
                f.write(f"    _api_login_token({email}) OK, role={body.get('user',{}).get('role','?')}\n")
            return result
        except urllib.error.HTTPError as e:
            body_text = ""
            try: body_text = e.read().decode()[:100]
            except: pass
            with open("/tmp/login_via_form_debug.log", "a") as f:
                f.write(f"    _api_login_token({email}) attempt {attempt}: {e.code} {body_text}\n")
            if e.code == 429 and attempt < retries:
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


def _wait_for_spa(page, timeout=15):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            el = page.evaluate("document.getElementById('app-view')")
            if el is not None:
                hidden = page.evaluate("document.getElementById('app-view').classList.contains('hidden')")
                if not hidden:
                    return
        except Exception:
            pass
        page.wait_for_timeout(300)
    raise AssertionError(f"SPA app-view never appeared after {timeout}s")

def login(page, email="brenda@pragma.io", password="TestPass123!"):
    token, _ = _api_login_token(email, password)
    page.goto(BASE_URL)
    page.evaluate(f"sessionStorage.setItem('pragma_token', '{token}')")
    page.goto(f"{BASE_URL}/app/dashboard")
    _wait_for_spa(page)


def login_via_form(page, email, password):
    with open("/tmp/login_via_form_debug.log", "a") as f:
        f.write(f"login_via_form called with {email}\n")
    try:
        token, user = _api_login_token(email, password)
    except Exception as e:
        with open("/tmp/login_via_form_debug.log", "a") as f:
            f.write(f"EXCEPTION: {e}\n")
        return  # bad credentials — caller tests the error state
    with open("/tmp/login_via_form_debug.log", "a") as f:
        f.write(f"token OK for {email}\n")
    page.goto(BASE_URL)
    with open("/tmp/login_via_form_debug.log", "a") as f:
        f.write(f"after goto1, checking url...\n")
    url1 = page.evaluate("window.location.href")
    with open("/tmp/login_via_form_debug.log", "a") as f:
        f.write(f"after goto1 url={url1}\n")
    page.evaluate(f"sessionStorage.setItem('pragma_token', '{token}')")
    with open("/tmp/login_via_form_debug.log", "a") as f:
        f.write(f"token set in sessionStorage, now goto2\n")
    page.goto(f"{BASE_URL}/app/dashboard")
    _wait_for_spa(page)
    url3 = page.evaluate("window.location.href")
    with open("/tmp/login_via_form_debug.log", "a") as f:
        f.write(f"after spa wait url={url3}\n")
    with open("/tmp/login_via_form_debug.log", "a") as f:
        f.write(f"session token = {page.evaluate('sessionStorage.getItem(\"pragma_token\")')}\n")
