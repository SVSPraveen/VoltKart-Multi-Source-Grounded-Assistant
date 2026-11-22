"""tests/e2e/conftest.py - Shared fixtures for Playwright browser and server testing."""

from __future__ import annotations

import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent.parent


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
