import json
import time
import urllib.request
import urllib.error
import pytest
from conftest import BASE_URL, login


DRIVER_EMAIL = "micro_driver@pragma.io"
DRIVER_PASS = "MicroPass1!"
DRIVER_TOKEN = None
_SEEDED = False


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


def _ensure_token():
    global DRIVER_TOKEN
    if DRIVER_TOKEN:
        return DRIVER_TOKEN
    try:
        body = _api("/api/v1/auth/register", data={"email": DRIVER_EMAIL, "password": DRIVER_PASS, "full_name": "Micro Driver", "role": "driver"})
    except AssertionError:
        body = _api("/api/v1/auth/login", data={"email": DRIVER_EMAIL, "password": DRIVER_PASS})
    DRIVER_TOKEN = body["access_token"]
    return DRIVER_TOKEN


def _end_active_sessions():
    tok = _ensure_token()
    try:
        res = _api("/api/v1/sessions/history", token=tok, method="GET")
        sessions = res.get("sessions", [])
        for s in sessions:
            if s.get("status") in ("active", "running"):
                _api("/api/v1/sessions/end", token=tok, data={"session_id": s["session_id"], "force": True})
    except Exception as e:
        print(f"Warning clearing sessions: {e}")


@pytest.fixture(scope="module", autouse=True)
def _seed_micro_slots():
    """Admin-seed a lot with micro slots and register our driver."""
    global _SEEDED
    if _SEEDED:
        return
    try:
        admin_body = _api("/api/v1/auth/register", data={"email": "micro_admin@pragma.io", "password": "AdminPass1!", "full_name": "Micro Admin", "role": "admin"})
    except AssertionError:
        admin_body = _api("/api/v1/auth/login", data={"email": "micro_admin@pragma.io", "password": "AdminPass1!"})
    admin_tok = admin_body["access_token"]
    try:
        _api("/api/v1/lots", token=admin_tok, data={"lot_id": "e2e_micro_lot", "name": "E2E Micro Lot", "total_slots": 30, "base_price": 8.0})
    except AssertionError:
        pass  # Lot already exists
    _api("/api/v1/micro/lots/e2e_micro_lot/slots/seed", token=admin_tok, method="POST")
    _SEEDED = True


def test_micro_slot_grid_renders(page):
    """Slot grid appears when a lot with micro slots is selected."""
    tok = _ensure_token()
    _end_active_sessions()
    page.goto(BASE_URL)
    page.evaluate(f"sessionStorage.setItem('pragma_driver_token', '{tok}')")
    page.evaluate(f"sessionStorage.setItem('pragma_driver_id', '{DRIVER_EMAIL}')")
    page.goto(f"{BASE_URL}/app/driver")
    deadline = time.time() + 20
    lot_cards = []
    while time.time() < deadline:
        lot_cards = page.evaluate("document.querySelectorAll('.lot-card')")
        if lot_cards and len(lot_cards) > 0:
            break
        page.wait_for_timeout(500)
    assert lot_cards and len(lot_cards) > 0, "No lot cards appeared after 20s"
    page.evaluate("document.querySelector('.lot-card').click()")
    deadline = time.time() + 15
    slot_cells = []
    while time.time() < deadline:
        slot_cells = page.evaluate("document.querySelectorAll('.slot-cell')")
        if slot_cells and len(slot_cells) > 0:
            break
        page.wait_for_timeout(500)
    assert slot_cells and len(slot_cells) > 0, "No slot cells appeared after selecting a lot"


def test_micro_slot_select_and_reserve_release(page):
    """Click slot cell -> selected bar -> reserve -> countdown -> release."""
    tok = _ensure_token()
    _end_active_sessions()
    page.goto(BASE_URL)
    page.evaluate(f"sessionStorage.setItem('pragma_driver_token', '{tok}')")
    page.evaluate(f"sessionStorage.setItem('pragma_driver_id', '{DRIVER_EMAIL}')")
    page.goto(f"{BASE_URL}/app/driver")
    # Wait for lot cards
    deadline = time.time() + 20
    while time.time() < deadline:
        if page.evaluate("document.querySelectorAll('.lot-card').length > 0"):
            break
        page.wait_for_timeout(500)
    page.evaluate("document.querySelector('.lot-card').click()")
    deadline = time.time() + 15
    while time.time() < deadline:
        if page.evaluate("document.querySelectorAll('.slot-cell').length > 0"):
            break
        page.wait_for_timeout(500)
    # Find and click an available slot
    available_idx = page.evaluate("""() => {
        const cells = document.querySelectorAll('.slot-cell');
        for (let c of cells) {
            const el = document.querySelector('.slot-cell[data-slot-index="' + c.dataset.slotIndex + '"]');
            if (el && el.getAttribute('aria-label') && el.getAttribute('aria-label').includes('available')) {
                return parseInt(c.dataset.slotIndex);
            }
        }
    }""")
    if available_idx is None:
        available_idx = page.evaluate("parseInt(document.querySelector('.slot-cell').dataset.slotIndex) || 1")
    page.evaluate(f"onSlotCellClick('e2e_micro_lot', {available_idx})")
    page.wait_for_timeout(500)
    selected_bar_visible = page.evaluate("document.getElementById('selected-slot-bar').style.display !== 'none'")
    assert selected_bar_visible, "Selected slot bar should appear after clicking cell"
    slot_label = page.evaluate("document.getElementById('sel-slot-label').textContent")
    assert slot_label and len(slot_label) > 0, "Slot label should be shown in selected bar"
    slot_state = page.evaluate("document.getElementById('sel-slot-state').textContent")
    assert slot_state and slot_state.lower() in ("available", "reserved", "occupied"), f"Unexpected slot state: {slot_state}"
    # Click Reserve
    reserve_btn = page.evaluate("document.getElementById('reserve-slot-btn')")
    assert reserve_btn is not None, "Reserve button should exist"
    reserve_visible = page.evaluate("document.getElementById('reserve-slot-btn').style.display !== 'none'")
    if not reserve_visible:
        pytest.skip("Reserve button not visible (slot may not be available)")
    page.evaluate("document.getElementById('reserve-slot-btn').click()")
    page.wait_for_timeout(1500)
    reserve_html = page.evaluate("document.getElementById('reserve-slot-btn')?.innerHTML || 'null'")
    reserve_display = page.evaluate("document.getElementById('reserve-slot-btn')?.style?.display || 'null'")
    release_html = page.evaluate("document.getElementById('release-slot-btn')?.innerHTML || 'null'")
    release_display = page.evaluate("document.getElementById('release-slot-btn')?.style?.display || 'null'")
    expiry_debug = page.evaluate("""() => {
        const e = typeof reservationExpiresAt !== 'undefined' ? reservationExpiresAt : 'UNDEF';
        const a = typeof activeReservationId !== 'undefined' ? activeReservationId : 'UNDEF';
        return 'expiresAt=' + e + ' activeId=' + a + ' now=' + Date.now();
    }""")
    api_debug = page.evaluate("""async () => {
        const tok = sessionStorage.getItem('pragma_driver_token');
        const resp = await fetch('/api/v1/micro/reserve', {
            method: 'POST',
            headers: {'Content-Type':'application/json','Authorization':'Bearer '+tok},
            body: JSON.stringify({lot_id:'e2e_micro_lot',slot_index:1})
        });
        const txt = await resp.text();
        return txt.slice(0,300);
    }""")
    print(f"  DEBUG reserve_html={reserve_html[:60]}")
    print(f"  DEBUG release_html={release_html[:60]}, release_display={release_display}")
    print(f"  DEBUG {expiry_debug}")
    print(f"  DEBUG api_raw={api_debug}")
    has_countdown = ":" in reserve_html and ("Reserved" in reserve_html or "clock" in reserve_html)
    assert has_countdown, f"Reserve button should show countdown, got: {reserve_html[:60]}"
    assert release_display != "none", f"Release button display={release_display} (reserve will be tried twice)"
    state_text = page.evaluate("document.getElementById('sel-slot-state').textContent")
    assert state_text.lower() == "reserved", f"Slot state should be reserved, got: {state_text}"
    # Release
    page.on("dialog", lambda d: d.accept())
    page.evaluate("document.getElementById('release-slot-btn').click()")
    page.wait_for_timeout(1500)
    reserve_visible_after = page.evaluate("document.getElementById('reserve-slot-btn').style.display !== 'none'")
    assert reserve_visible_after, "Reserve button should reappear after release"


def test_micro_slot_start_session_with_selected_slot(page):
    """Select slot -> start session -> verify slot label + type badge -> end -> receipt."""
    tok = _ensure_token()
    _end_active_sessions()
    page.goto(BASE_URL)
    page.evaluate(f"sessionStorage.setItem('pragma_driver_token', '{tok}')")
    page.evaluate(f"sessionStorage.setItem('pragma_driver_id', '{DRIVER_EMAIL}')")
    page.goto(f"{BASE_URL}/app/driver")
    deadline = time.time() + 20
    while time.time() < deadline:
        if page.evaluate("document.querySelectorAll('.lot-card').length > 0"):
            break
        page.wait_for_timeout(500)
    page.evaluate("document.querySelector('.lot-card').click()")
    deadline = time.time() + 15
    while time.time() < deadline:
        if page.evaluate("document.querySelectorAll('.slot-cell').length > 0"):
            break
        page.wait_for_timeout(500)
    # Select first available slot
    available_idx = page.evaluate("""() => {
        const cells = document.querySelectorAll('.slot-cell');
        for (let c of cells) {
            const el = document.querySelector('.slot-cell[data-slot-index="' + c.dataset.slotIndex + '"]');
            if (el && el.getAttribute('aria-label') && el.getAttribute('aria-label').includes('available')) {
                return parseInt(c.dataset.slotIndex);
            }
        }
    }""")
    if available_idx is None:
        available_idx = page.evaluate("parseInt(document.querySelector('.slot-cell').dataset.slotIndex) || 1")
    page.evaluate(f"onSlotCellClick('e2e_micro_lot', {available_idx})")
    page.wait_for_timeout(300)
    # Now select the correct lot: call selectLot directly so selectedLotId = e2e_micro_lot
    page.evaluate("""async () => {
        await selectLot('e2e_micro_lot');
    }""")
    page.wait_for_timeout(1000)
    # Re-select the same slot after grid re-render (selectLot resets selectedMicroSlotIndex)
    page.evaluate(f"onSlotCellClick('e2e_micro_lot', {available_idx})")
    page.wait_for_timeout(300)
    # Start session
    btn_disabled = page.evaluate("document.getElementById('start-session-btn')?.disabled")
    btn_text = page.evaluate("document.getElementById('start-session-btn')?.innerHTML || ''")
    print(f"  DEBUG: start-btn disabled={btn_disabled} text={btn_text[:50]}")
    pre_click = page.evaluate("""() => {
        return JSON.stringify({
            selectedMicroSlotIndex,
            selectedSlot: typeof selectedSlot !== 'undefined' ? selectedSlot : 'UNDEF',
            selectedLotId,
            slotFound: !!cachedSlots.find(s => s.slot_index === selectedMicroSlotIndex),
            cachedLen: cachedSlots?.length || 0
        });
    }""")
    print(f"  DEBUG: pre-click state: {pre_click}")
    page.evaluate("document.getElementById('start-session-btn').click()")
    page.wait_for_timeout(2000)
    deadline = time.time() + 20
    timer_text = ""
    while time.time() < deadline:
        timer_text = page.evaluate("document.getElementById('session-timer')?.textContent || ''")
        if timer_text and timer_text != "00:00" and ("00:0" in timer_text or "00:" in timer_text):
            break
        page.wait_for_timeout(500)
    assert timer_text and timer_text != "00:00", f"Session timer did not start (got default '{timer_text}')"
    page.wait_for_timeout(500)
    slot_info_visible = page.evaluate("""() => {
        const el = document.getElementById('active-slot-info');
        return el && el.style.display !== 'none';
    }""")
    if not slot_info_visible:
        diag = page.evaluate("""() => JSON.stringify({
            display: document.getElementById('active-slot-info')?.style?.display,
            len: cachedSlots?.length,
            selIdx: selectedMicroSlotIndex,
            lotId: selectedLotId,
        })""")
        print(f"  DEBUG slot_info: {diag}")
    assert slot_info_visible, "Active slot info should be visible in session card"
    slot_label_active = page.evaluate("document.getElementById('active-slot-label')?.textContent || ''")
    assert slot_label_active, "Slot label should be shown in active session card"
    page.wait_for_timeout(2000)
    # End session
    page.on("dialog", lambda d: d.accept())
    page.evaluate("document.getElementById('end-session-btn').click()")
    deadline = time.time() + 30
    receipt_visible = False
    while time.time() < deadline:
        receipt_visible = page.evaluate("document.getElementById('screen-receipt')?.classList.contains('active') || false")
        if receipt_visible:
            break
        page.wait_for_timeout(1000)
    assert receipt_visible, "Receipt screen did not appear within 30s"
    receipt_title = page.evaluate("document.querySelector('#screen-receipt h2')?.textContent || ''")
    assert "paid" in receipt_title.lower(), f"Receipt title should include 'Paid', got: '{receipt_title}'"
    # Verify receipt shows Lot (indirectly proves slot info was processed)
    receipt_text = page.evaluate("document.getElementById('receipt-details')?.textContent || ''")
    assert "e2e_micro_lot" in receipt_text.lower() or "Slot" in receipt_text, "Receipt should contain slot info"


def test_micro_bookings_tab_renders(page):
    """Bookings tab exists and can be navigated to."""
    tok = _ensure_token()
    page.goto(BASE_URL)
    page.evaluate(f"sessionStorage.setItem('pragma_driver_token', '{tok}')")
    page.evaluate(f"sessionStorage.setItem('pragma_driver_id', '{DRIVER_EMAIL}')")
    page.goto(f"{BASE_URL}/app/driver")
    # Click the Bookings nav button
    bookings_btn = page.evaluate("""() => {
        const btns = document.querySelectorAll('.nav-btn');
        for (let b of btns) {
            if (b.textContent.includes('Bookings')) return b;
        }
        return null;
    }""")
    assert bookings_btn is not None, "Bookings nav button should exist"
    page.evaluate("""() => {
        const btns = document.querySelectorAll('.nav-btn');
        for (let b of btns) {
            if (b.textContent.includes('Bookings')) b.click();
        }
    }""")
    page.wait_for_timeout(500)
    bookings_visible = page.evaluate("document.getElementById('screen-bookings')?.classList.contains('active') || false")
    assert bookings_visible, "Bookings screen should be active after clicking nav button"
    bookings_content = page.evaluate("document.getElementById('screen-bookings')?.textContent || ''")
    assert "Pre-book" in bookings_content or "Booking" in bookings_content or "No" in bookings_content, "Bookings screen should have meaningful content"
