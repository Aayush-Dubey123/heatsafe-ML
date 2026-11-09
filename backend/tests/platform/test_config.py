from datetime import timedelta

import jwt
import pytest
from pydantic import ValidationError

from backend.commons import auth
from backend.core.config.settings import Settings

POSTGRES_URL = "postgresql+psycopg://user@localhost:5432/heatsafe"
STRONG_SECRET = "x" * 40


def make_settings(**overrides: object) -> Settings:
    """
    Build Settings from explicit values only, ignoring the root .env file.
    """
    values: dict[str, object] = {"environment": "development", "database_url": POSTGRES_URL}
    values.update(overrides)
    return Settings(_env_file=None, **values)  # type: ignore[arg-type]


def test_missing_database_url_is_rejected(monkeypatch):
    """
    The app must refuse to start when HEATSAFE_DATABASE_URL is not configured.
    """
    monkeypatch.delenv("HEATSAFE_DATABASE_URL", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # type: ignore[call-arg]


def test_sqlite_rejected_outside_tests():
    """
    SQLite is a test-only database; development and production need PostgreSQL.
    """
    with pytest.raises(ValidationError, match="SQLite"):
        make_settings(database_url="sqlite:///./local.sqlite3")
    with pytest.raises(ValidationError, match="SQLite"):
        make_settings(environment="production", database_url="sqlite:///./local.sqlite3")


def test_non_postgres_url_rejected():
    """
    Only PostgreSQL URLs are accepted outside the test environment.
    """
    with pytest.raises(ValidationError, match="PostgreSQL"):
        make_settings(database_url="mysql://user@localhost/heatsafe")


def test_production_requires_strong_secret():
    """
    Production refuses a missing or short JWT secret.
    """
    with pytest.raises(ValidationError, match="JWT_SECRET_KEY"):
        make_settings(environment="production", jwt_secret_key=None)
    with pytest.raises(ValidationError, match="JWT_SECRET_KEY"):
        make_settings(environment="production", jwt_secret_key="too-short")  # noqa: S106 - deliberately weak test value


def test_production_rejects_wildcard_cors():
    """
    A wildcard CORS origin is not allowed in production.
    """
    with pytest.raises(ValidationError, match="Wildcard"):
        make_settings(environment="production", jwt_secret_key=STRONG_SECRET, cors_origins="*")


def test_valid_production_settings_and_cors_parsing():
    """
    A complete production configuration validates and splits comma-separated origins.
    """
    settings = make_settings(
        environment="production",
        jwt_secret_key=STRONG_SECRET,
        cors_origins="https://heatsafe.app, https://planner.heatsafe.app",
    )
    assert settings.cors_origins == ["https://heatsafe.app", "https://planner.heatsafe.app"]
    assert STRONG_SECRET not in repr(settings)


def test_token_round_trip():
    """
    A token created with the configured secret verifies and keeps its claims.
    """
    token = auth.create_access_token({"sub": "admin", "role": "SUPERADMIN"})
    claims = auth.verify_access_token(token)
    assert claims["sub"] == "admin"
    assert claims["role"] == "SUPERADMIN"


def test_tampered_and_expired_tokens_rejected():
    """
    Tokens with a bad signature or past expiry are rejected.
    """
    forged = jwt.encode({"sub": "admin"}, "attacker-secret-" + "y" * 32, algorithm="HS256")
    with pytest.raises(jwt.InvalidSignatureError):
        auth.verify_access_token(forged)

    expired = auth.create_access_token({"sub": "admin"}, expires_delta=timedelta(seconds=-1))
    with pytest.raises(jwt.ExpiredSignatureError):
        auth.verify_access_token(expired)


def test_auth_unusable_without_secret(monkeypatch):
    """
    With no configured secret there is no insecure fallback: token creation fails.
    """
    monkeypatch.setattr(auth, "get_settings", lambda: make_settings(jwt_secret_key=None))
    with pytest.raises(RuntimeError, match="JWT_SECRET_KEY"):
        auth.create_access_token({"sub": "admin"})


def test_empty_claims_rejected():
    """
    Creating a token without claims is refused.
    """
    with pytest.raises(ValueError):
        auth.create_access_token({})
