"""add client binding primitives

Revision ID: 0021
Revises: 0020
Create Date: 2026-07-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0021"
down_revision: str | None = "0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "client_telegram_identities",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clients.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("requested_public_name", sa.String(length=160), nullable=True),
        sa.Column("requested_phone", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('pending', 'active', 'revoked')", name="client_telegram_identity_status_valid"),
        sa.CheckConstraint(
            "(status = 'pending' AND client_id IS NULL AND requested_public_name IS NOT NULL) "
            "OR (status = 'active' AND client_id IS NOT NULL) OR status = 'revoked'",
            name="client_telegram_identity_state_consistent",
        ),
        sa.UniqueConstraint("owner_user_id", "telegram_user_id", name="uq_client_telegram_identities_owner_telegram"),
    )
    op.create_index(
        "uq_client_telegram_identities_owner_active_client",
        "client_telegram_identities",
        ["owner_user_id", "client_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active' AND client_id IS NOT NULL"),
    )

    op.create_table(
        "master_public_profile",
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("display_name", sa.String(length=160), nullable=False),
        sa.Column("public_contact", sa.String(length=160), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "master_link_tokens",
        sa.Column("token", sa.String(length=96), primary_key=True),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_master_link_tokens_owner_active", "master_link_tokens", ["owner_user_id", "revoked_at"])


def downgrade() -> None:
    op.drop_index("ix_master_link_tokens_owner_active", table_name="master_link_tokens")
    op.drop_table("master_link_tokens")
    op.drop_table("master_public_profile")
    op.drop_index("uq_client_telegram_identities_owner_active_client", table_name="client_telegram_identities")
    op.drop_table("client_telegram_identities")
