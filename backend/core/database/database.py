from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.core import logger
from backend.core.config.settings import get_settings

logging = logger(__name__)

_settings = get_settings()
DATABASE_URL: str = _settings.database_url
# Fail fast instead of hanging forever when the database host is unreachable.
POSTGRES_CONNECT_TIMEOUT_SECONDS = 10

# Process-wide engine singleton with connection health checks.
engine = create_engine(
    DATABASE_URL,
    connect_args=(
        {"check_same_thread": False}
        if DATABASE_URL.startswith("sqlite")
        else {"connect_timeout": POSTGRES_CONNECT_TIMEOUT_SECONDS}
    ),
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """
    Provide transactional database session scope for dependency injection.

    Ensures proper cleanup and session closure after request lifecycle.

    Yields:
        Session: Active SQLAlchemy session instance.

    Raises:
        Exception: Re-raises unhandled database exceptions during execution.
    """
    logging.info("Executing database session acquisition")
    db: Session = SessionLocal()
    try:
        yield db
    except Exception as err:
        logging.error(f"Error in database session: {err}")
        db.rollback()
        raise
    finally:
        db.close()
