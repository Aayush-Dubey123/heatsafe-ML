from fastapi.testclient import TestClient

from backend.core.apis.api import app

client = TestClient(app)


def test_get_health():
    """
    Verify GET /api/v1/health returns HTTP 200 with healthy status and database connection.
    """
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "heatsafe-backend"
    assert data["database"] == "connected"
    assert "timestamp" in data


def test_post_health_ping():
    """
    Verify POST /api/v1/health/ping echoes client payload with HTTP 200.
    """
    payload = {
        "client_tag": "pytest-suite",
        "echo_message": "test-ping-ok",
    }
    response = client.post("/api/v1/health/ping", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["echo"] == "test-ping-ok"
