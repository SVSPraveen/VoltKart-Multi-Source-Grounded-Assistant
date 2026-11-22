"""tests/unit/test_api_streaming.py - Integration test for SSE streaming API and chat endpoints.

Verifies:
1. POST /api/chats and GET /api/chats create and list sessions.
2. POST /api/chats/{id}/messages streams Server-Sent Events (status, citation, answer, done).
3. Stored message history persists in SQLite with status and metadata.
4. GET /api/chats/{id}/export.pdf returns HTTP 200 with application/pdf.
"""

from __future__ import annotations

import json

from starlette.testclient import TestClient

from backend.api import app
from backend.storage import init_sqlite_db, reset_storage


def test_chat_lifecycle_and_streaming_sse():
    """Test full chat lifecycle: create, stream message via SSE, retrieve messages, and export PDF."""
    reset_storage()
    init_sqlite_db()

    client = TestClient(app)

    # 1. Health check
    res_health = client.get("/api/health")
    assert res_health.status_code == 200
    assert res_health.json() == {"status": "ok"}

    # 2. Create new chat
    res_chat = client.post("/api/chats", json={"title": "Streaming Test Chat"})
    assert res_chat.status_code == 200
    chat_data = res_chat.json()
    chat_id = chat_data["chat_id"]
    assert chat_id.startswith("chat_")

    # 3. List chats
    res_list = client.get("/api/chats")
    assert res_list.status_code == 200
    chats = res_list.json()
    assert any(c["chat_id"] == chat_id for c in chats)

    # 4. Stream message via SSE
    payload = {
        "content": "What is the return window for Gold members?",
        "web_enabled": False,
    }
    with client.stream("POST", f"/api/chats/{chat_id}/messages", json=payload) as response:
        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")

        events: list[tuple[str, dict]] = []
        current_event = None

        for line in response.iter_lines():
            if line.startswith("event:"):
                current_event = line.replace("event:", "").strip()
            elif line.startswith("data:"):
                raw_data = line.replace("data:", "").strip()
                data = json.loads(raw_data)
                events.append((current_event, data))
                current_event = None

        # Verify event stream structure
        event_names = [e[0] for e in events]
        assert "status" in event_names
        assert "answer" in event_names
        assert "done" in event_names

        # Check answer event content
        answer_events = [e[1] for e in events if e[0] == "answer"]
        assert len(answer_events) == 1
        assert "30" in answer_events[0]["content"]

    # 5. Retrieve stored message history
    res_msgs = client.get(f"/api/chats/{chat_id}/messages")
    assert res_msgs.status_code == 200
    msgs = res_msgs.json()["messages"]
    assert len(msgs) >= 2  # user and assistant
    assert msgs[0]["role"] == "user"
    assert msgs[1]["role"] == "assistant"
    assert msgs[1]["status"] == "completed"

    # 6. Test PDF export endpoint
    res_pdf = client.get(f"/api/chats/{chat_id}/export.pdf")
    assert res_pdf.status_code == 200
    assert res_pdf.headers["content-type"] == "application/pdf"
    assert res_pdf.content.startswith(b"%PDF")
