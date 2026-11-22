"""tests/unit/test_no_hardcode.py - Verify the no-hardcode scanner."""

from pathlib import Path

import pytest

from scripts.check_no_hardcode import scan_file


def test_scan_file_clean(tmp_path: Path):
    clean_file = tmp_path / "clean.py"
    clean_file.write_text("def calculate_total(items):\n    return sum(x.price for x in items)\n")
    violations = scan_file(clean_file)
    assert violations == []


@pytest.mark.parametrize(
    "bad_content, expected_match",
    [
        ("store_id = 'S04'", "Store ID"),
        ("store_id = 'S07'", "Store ID"),
        ("name = 'VoltKart Connaught Place'", "voltkart"),
        ("store = 'Baner'", "Baner"),
        ("manager = 'Ritu Menon'", "Ritu Menon"),
        ("if customer == 'Aarav Kulkarni': pass", "Aarav Kulkarni"),
        ("customer_id = 'C0001'", "Customer ID"),
        ("order_id = 'O00050'", "Order ID"),
        ("product = 'Nexora X12 Pro'", "Nexora"),
        ("doc = 'VoltKart_Return_Policy_2025.txt'", "voltkart"),
    ],
)
def test_scan_file_catches_violations(tmp_path: Path, bad_content: str, expected_match: str):
    dirty_file = tmp_path / "dirty.py"
    dirty_file.write_text(bad_content)
    violations = scan_file(dirty_file)
    assert len(violations) >= 1
    assert any(expected_match.lower() in v.lower() for v in violations)


def test_frontend_components_contain_no_raw_hex_colors():
    """Verify AGENTS.md Section 4: All colour comes from design tokens, no raw hex in components."""
    import glob
    import re

    root = Path(__file__).resolve().parent.parent.parent
    tsx_files = glob.glob(str(root / "frontend" / "src" / "**" / "*.tsx"), recursive=True)
    assert len(tsx_files) > 0, "No TSX frontend files found to audit."

    hex_violations: list[str] = []
    for fpath in tsx_files:
        content = Path(fpath).read_text(encoding="utf-8", errors="replace")
        matches = re.findall(r"#[0-9a-fA-F]{3,8}\b", content)
        if matches:
            hex_violations.append(f"{Path(fpath).name}: {matches}")

    assert not hex_violations, f"Raw hex colors found in frontend components: {hex_violations}"
