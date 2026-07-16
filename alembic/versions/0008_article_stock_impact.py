"""article_stocks — 뉴스-주가 영향도 컬럼 추가

Revision ID: 0008
Revises: 0007
Create Date: 2026-07-16
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column("article_stocks", sa.Column("price_change_publish_day", sa.Float, nullable=True))
    op.add_column("article_stocks", sa.Column("price_change_3d", sa.Float, nullable=True))
    op.add_column("article_stocks", sa.Column("impact_analyzed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_as_impact_analyzed", "article_stocks", ["impact_analyzed_at"])


def downgrade() -> None:
    op.drop_index("ix_as_impact_analyzed", "article_stocks")
    op.drop_column("article_stocks", "impact_analyzed_at")
    op.drop_column("article_stocks", "price_change_3d")
    op.drop_column("article_stocks", "price_change_publish_day")
