"""add article_views table

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-27
"""
from __future__ import annotations

import uuid
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "article_views",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("article_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("articles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("viewed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_av_user_article", "article_views", ["user_id", "article_id"], unique=True)
    op.create_index("ix_av_user_viewed", "article_views", ["user_id", "viewed_at"])


def downgrade() -> None:
    op.drop_index("ix_av_user_viewed", table_name="article_views")
    op.drop_index("ix_av_user_article", table_name="article_views")
    op.drop_table("article_views")
