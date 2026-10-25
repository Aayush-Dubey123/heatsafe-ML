import os
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from backend.core import logger

logging = logger(__name__)

# Resolve DATABASE_URL, falling back to local SQLite if unset or set to placeholder
_raw_url = os.getenv("HEATSAFE_DATABASE_URL") or os.getenv("DATABASE_URL")
if not _raw_url or "USER:PASSWORD" in _raw_url:
    DATABASE_URL: str = "sqlite:///./heatsafe.sqlite3"
else:
    DATABASE_URL = _raw_url

# Initialize SQLAlchemy engine with connection pool hardening
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
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
