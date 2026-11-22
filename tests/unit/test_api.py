"""tests/unit/test_api.py - Unit tests for FastAPI ingestion HTTP endpoints.

Verifies /api/health, /api/upload, /api/ingestion-summary, /api/schema-card, and /api/reset.
"""

from fastapi.testclient import TestClient

from backend.api import app
from backend.storage import reset_storage

client = TestClient(app)


def setup_function():
    reset_storage()


def test_health_check_endpoint():
    """Verify health endpoint returns status ok."""
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_upload_and_summary_endpoint():
    """Verify file upload via multipart/form-data and summary retrieval."""
    csv_bytes = b"product_code,price\nPRD1,499.0\nPRD2,899.0\n"
    files = [
        ("files", ("products_test.csv", csv_bytes, "text/csv")),
    ]

    upload_resp = client.post("/api/upload", files=files)
    assert upload_resp.status_code == 200
    data = upload_resp.json()
    assert len(data["tables"]) == 1
    assert data["tables"][0]["table_name"] == "products_test"
    assert data["tables"][0]["row_count"] == 2

    # Verify GET /api/ingestion-summary returns matching state
    sum_resp = client.get("/api/ingestion-summary")
    assert sum_resp.status_code == 200
    sum_data = sum_resp.json()
    assert len(sum_data["tables"]) == 1


def test_schema_card_endpoint():
    """Verify /api/schema-card returns markdown summary."""
    resp = client.get("/api/schema-card")
    assert resp.status_code == 200
    assert "schema_card" in resp.json()
    assert "# Database Schema Card" in resp.json()["schema_card"]


def test_reset_endpoint():
    """Verify /api/reset clears state."""
    reset_resp = client.post("/api/reset")
    assert reset_resp.status_code == 200
    assert reset_resp.json() == {"status": "cleared"}
