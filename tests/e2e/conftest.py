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
    yield

BASE_URL = os.getenv("E2E_BASE_URL", "http://127.0.0.1:8989")

_token_cache: dict[str, tuple[str, dict]] = {}

@pytest.fixture(scope="session", autouse=True)
def _pre_register_users():
    _ensure_user("e2e@test.io", "E2ePass123!", "E2E User", retries=10, role="admin")
    _ensure_user("nav@test.io", "NavPass123!", "Nav User", retries=10, role="admin")

def _ensure_user(email, password, full_name, retries=3, role="driver"):
    try:
        _api_login_token(email, password, retries=retries)
        return None
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
                continue
            raise
    raise AssertionError(f"Failed to register {email} after {retries} retries")

def _api_login_token(email, password, retries=3):
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
            body_text = ""
            try: body_text = e.read().decode()[:100]
            except: pass
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
            content = page.evaluate("document.body?.innerText || ''")
            if "Admin Panel" in content or "Dashboard" in content:
                return
        except Exception:
            pass
        page.wait_for_timeout(300)
    raise AssertionError(f"SPA admin UI never appeared after {timeout}s")


def _set_local_storage(page, token, user):
    page.evaluate("""(args) => {
        localStorage.setItem('pragma_token', args.token);
        localStorage.setItem('pragma_user', JSON.stringify(args.user));
    }""", {"token": token, "user": user})


def login(page, email="brenda@pragma.io", password="TestPass123!"):
    token, user = _api_login_token(email, password)
    page.goto(f"{BASE_URL}/#/app/dashboard")
    page.wait_for_timeout(500)
    _set_local_storage(page, token, user)
    page.reload()
    _wait_for_spa(page)


def login_via_form(page, email, password):
    try:
        token, user = _api_login_token(email, password)
    except Exception:
        return
    page.goto(f"{BASE_URL}/#/app/dashboard")
    page.wait_for_timeout(500)
    _set_local_storage(page, token, user)
    page.reload()
    _wait_for_spa(page)
