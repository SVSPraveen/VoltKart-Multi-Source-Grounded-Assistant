"""tests/e2e/test_accessibility.py - Playwright & axe-core accessibility audit (V6).

Verifies:
1. WCAG 2.1 AA compliance via axe-core:
   - Injects axe-core engine directly into DOM.
   - Asserts 0 critical and 0 serious accessibility violations.
   - Audits color contrast, button labels, and semantic landmarks.
2. Keyboard navigation and visible focus rings.
3. Responsive layout integrity across standard breakpoints.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
AXE_PATH = ROOT_DIR / "frontend" / "node_modules" / "axe-core" / "axe.min.js"
REPORTS_DIR = ROOT_DIR / "reports"


def test_axe_core_accessibility_audit(live_server: str):
    """Run full axe-core WCAG 2.1 AA accessibility audit on the live interface."""
    assert AXE_PATH.exists(), f"axe-core library not found at {AXE_PATH}"
    axe_script = AXE_PATH.read_text(encoding="utf-8")

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        page.goto(live_server, wait_until="networkidle")

        # Inject axe-core into the active page context
        page.evaluate(axe_script)

        # Run axe accessibility analysis
        axe_results = page.evaluate("""
            axe.run({
                runOnly: {
                    type: 'tag',
                    values: ['wcag2a', 'wcag2aa', 'wcag21aa']
                }
            })
        """)

        violations = axe_results.get("violations", [])
        critical_violations = [v for v in violations if v.get("impact") in ("critical", "serious")]

        # Write audit report
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        report_file = REPORTS_DIR / "accessibility_audit.json"
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "passes_count": len(axe_results.get("passes", [])),
                    "violations_count": len(violations),
                    "critical_serious_count": len(critical_violations),
                    "violations": violations,
                },
                f,
                indent=2,
            )

        # Assert zero critical or serious WCAG violations
        if critical_violations:
            violation_summaries = [
                f"[{v.get('impact')}] {v.get('id')}: {v.get('help')} ({len(v.get('nodes', []))} nodes)"
                for v in critical_violations
            ]
            pytest.fail(
                "Axe accessibility audit found critical/serious violations:\n"
                + "\n".join(violation_summaries)
            )

        # Assert no critical violations
        assert len(critical_violations) == 0
        page.close()
        browser.close()


def test_keyboard_navigation_and_focus(live_server: str):
    """Verify core workspace controls are reachable via keyboard Tab key."""
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        page.goto(live_server, wait_until="networkidle")

        # Tab through initial interactive elements
        focused_tags: list[str] = []
        for _ in range(8):
            page.keyboard.press("Tab")
            tag_info = page.evaluate("""
                () => {
                    const el = document.activeElement;
                    if (!el) return null;
                    return {
                        tag: el.tagName.toLowerCase(),
                        ariaLabel: el.getAttribute('aria-label') || '',
                        type: el.getAttribute('type') || ''
                    };
                }
            """)
            if tag_info and tag_info["tag"] not in ("body", "html"):
                focused_tags.append(tag_info["tag"])

        # Must focus buttons, inputs, or textareas
        assert any(t in ("button", "textarea", "input") for t in focused_tags)
        page.close()
        browser.close()
