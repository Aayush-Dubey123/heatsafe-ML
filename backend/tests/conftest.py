import os
import secrets
import shutil
import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest

# Configure the test environment BEFORE any backend module is imported, because
# settings and the database engine are created at import time.
_TMP_DIR = Path(tempfile.mkdtemp(prefix="heatsafe-test-"))
_SQLITE_URL = f"sqlite:///{(_TMP_DIR / 'test.sqlite3').as_posix()}"
TEST_DATABASE_URL = os.environ.get("HEATSAFE_TEST_DATABASE_URL") or _SQLITE_URL

os.environ["HEATSAFE_ENVIRONMENT"] = "test"
os.environ["HEATSAFE_DATABASE_URL"] = TEST_DATABASE_URL
os.environ["HEATSAFE_JWT_SECRET_KEY"] = secrets.token_urlsafe(48)  # random per run, never committed
os.environ["HEATSAFE_CORS_ORIGINS"] = "https://app.heatsafe.test"

BACKEND_DIR = Path(__file__).resolve().parents[1]


def alembic_config():  # type: ignore[no-untyped-def]
    """
    Build an Alembic config pointed at the test database.

    Returns:
        alembic.config.Config: Config using backend/alembic.ini and TEST_DATABASE_URL.
    """
    from alembic.config import Config

    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)
    config.attributes["configure_logger"] = False
    return config


@pytest.fixture(scope="session", autouse=True)
def migrated_database() -> Generator[None, None, None]:
    """
    Apply all Alembic migrations once per test session, then tear them down.

    Tests therefore exercise the real migration path instead of create_all().

    Yields:
        None: Control to the test session.
    """
    from alembic import command

    from backend.core.database.database import engine

    config = alembic_config()
    command.upgrade(config, "head")
    yield
    command.downgrade(config, "base")
    engine.dispose()
    shutil.rmtree(_TMP_DIR, ignore_errors=True)
