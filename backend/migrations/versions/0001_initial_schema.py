"""Initial schema: PostGIS extension and health check records.

Revision ID: 0001
Revises:
Create Date: 2026-11-09
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """
    Enable PostGIS (PostgreSQL only) and create the health_check_records table.

    PostGIS is skipped on SQLite, which is used only by the unit tests.
    """
    if op.get_bind().dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    op.create_table(
        "health_check_records",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("service_name", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_health_check_records_id"), "health_check_records", ["id"], unique=False)


def downgrade() -> None:
    """
    Drop the health_check_records table.

    The PostGIS extension is left installed because other schemas may depend on it.
    """
    op.drop_index(op.f("ix_health_check_records_id"), table_name="health_check_records")
    op.drop_table("health_check_records")
