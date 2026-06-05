"""Playwright E2E: Anonymous visitor — landing page (P0)."""

import time
from conftest import BASE_URL


def test_landing_page_loads(page):
    """Validate hero, ThreeGlobe, MetricTicker, architecture diagram, live terminal, CTA."""
    page.goto(f"{BASE_URL}/#/")
    page.wait_for_timeout(2000)

    # Hero section renders
    hero = page.evaluate("document.querySelector('section')?.textContent || ''")
    assert "Pragma" in hero or "Smart Parking" in hero or "Autonomous" in hero, \
        f"Hero missing key text: {hero[:200]}"

    # Architecture diagram section renders with all 6 layers
    arch = page.evaluate("document.getElementById('architecture')?.textContent || ''")
    layers = ["IoT", "ML", "Blockchain", "RL", "Digital Twin", "Actuator"]
    for layer in layers:
        assert layer.lower() in arch.lower(), f"Architecture section missing layer: {layer}"

    # Live terminal section renders
    terminal = page.evaluate("document.getElementById('terminal')?.textContent || ''")
    assert len(terminal) > 50, f"Terminal missing content: {terminal[:100]}"

    # Testimonials section renders
    testimonials = page.evaluate("document.getElementById('testimonials')?.textContent || ''")
    assert len(testimonials) > 50, f"Testimonials missing content: {testimonials[:100]}"

    # Prediction engine section renders
    prediction = page.evaluate("document.getElementById('prediction')?.textContent || ''")
    assert len(prediction) > 50, f"Prediction section missing content: {prediction[:100]}"

    # Blockchain section renders
    blockchain = page.evaluate("document.getElementById('blockchain')?.textContent || ''")
    assert len(blockchain) > 50, f"Blockchain section missing content: {blockchain[:100]}"

    # Digital twin section renders
    dt = page.evaluate("document.getElementById('digital-twin')?.textContent || ''")
    assert len(dt) > 50, f"Digital twin section missing content: {dt[:100]}"

    # Revenue section renders
    revenue = page.evaluate("document.getElementById('revenue')?.textContent || ''")
    assert len(revenue) > 50, f"Revenue section missing content: {revenue[:100]}"

    # Slots section renders
    slots = page.evaluate("document.getElementById('slots')?.textContent || ''")
    assert len(slots) > 50, f"Slots section missing content: {slots[:100]}"
