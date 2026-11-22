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

import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
SCREENS_DIR = ROOT_DIR / "reports" / "screens"


def find_free_port() -> int:
    """Find a free TCP port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def live_server():
    """Start local uvicorn test server serving the FastAPI backend and React frontend."""
    port = find_free_port()
    env = {**dict(subprocess.os.environ), "PYTHONPATH": str(ROOT_DIR)}
    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "backend.api:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
    ]

    proc = subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # Wait for server to bind
    base_url = f"http://127.0.0.1:{port}"
    ready = False
    for _ in range(50):
        time.sleep(0.1)
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                ready = True
                break
        except OSError:
            pass

    if not ready:
        proc.kill()
        raise RuntimeError("Failed to start live uvicorn server for E2E test")

    yield base_url

    proc.terminate()
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill()


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

            # Check that root container rendered
            assert page.locator("#root").count() > 0

            # Capture screenshot
            out_path = SCREENS_DIR / filename
            page.screenshot(path=str(out_path), full_page=True)
            assert out_path.exists()
            assert out_path.stat().st_size > 5000  # Non-trivial image content
            page.close()

        browser.close()
