import uuid

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from fastapi.testclient import TestClient

from backend.core.apis.api import app, create_app
from backend.core.cruds.health_crud import HealthCRUD
from backend.core.database.base_class import Base, migration_name_filter
from backend.core.database.database import engine

client = TestClient(app)
ALLOWED_ORIGIN = "https://app.heatsafe.test"


def assert_error_envelope(response, status_code: int, code: str) -> dict:
    """
    Check a response uses the uniform error envelope and return its error body.
    """
    assert response.status_code == status_code
    body = response.json()
    assert set(body) == {"error"}
    error = body["error"]
    assert error["code"] == code
    assert isinstance(error["message"], str) and error["message"]
    assert error["request_id"] == response.headers["X-Request-ID"]
    return error


def test_request_id_generated_and_security_headers_set():
    """
    Every response carries a generated request ID and the security headers.
    """
    response = client.get("/api/v1/health")
    uuid.UUID(response.headers["X-Request-ID"])
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert "default-src 'none'" in response.headers["Content-Security-Policy"]
    assert "Strict-Transport-Security" not in response.headers  # HSTS only in production


def test_docs_page_not_blocked_by_csp():
    """
    Swagger UI still loads: the strict API CSP is not applied to /docs.
    """
    response = client.get("/docs")
    assert response.status_code == 200
    assert "Content-Security-Policy" not in response.headers


def test_valid_inbound_request_id_is_reused_and_invalid_is_replaced():
    """
    A well-formed X-Request-ID is echoed; a malformed one is replaced.
    """
    response = client.get("/api/v1/health", headers={"X-Request-ID": "trace-abc-123"})
    assert response.headers["X-Request-ID"] == "trace-abc-123"

    response = client.get("/api/v1/health", headers={"X-Request-ID": "bad id\nwith injection"})
    uuid.UUID(response.headers["X-Request-ID"])


def test_unknown_route_returns_404_envelope():
    """
    Unknown paths return the uniform envelope with a not_found code.
    """
    assert_error_envelope(client.get("/api/v1/does-not-exist"), 404, "not_found")


def test_validation_error_envelope_does_not_echo_input():
    """
    Invalid bodies return 422 with field details but never the submitted value.
    """
    secret_like = "Z" * 200
    response = client.post("/api/v1/health/ping", json={"echo_message": secret_like})
    error = assert_error_envelope(response, 422, "validation_error")
    assert error["details"][0]["loc"] == ["body", "echo_message"]
    assert secret_like not in response.text


def test_controller_http_exception_keeps_status(monkeypatch):
    """
    A controller's 503 reaches the client as a 503 envelope, not a generic 500.
    """

    def failing_heartbeat(*args, **kwargs):
        raise RuntimeError("connection refused to db-host:5432")

    monkeypatch.setattr(HealthCRUD, "record_heartbeat", failing_heartbeat)
    response = client.get("/api/v1/health")
    assert_error_envelope(response, 503, "service_unavailable")
    assert "db-host" not in response.text


def test_unhandled_exception_hidden_behind_generic_500():
    """
    Uncaught exceptions return a generic 500 envelope with no internal details.
    """
    fresh_app = create_app()

    @fresh_app.get("/boom")
    def boom() -> None:
        raise RuntimeError("internal path C:/secret/config leaked")

    response = TestClient(fresh_app, raise_server_exceptions=False).get("/boom")
    assert response.status_code == 500
    body = response.json()["error"]
    assert body["code"] == "internal_server_error"
    assert body["message"] == "Internal Server Error"
    assert "secret" not in response.text


def test_cors_allows_only_configured_origins_without_credentials():
    """
    Configured origins get CORS headers; others do not; credentials stay disabled.
    """
    preflight = {"Access-Control-Request-Method": "GET"}
    allowed = client.options("/api/v1/health", headers={"Origin": ALLOWED_ORIGIN, **preflight})
    assert allowed.headers["access-control-allow-origin"] == ALLOWED_ORIGIN
    assert "access-control-allow-credentials" not in allowed.headers

    blocked = client.options("/api/v1/health", headers={"Origin": "https://evil.example", **preflight})
    assert "access-control-allow-origin" not in blocked.headers


def test_migrations_match_models():
    """
    The migrated schema matches the SQLAlchemy models: no pending migration is missing.
    """
    with engine.connect() as connection:
        context = MigrationContext.configure(connection, opts={"include_name": migration_name_filter(connection)})
        diff = compare_metadata(context, Base.metadata)
    assert diff == []
