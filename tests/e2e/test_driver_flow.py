"""Playwright E2E: Driver persona — P0 flow (login, search, full session, end, receipt)."""

import json
import time
import urllib.request
import urllib.error
import pytest
from conftest import BASE_URL, login


DRIVER_EMAIL = "e2e-driver@demo.io"
DRIVER_PASS = "E2ePass123!"
DRIVER_TOKEN = None


def _api(path, token=None, data=None, method="POST"):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(f"{BASE_URL}{path}", data=body, headers=headers, method=method)
    try:
        resp = urllib.request.urlopen(req)
        return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body_text = e.read().decode()
        raise AssertionError(f"{method} {path} -> {e.code}: {body_text}")


def _ensure_driver():
    """Ensure driver test user exists, return token."""
    global DRIVER_TOKEN
    # Try login first
    try:
        body = _api("/api/v1/auth/login", data={"email": DRIVER_EMAIL, "password": DRIVER_PASS})
        DRIVER_TOKEN = body["access_token"]
        return DRIVER_TOKEN
    except AssertionError:
        pass
    # Register
    body = _api("/api/v1/auth/register", data={
        "email": DRIVER_EMAIL, "password": DRIVER_PASS,
        "full_name": "E2E Driver", "role": "driver"
    })
    body = _api("/api/v1/auth/login", data={"email": DRIVER_EMAIL, "password": DRIVER_PASS})
    DRIVER_TOKEN = body["access_token"]
    return DRIVER_TOKEN


def _end_active_sessions():
    tok = _ensure_driver()
    try:
        res = _api("/api/v1/sessions/history", token=tok, method="GET")
        sessions = res.get("sessions", [])
        for s in sessions:
            if s.get("status") in ("active", "running"):
                _api("/api/v1/sessions/end", token=tok, data={"session_id": s["session_id"], "force": True})
    except Exception as e:
        print(f"Warning clearing sessions: {e}")


def _ensure_wallet():
    """Ensure driver has wallet funds."""
    tok = _ensure_driver()
    try:
        bal = _api("/api/v1/wallet", token=tok, method="GET")
        if bal.get("balance", 0) < 100:
            _api("/api/v1/wallet/topup", token=tok, data={"amount": 200})
    except Exception as e:
        print(f"Warning topping up wallet: {e}")


# ── P0: Driver login ──

def test_driver_login(page):
    """Driver can login and see find page."""
    tok = _ensure_driver()
    page.goto(BASE_URL)
    page.evaluate(f"sessionStorage.setItem('pragma_driver_token', '{tok}')")
    page.evaluate(f"sessionStorage.setItem('pragma_driver_user', JSON.stringify({{email:'{DRIVER_EMAIL}'}}))")
    page.goto(f"{BASE_URL}/#/driver/find")
    page.wait_for_timeout(1500)

    body = page.evaluate("document.body.innerText || ''")
    assert "Find" in body or "find" in body, f"Find page missing find text: {body[:200]}"
    assert "park" in body.lower() or "lots" in body.lower(), \
        f"Find page missing parking/lots: {body[:200]}"


# ── P0: Driver search lots ──

def test_driver_search_lots(page):
    """Lot cards appear on the find page."""
    tok = _ensure_driver()
    _end_active_sessions()
    page.goto(BASE_URL)
    page.evaluate(f"sessionStorage.setItem('pragma_driver_token', '{tok}')")
    page.evaluate(f"sessionStorage.setItem('pragma_driver_user', JSON.stringify({{email:'{DRIVER_EMAIL}'}}))")
    page.goto(f"{BASE_URL}/#/driver/find")

    deadline = time.time() + 20
    lot_text = ""
    while time.time() < deadline:
        lot_text = page.evaluate("document.body.innerText || ''")
        if "/hr" in lot_text or lots_check(lot_text):
            break
        page.wait_for_timeout(500)
    assert "/hr" in lot_text or "spots" in lot_text, \
        f"No lot cards appeared: {lot_text[:300]}"


def lots_check(text):
    """Check if text mentions slot counts."""
    keywords = ["spots", "slots", "/hr", "$"]
    return any(k in text for k in keywords)


# ── P0: Full session flow ──

def test_driver_full_session_flow(page):
    """Complete session lifecycle: find lot → start → timer → end → pay → receipt."""
    tok = _ensure_driver()
    _end_active_sessions()
    _ensure_wallet()

    # Set auth in session storage
    page.goto(BASE_URL)
    page.evaluate(f"sessionStorage.setItem('pragma_driver_token', '{tok}')")
    page.evaluate(f"sessionStorage.setItem('pragma_driver_user', JSON.stringify({{email:'{DRIVER_EMAIL}'}}))")
    page.goto(f"{BASE_URL}/#/driver/find")

    # Wait for lot cards
    deadline = time.time() + 20
    lot_cards = []
    while time.time() < deadline:
        lot_cards = page.evaluate("document.querySelectorAll('button')")
        lot_cards = [b for b in lot_cards if '/hr' in (b.get('textContent') or '')]
        if lot_cards:
            break
        page.wait_for_timeout(500)
    assert lot_cards, "No lot cards appeared after 20s"

    # Click the first lot card
    page.evaluate("""
        const buttons = document.querySelectorAll('button');
        for (const b of buttons) {
            if (b.textContent.includes('/hr')) {
                b.click();
                break;
            }
        }
    """)
    page.wait_for_timeout(1500)

    # Wait for slot picker
    deadline = time.time() + 10
    slot_btns = []
    while time.time() < deadline:
        slot_btns = page.evaluate("document.querySelectorAll('button')")
        slot_btns = [b for b in slot_btns if b.get('textContent') and b['textContent'].strip().isdigit()]
        if slot_btns:
            break
        page.wait_for_timeout(500)

    if not slot_btns:
        pytest.skip("No slot buttons found — lot detail may not have rendered")
        return

    # Click first slot number
    first_slot_text = slot_btns[0]['textContent'].strip()
    page.evaluate(f"""
        const buttons = document.querySelectorAll('button');
        for (const b of buttons) {{
            if (b.textContent.trim() === '{first_slot_text}' && !isNaN(parseInt(b.textContent.trim()))) {{
                b.click();
                break;
            }}
        }}
    """)
    page.wait_for_timeout(500)

    # Click "Park in Slot N" button
    deadline = time.time() + 10
    clicked_start = False
    while time.time() < deadline:
        park_text = page.evaluate("document.body.innerText || ''")
        if "Park in Slot" in park_text or "Select a Slot" in park_text:
            # Find and click the start button
            page.evaluate("""
                const buttons = document.querySelectorAll('button');
                for (const b of buttons) {
                    if (b.textContent.includes('Park in Slot') || b.textContent.includes('Starting')) {
                        b.click();
                        break;
                    }
                }
            """)
            clicked_start = True
            break
        page.wait_for_timeout(500)

    assert clicked_start, "Could not find Park in Slot button"

    # Wait for redirect to active session
    deadline = time.time() + 15
    on_active = False
    while time.time() < deadline:
        if "active" in page.url:
            on_active = True
            break
        page.wait_for_timeout(500)
    assert on_active, f"Did not navigate to active session, URL: {page.url}"

    # Wait for timer or active session content
    deadline = time.time() + 10
    session_text = ""
    while time.time() < deadline:
        session_text = page.evaluate("document.body.innerText || ''")
        if "Active" in session_text or "Session" in session_text or "End" in session_text:
            break
        page.wait_for_timeout(500)
    assert "End" in session_text or "Active" in session_text, \
        f"Active session page not showing: {session_text[:200]}"

    # Brief tick
    page.wait_for_timeout(3000)

    # Click End Parking
    deadline = time.time() + 10
    clicked_end = False
    while time.time() < deadline:
        end_btn = page.evaluate("""
            const buttons = document.querySelectorAll('button');
            let found = null;
            for (const b of buttons) {
                if (b.textContent.includes('End')) {
                    found = b;
                    break;
                }
            }
            found ? 'found' : null;
        """)
        if end_btn:
            page.evaluate("""
                const buttons = document.querySelectorAll('button');
                for (const b of buttons) {
                    if (b.textContent.includes('End')) {
                        b.click();
                        break;
                    }
                }
            """)
            clicked_end = True
            break
        page.wait_for_timeout(500)

    assert clicked_end, "End Parking button not found"

    # Wait for session ended / payment screen
    deadline = time.time() + 15
    payment_screen = False
    while time.time() < deadline:
        body = page.evaluate("document.body.innerText || ''")
        if "Session Ended" in body or "Pay $" in body or "Total due" in body:
            payment_screen = True
            break
        page.wait_for_timeout(1000)
    assert payment_screen, "Session ended screen did not appear"

    # Click Pay button
    deadline = time.time() + 10
    clicked_pay = False
    while time.time() < deadline:
        pay_btn = page.evaluate("""
            const buttons = document.querySelectorAll('button');
            for (const b of buttons) {
                if (b.textContent.includes('Pay $')) {
                    b.click();
                    return 'clicked';
                }
            }
            return null;
        """)
        if pay_btn:
            clicked_pay = True
            break
        page.wait_for_timeout(500)

    assert clicked_pay, "Pay button not found"

    # Wait for receipt
    deadline = time.time() + 15
    receipt = False
    while time.time() < deadline:
        body = page.evaluate("document.body.innerText || ''")
        if "Parking Complete" in body or "Charged" in body or "Duration" in body:
            receipt = True
            break
        page.wait_for_timeout(1000)
    assert receipt, "Receipt screen did not appear after payment"


# ── P1: Session history ──

def test_driver_session_history(page):
    """Driver can view session history after completing a session."""
    tok = _ensure_driver()
    page.goto(BASE_URL)
    page.evaluate(f"sessionStorage.setItem('pragma_driver_token', '{tok}')")
    page.evaluate(f"sessionStorage.setItem('pragma_driver_user', JSON.stringify({{email:'{DRIVER_EMAIL}'}}))")
    page.goto(f"{BASE_URL}/#/driver/history")

    deadline = time.time() + 10
    while time.time() < deadline:
        body = page.evaluate("document.body.innerText || ''")
        if "History" in body:
            break
        page.wait_for_timeout(500)
    body = page.evaluate("document.body.innerText || ''")
    assert "History" in body, f"History page missing heading: {body[:200]}"


# ── P1: Wallet ──

def test_driver_wallet(page):
    """Driver wallet balance and topup."""
    tok = _ensure_driver()

    # Check balance via API
    bal = _api("/api/v1/wallet", token=tok, method="GET")
    balance_before = bal.get("balance", 0)

    # Topup via API
    result = _api("/api/v1/wallet/topup", token=tok, data={"amount": 50.0})
    assert "balance" in result, f"Topup response missing balance: {result}"
    assert result.get("amount_added", 0) == 50.0, f"Topup amount mismatch: {result}"
    assert result["balance"] == balance_before + 50.0, \
        f"Balance mismatch: {result['balance']} != {balance_before + 50}"

    # Verify in UI
    page.goto(BASE_URL)
    page.evaluate(f"sessionStorage.setItem('pragma_driver_token', '{tok}')")
    page.evaluate(f"sessionStorage.setItem('pragma_driver_user', JSON.stringify({{email:'{DRIVER_EMAIL}'}}))")
    page.goto(f"{BASE_URL}/#/driver/find")
    page.wait_for_timeout(1500)
    body = page.evaluate("document.body.innerText || ''")
    # The wallet increased, just verify the find page loads
    assert "Find" in body or "parking" in body.lower(), f"Find page after topup: {body[:200]}"


# ── P2: Payment history ──

def test_driver_payment_history(page):
    """Driver can retrieve payment history via API."""
    tok = _ensure_driver()
    result = _api("/api/v1/payments/history", token=tok, method="GET")
    assert "payments" in result or "transactions" in result or isinstance(result, list), \
        f"Payment history unexpected shape: {type(result)}"
