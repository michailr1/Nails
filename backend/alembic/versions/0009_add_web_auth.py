"""add web auth challenge and session tables

Revision ID: 0009
Revises: 0008
Create Date: 2026-07-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "web_login_challenges",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("browser_token_hash", sa.String(length=64), nullable=False),
        sa.Column("pending_scope_hash", sa.String(length=64), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("request_ip_hash", sa.String(length=64), nullable=False),
        sa.Column("user_agent_hash", sa.String(length=64), nullable=True),
        sa.Column("request_id", sa.String(length=128), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code_hash"),
    )
    op.create_index(
        "ix_web_login_challenges_status_expires",
        "web_login_challenges",
        ["status", "expires_at"],
    )
    op.create_index(
        "ix_web_login_challenges_ip_created",
        "web_login_challenges",
        ["request_ip_hash", "created_at"],
    )
    op.create_index(
        "uq_web_login_challenges_pending_scope",
        "web_login_challenges",
        ["pending_scope_hash"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
    )

    op.create_table(
        "web_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("idle_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "absolute_expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rotation_counter", sa.Integer(), nullable=False),
        sa.Column("created_ip_hash", sa.String(length=64), nullable=False),
        sa.Column("last_ip_hash", sa.String(length=64), nullable=False),
        sa.Column("user_agent_hash", sa.String(length=64), nullable=True),
        sa.Column("request_id", sa.String(length=128), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(
        "ix_web_sessions_user_active",
        "web_sessions",
        ["user_id", "revoked_at"],
    )
    op.create_index(
        "ix_web_sessions_expiry",
        "web_sessions",
        ["idle_expires_at", "absolute_expires_at"],
    )

    op.create_table(
        "web_auth_rate_buckets",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("scope_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "window_started_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "action",
            "scope_hash",
            name="uq_web_auth_rate_bucket_scope",
        ),
    )
    op.create_index(
        "ix_web_auth_rate_buckets_window",
        "web_auth_rate_buckets",
        ["window_started_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_web_auth_rate_buckets_window",
        table_name="web_auth_rate_buckets",
    )
    op.drop_table("web_auth_rate_buckets")
    op.drop_index("ix_web_sessions_expiry", table_name="web_sessions")
    op.drop_index("ix_web_sessions_user_active", table_name="web_sessions")
    op.drop_table("web_sessions")
    op.drop_index(
        "uq_web_login_challenges_pending_scope",
        table_name="web_login_challenges",
    )
    op.drop_index(
        "ix_web_login_challenges_ip_created",
        table_name="web_login_challenges",
    )
    op.drop_index(
        "ix_web_login_challenges_status_expires",
        table_name="web_login_challenges",
    )
    op.drop_table("web_login_challenges")
