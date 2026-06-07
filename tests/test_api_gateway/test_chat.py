"""Test: /api/v1/chat basic conversation."""
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

from fastapi.testclient import TestClient
from api_gateway.core import app

client = TestClient(app)


def test_chat_empty_message():
    """Test: empty message returns error."""
    response = client.post("/api/v1/chat", json={"message": ""})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "error"
    assert "不能为空" in data["message"]
    print("✅ test_chat_empty_message passed")


def test_chat_unmatched_query():
    """Test: unmatched query returns unmatched status."""
    response = client.post("/api/v1/chat", json={"message": "zzzznotarealword12345"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("unmatched", "error")
    print("✅ test_chat_unmatched_query passed")
