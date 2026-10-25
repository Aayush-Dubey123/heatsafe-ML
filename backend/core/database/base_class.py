from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """
    SQLAlchemy 2.0 Declarative Base class for all backend persistence entities.

    Provides common attribute metadata and identity hooks across models.
    """
    pass
