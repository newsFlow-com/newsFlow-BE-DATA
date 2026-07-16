"""issues — 속보 알림 발송 여부 마킹 컬럼 추가

Revision ID: 0009
Revises: 0008
Create Date: 2026-07-16
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column("issues", sa.Column("breaking_notified_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_issues_breaking_notified", "issues", ["breaking_notified_at"])


def downgrade() -> None:
    op.drop_index("ix_issues_breaking_notified", "issues")
    op.drop_column("issues", "breaking_notified_at")
