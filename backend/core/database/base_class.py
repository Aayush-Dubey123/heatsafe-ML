from collections.abc import Callable

from sqlalchemy import Connection, text
from sqlalchemy.orm import DeclarativeBase

# Tables owned by any installed extension (PostGIS spatial_ref_sys, tiger geocoder, topology, ...).
_EXTENSION_TABLES_SQL = text(
    """
    SELECT c.relname
    FROM pg_class c
    JOIN pg_depend d
      ON d.objid = c.oid
     AND d.classid = 'pg_class'::regclass
     AND d.deptype = 'e'
    WHERE c.relkind IN ('r', 'p', 'v', 'm', 'f')
    """
)


class Base(DeclarativeBase):
    """
    SQLAlchemy 2.0 Declarative Base class for all backend persistence entities.

    Provides common attribute metadata and identity hooks across models.
    """
    pass


def extension_owned_tables(connection: Connection) -> frozenset[str]:
    """
    List tables that belong to installed PostgreSQL extensions.

    These tables are created by extensions such as PostGIS, never by our models,
    so migrations must neither create nor drop them. SQLite has no extensions.

    Args:
        connection (Connection): Open database connection.

    Returns:
        frozenset[str]: Extension-owned table names (empty on non-PostgreSQL databases).
    """
    if connection.dialect.name != "postgresql":
        return frozenset()
    return frozenset(connection.execute(_EXTENSION_TABLES_SQL).scalars())


def migration_name_filter(connection: Connection) -> Callable[[str | None, str, object], bool]:
    """
    Build an Alembic `include_name` filter that ignores extension-owned tables.

    Prevents autogenerate from proposing to drop PostGIS tables like `spatial_ref_sys`.
    The lookup is deferred until Alembic first compares an object, so building the
    filter never opens a transaction that would swallow Alembic's own commit.

    Args:
        connection (Connection): Open database connection used to look up extension tables.

    Returns:
        Callable[[str | None, str, object], bool]: Filter returning False for extension tables.
    """
    cache: list[frozenset[str]] = []

    def include_name(name: str | None, type_: str, parent_names: object) -> bool:
        """
        Decide whether Alembic should compare one database object.

        Args:
            name (str | None): Object name reported by Alembic.
            type_ (str): Object kind, e.g. "table", "column", "index".
            parent_names (object): Alembic's parent-name mapping (unused).

        Returns:
            bool: False for extension-owned tables, True otherwise.
        """
        if type_ != "table":
            return True
        if not cache:
            cache.append(extension_owned_tables(connection))
        return name not in cache[0]

    return include_name
