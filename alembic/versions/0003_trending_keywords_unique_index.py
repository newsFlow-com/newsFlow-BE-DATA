"""trending_keywords: ix_tk_keyword_date unique=True

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-28
"""
from __future__ import annotations

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("ix_tk_keyword_date", table_name="trending_keywords")
    op.create_index(
        "ix_tk_keyword_date",
        "trending_keywords",
        ["keyword_id", "trend_date"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_tk_keyword_date", table_name="trending_keywords")
    op.create_index(
        "ix_tk_keyword_date",
        "trending_keywords",
        ["keyword_id", "trend_date"],
        unique=False,
    )
