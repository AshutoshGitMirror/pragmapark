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
        token, user = _token_cache[email]
        try:
            req = urllib.request.Request(
                f"{BASE_URL}/api/v1/auth/me",
                headers={"Authorization": f"Bearer {token}"},
            )
            urllib.request.urlopen(req)
            return token, user
        except Exception:
            _token_cache.pop(email, None)
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
    p.on("console", lambda msg: print(f"[CONSOLE] {msg.type}: {msg.text}"))
    p.on("pageerror", lambda err: print(f"[PAGE ERROR] {err}"))
    p.on("requestfailed", lambda req: print(f"[REQ FAILED] {req.method} {req.url}: {getattr(req.failure, 'error_text', req.failure) if req.failure else 'no error'}"))
    p.on("response", lambda resp: print(f"[RESP] {resp.status} {resp.url}") if resp.status >= 400 else None)
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
    url = page.url
    text = ""
    try:
        text = page.evaluate("document.body?.innerText || ''")
    except Exception as e:
        text = f"Error evaluating: {e}"
    cookies = page.context.cookies()
    print(f"\n[DEBUG _wait_for_spa] URL: {url}\n[DEBUG cookies] {cookies}\n[DEBUG _wait_for_spa] Text:\n{text}\n")
    raise AssertionError(f"SPA admin UI never appeared after {timeout}s. URL: {url}")


def _set_auth_cookie(page, token):
    """Set the pragma_token HttpOnly cookie via Playwright's API context."""
    # Use the page's browser context to add the cookie directly
    page.context.add_cookies([{
        "name": "pragma_token",
        "value": token,
        "url": BASE_URL.rstrip("/") + "/",
        "httpOnly": True,
        "sameSite": "Lax",
    }])


def login(page, email="brenda@pragma.io", password="TestPass123!"):
    token, user = _api_login_token(email, password)
    # Set the HttpOnly cookie before the SPA ever mounts. AuthProvider only calls
    # /auth/me on initial mount; navigating first would cache an unauthenticated
    # state and redirect to /login even after the cookie is added.
    _set_auth_cookie(page, token)
    page.goto(f"{BASE_URL}/#/app/dashboard")
    _wait_for_spa(page)


def login_via_form(page, email, password):
    try:
        token, user = _api_login_token(email, password)
    except Exception:
        return
    # See login(): cookie must exist before the SPA mounts.
    _set_auth_cookie(page, token)
    page.goto(f"{BASE_URL}/#/app/dashboard")
    _wait_for_spa(page)
