"""sentiment columns + api_keys table

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-30
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("articles", sa.Column("sentiment", sa.String(20), nullable=True))
    op.add_column("articles", sa.Column("sentiment_score", sa.Float, nullable=True))
    op.create_index("ix_articles_sentiment", "articles", ["sentiment"])

    op.create_table(
        "api_keys",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True),
                  primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("key_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("client_name", sa.String(100), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("rate_limit_per_hour", sa.Integer, nullable=False,
                  server_default=sa.text("1000")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_api_keys_hash", "api_keys", ["key_hash"])
    op.create_index("ix_api_keys_active", "api_keys", ["is_active"])


def downgrade() -> None:
    op.drop_index("ix_api_keys_active", "api_keys")
    op.drop_index("ix_api_keys_hash", "api_keys")
    op.drop_table("api_keys")
    op.drop_index("ix_articles_sentiment", "articles")
    op.drop_column("articles", "sentiment_score")
    op.drop_column("articles", "sentiment")
