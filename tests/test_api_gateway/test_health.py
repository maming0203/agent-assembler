"""Test: /api/v1/health endpoint."""
import os
import sys

# Ensure api_gateway is importable from project root
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

from fastapi.testclient import TestClient
from api_gateway.core import app

client = TestClient(app)


def test_health_returns_ok():
    """Test: /api/v1/health returns status ok and version."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data
    print("✅ test_health_returns_ok passed")


def test_health_is_get_only():
    """Test: /api/v1/health only accepts GET."""
    response = client.post("/api/v1/health")
    assert response.status_code == 405  # Method Not Allowed
    print("✅ test_health_is_get_only passed")
