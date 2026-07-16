"""source_sentiment_stats — 매체×카테고리별 일별 감성 집계 테이블

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-16
"""
from __future__ import annotations

import uuid
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "source_sentiment_stats",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("source_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("sources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("category_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("categories.id", ondelete="CASCADE"), nullable=True),
        sa.Column("stat_date", sa.Date, nullable=False),
        sa.Column("positive_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("negative_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("neutral_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_sss_source_category_date", "source_sentiment_stats",
        ["source_id", "category_id", "stat_date"], unique=True,
    )
    op.create_index("ix_sss_date", "source_sentiment_stats", ["stat_date"])


def downgrade() -> None:
    op.drop_index("ix_sss_date", "source_sentiment_stats")
    op.drop_index("ix_sss_source_category_date", "source_sentiment_stats")
    op.drop_table("source_sentiment_stats")
