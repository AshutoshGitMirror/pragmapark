from playwright.sync_api import sync_playwright, expect


BASE_URL = "http://127.0.0.1:8989"


def test_app_loads():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(BASE_URL)
        expect(page).to_have_title(
            "PRAGMA | AI-Powered Smart Parking with Blockchain Ledger"
        )
        browser.close()
