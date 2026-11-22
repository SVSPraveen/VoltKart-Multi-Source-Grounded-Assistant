"""tests/e2e/test_ui_screens.py - Playwright UI end-to-end and responsive screenshot verification.

Verifies:
1. Spawns live FastAPI backend serving the compiled React frontend.
2. Connects via Playwright headless browser at 4 standard breakpoints:
   - 360px (mobile)
   - 768px (tablet)
   - 1280px (laptop)
   - 1920px (desktop)
3. Saves visual screenshots to reports/screens/ for DESIGN.md inspection.
4. Asserts presence of core interface components: sidebar, thread, composer, evidence drawer.
"""

from __future__ import annotations

from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
SCREENS_DIR = ROOT_DIR / "reports" / "screens"


def test_responsive_screenshots_and_layout(live_server: str):
    """Capture responsive screenshots across 360px, 768px, 1280px, 1920px."""
    SCREENS_DIR.mkdir(parents=True, exist_ok=True)

    breakpoints = [
        (360, 640, "screen-360.png"),
        (768, 1024, "screen-768.png"),
        (1280, 800, "screen-1280.png"),
        (1920, 1080, "screen-1920.png"),
    ]

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)

        for width, height, filename in breakpoints:
            page = browser.new_page(viewport={"width": width, "height": height})
            page.goto(live_server, wait_until="networkidle")

            # Check that root container and core instrument-panel controls rendered
            assert page.locator("#root").count() > 0

            # Verify presence of core workspace controls
            assert page.locator("button:has-text('Export PDF')").count() > 0
            assert page.locator("button:has-text('Ingestion Card')").count() > 0
            assert page.locator("textarea").count() > 0
            assert page.locator("text=Web Search").count() > 0
            assert page.locator("button:has-text('Send')").count() > 0
            assert page.locator("button:has-text('Upload Files')").count() > 0

            # On mobile viewport (360px), verify mobile drawer/menu toggle exists
            if width <= 768:
                assert page.locator(".header-menu-btn").count() > 0

            # Capture screenshot
            out_path = SCREENS_DIR / filename
            page.screenshot(path=str(out_path), full_page=True)
            assert out_path.exists()
            assert out_path.stat().st_size > 5000  # Non-trivial image content
            page.close()

        browser.close()
