"""issues, issue_keywords 테이블 + articles.issue_id

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-16
"""
from __future__ import annotations

import uuid
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "issues",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("representative_article_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("articles.id", ondelete="SET NULL"), nullable=True),
        sa.Column("category_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("categories.id", ondelete="SET NULL"), nullable=True),
        sa.Column("article_count", sa.Integer, nullable=False, server_default="1"),
        sa.Column("source_count", sa.Integer, nullable=False, server_default="1"),
        sa.Column("first_published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active",
                  comment="active | archived"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_issues_category_last_published", "issues",
                    ["category_id", "last_published_at"])
    op.create_index("ix_issues_status", "issues", ["status"])

    op.create_table(
        "issue_keywords",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("issue_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("issues.id", ondelete="CASCADE"), nullable=False),
        sa.Column("keyword_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("keywords.id", ondelete="CASCADE"), nullable=False),
        sa.Column("weight", sa.Float, nullable=False, server_default="0"),
    )
    op.create_index("ix_ik_issue_keyword", "issue_keywords",
                    ["issue_id", "keyword_id"], unique=True)
    op.create_index("ix_ik_keyword", "issue_keywords", ["keyword_id"])

    op.add_column("articles", sa.Column(
        "issue_id", postgresql.UUID(as_uuid=True),
        sa.ForeignKey("issues.id", ondelete="SET NULL"), nullable=True,
    ))
    op.create_index("ix_articles_issue", "articles", ["issue_id"])


def downgrade() -> None:
    op.drop_index("ix_articles_issue", "articles")
    op.drop_column("articles", "issue_id")
    op.drop_index("ix_ik_keyword", "issue_keywords")
    op.drop_index("ix_ik_issue_keyword", "issue_keywords")
    op.drop_table("issue_keywords")
    op.drop_index("ix_issues_status", "issues")
    op.drop_index("ix_issues_category_last_published", "issues")
    op.drop_table("issues")
