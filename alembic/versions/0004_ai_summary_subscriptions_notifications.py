"""ai_summary, subscriptions, user_notifications

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-30
"""
from __future__ import annotations

import uuid
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # 1. articles.ai_summary 컬럼 추가
    op.add_column("articles", sa.Column("ai_summary", sa.Text, nullable=True))

    # 2. subscriptions 테이블
    op.create_table(
        "subscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("subscription_type", sa.String(20), nullable=False,
                  comment="keyword | category"),
        sa.Column("value", sa.String(100), nullable=False,
                  comment="키워드 단어 또는 카테고리 slug"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_sub_user_type_value", "subscriptions",
        ["user_id", "subscription_type", "value"], unique=True
    )
    op.create_index("ix_sub_type_value_active", "subscriptions",
                    ["subscription_type", "value", "is_active"])

    # 3. user_notifications 테이블
    op.create_table(
        "user_notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("article_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("articles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("subscription_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("subscriptions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("is_read", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("sent_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_un_user_read", "user_notifications", ["user_id", "is_read"])
    op.create_index("ix_un_article", "user_notifications", ["article_id"])
    op.create_index("ix_un_sent", "user_notifications", ["sent_at"])


def downgrade() -> None:
    op.drop_table("user_notifications")
    op.drop_table("subscriptions")
    op.drop_column("articles", "ai_summary")
