"""add lifecycle columns and release_events table

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Expand-only: the default makes existing rows DRAFT, and old code that does not
    # know these columns can still insert releases.
    op.add_column(
        "releases",
        sa.Column("status", sa.Text(), nullable=False, server_default="DRAFT"),
    )
    op.add_column(
        "releases",
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_check_constraint(
        op.f("ck_releases_status_valid"),
        "releases",
        "status IN ('DRAFT', 'PUBLISHED', 'ARCHIVED')",
    )
    op.create_check_constraint(
        op.f("ck_releases_published_at_matches_status"),
        "releases",
        "(status = 'DRAFT') = (published_at IS NULL)",
    )
    op.create_index(
        op.f("uq_releases_version_published"),
        "releases",
        ["version"],
        unique=True,
        postgresql_where=sa.text("status <> 'DRAFT'"),
    )

    op.create_table(
        "release_events",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("release_id", sa.BigInteger(), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_release_events")),
        sa.ForeignKeyConstraint(
            ["release_id"],
            ["releases.id"],
            name=op.f("fk_release_events_release_id_releases"),
        ),
        sa.CheckConstraint(
            "event_type IN ('CREATED', 'UPDATED', 'PUBLISHED', 'ARCHIVED')",
            name=op.f("ck_release_events_event_type_valid"),
        ),
    )
    op.create_index(
        op.f("ix_release_events_release_id"), "release_events", ["release_id"]
    )

    # Releases created before this migration get a CREATED event, so every release
    # has a history.
    op.execute(
        "INSERT INTO release_events (release_id, event_type, occurred_at) "
        "SELECT id, 'CREATED', created_at FROM releases"
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_release_events_release_id"), table_name="release_events")
    op.drop_table("release_events")
    op.drop_index(op.f("uq_releases_version_published"), table_name="releases")
    op.drop_constraint(
        op.f("ck_releases_published_at_matches_status"), "releases", type_="check"
    )
    op.drop_constraint(op.f("ck_releases_status_valid"), "releases", type_="check")
    op.drop_column("releases", "published_at")
    op.drop_column("releases", "status")
