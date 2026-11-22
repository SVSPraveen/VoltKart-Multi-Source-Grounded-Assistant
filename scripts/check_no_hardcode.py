#!/usr/bin/env python3
"""scripts/check_no_hardcode.py - Enforce Rule 4 and REVIEW.md R-005.

Scans backend/ and frontend/src/ to ensure application code contains NO
sample-specific hardcoded values (VoltKart, store IDs, customer names,
document titles, or sample order numbers).
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Targeted forbidden sample-specific strings and patterns
# Sourced from VoltKart_Sample_Bundle tables and documents
FORBIDDEN_PATTERNS: list[tuple[str, str, bool]] = [
    # (Label, Pattern, Case-insensitive)
    ("Brand name", r"\bvoltkart\b", True),
    ("Brand warranty", r"\bvoltcare\b", True),
    ("Store ID S01", r"\bS01\b", False),
    ("Store ID S02", r"\bS02\b", False),
    ("Store ID S03", r"\bS03\b", False),
    ("Store ID S04", r"\bS04\b", False),
    ("Store ID S05", r"\bS05\b", False),
    ("Store ID S06", r"\bS06\b", False),
    ("Store: Connaught Place", r"\bConnaught Place\b", True),
    ("Store: Hitech City", r"\bHitech City\b", True),
    ("Store: Salt Lake", r"\bSalt Lake\b", True),
    ("Store: Andheri", r"\bAndheri\b", True),
    ("Store: Anna Nagar", r"\bAnna Nagar\b", True),
    ("Store: Indiranagar", r"\bIndiranagar\b", True),
    ("Customer: Aarav Kulkarni", r"\bAarav Kulkarni\b", True),
    ("Customer: Ishaan Sharma", r"\bIshaan Sharma\b", True),
    ("Customer: Varun Mishra", r"\bVarun Mishra\b", True),
    ("Customer: Kabir Kapoor", r"\bKabir Kapoor\b", True),
    ("Customer: Kavya Kapoor", r"\bKavya Kapoor\b", True),
    ("Customer: Vikram Sethi", r"\bVikram Sethi\b", True),
    ("Customer: Ananya Rao", r"\bAnanya Rao\b", True),
    ("Sample Customer ID C0118", r"\bC0118\b", False),
    ("Sample Customer ID C0112", r"\bC0112\b", False),
    ("Sample Customer ID C0052", r"\bC0052\b", False),
    ("Sample Customer ID C0037", r"\bC0037\b", False),
    ("Sample Customer ID C0030", r"\bC0030\b", False),
    ("Product: Nexora X12 Pro", r"\bNexora X12 Pro\b", True),
    ("Product: Auralis Pods Max ANC", r"\bAuralis Pods Max ANC\b", True),
    ("Doc: Return Policy title", r"VoltKart_Return_Policy", True),
    ("Doc: JD ML Engineer title", r"JD_ML_Engineer", True),
    ("Doc: Warranty Terms title", r"VoltKart_Warranty_Terms", True),
    ("Doc: Store Operations Notice", r"VoltKart_Store_Operations_Notice", True),
    ("Sample Order ID O00174", r"\bO00174\b", False),
    ("Sample Order ID O00351", r"\bO00351\b", False),
    ("Sample Order ID O00485", r"\bO00485\b", False),
    ("Sample Order ID O00663", r"\bO00663\b", False),
]

TEXT_EXTENSIONS = {
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".html",
    ".css",
    ".json",
    ".sql",
    ".yaml",
    ".yml",
    ".md",
    ".txt",
}

IGNORED_DIRS = {
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    "node_modules",
    ".git",
    ".venv",
}


def scan_file(file_path: Path) -> list[str]:
    """Scan a single file for forbidden hardcoded strings."""
    violations: list[str] = []
    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        return [f"Could not read {file_path}: {exc}"]

    lines = content.splitlines()
    for line_idx, line in enumerate(lines, start=1):
        for label, pattern, ignore_case in FORBIDDEN_PATTERNS:
            flags = re.IGNORECASE if ignore_case else 0
            if re.search(pattern, line, flags=flags):
                snippet = line.strip()
                if len(snippet) > 80:
                    snippet = snippet[:77] + "..."
                violations.append(
                    f"{file_path}:{line_idx} - [{label}] matched '{pattern}': '{snippet}'"
                )
    return violations


def scan_directories(directories: list[Path], verbose: bool = False) -> tuple[int, list[str]]:
    """Scan all target directories for violations."""
    all_violations: list[str] = []
    file_count = 0

    for directory in directories:
        if not directory.exists():
            continue
        for path in directory.rglob("*"):
            if not path.is_file():
                continue
            if any(part in IGNORED_DIRS for part in path.parts):
                continue
            if path.suffix.lower() not in TEXT_EXTENSIONS:
                continue

            file_count += 1
            if verbose:
                print(f"Scanning: {path}")
            violations = scan_file(path)
            all_violations.extend(violations)

    return file_count, all_violations


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify no sample-specific strings are hardcoded in application code."
    )
    parser.add_argument(
        "--target-dirs",
        nargs="+",
        default=["backend", "frontend/src"],
        help="Directories to scan (default: backend, frontend/src)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Print each scanned file",
    )
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent
    target_paths = [project_root / d for d in args.target_dirs]

    file_count, violations = scan_directories(target_paths, verbose=args.verbose)

    if violations:
        print(f"FAILED: Found {len(violations)} hardcoded sample violation(s):", file=sys.stderr)
        for v in violations:
            print(f"  - {v}", file=sys.stderr)
        return 1

    print(
        f"PASS: No hardcoded sample entities found in {[str(p.relative_to(project_root)) for p in target_paths]} "
        f"({file_count} files scanned)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
