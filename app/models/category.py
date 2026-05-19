"""
category.py — 카테고리 & 기사-카테고리 분류
  - categories
  - article_categories
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Float, ForeignKey, Index, Integer, String, Text, func, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, UUIDMixin


class Category(UUIDMixin, TimestampMixin, Base):
    """
    카테고리 계층 구조.
    parent_id = NULL → 대분류 (정치, 경제, 사회, 기술 …)
    parent_id = uuid → 소분류 (경제 > 주식, 경제 > 환율 …)
    depth는 애플리케이션 레이어에서 관리한다 (무한 depth 방지).
    """
    __tablename__ = "categories"
    __table_args__ = (
        Index("ix_categories_slug", "slug", unique=True),
        Index("ix_categories_parent", "parent_id"),
        Index("ix_categories_active", "is_active"),
    )

    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    icon_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(
        __import__("sqlalchemy").Boolean, default=True
    )

    # ── Self-referential ───────────────────────────────────────
    children: Mapped[list["Category"]] = relationship(
        "Category", back_populates="parent"
    )
    parent: Mapped[Optional["Category"]] = relationship(
        "Category", back_populates="children", remote_side="Category.id"
    )

    # ── Relations ──────────────────────────────────────────────
    article_categories: Mapped[list["ArticleCategory"]] = relationship(
        back_populates="category"
    )
    user_categories: Mapped[list["UserCategory"]] = relationship(
        back_populates="category"
    )


class ArticleCategory(UUIDMixin, Base):
    """
    기사-카테고리 N:M 연결.
    classified_by 로 분류 방식을 추적 → AI 전환 시 정확도 비교 가능.
    confidence_score 로 AI 신뢰도 저장.
    """
    __tablename__ = "article_categories"
    __table_args__ = (
        Index("ix_ac_article_category", "article_id", "category_id", unique=True),
        Index("ix_ac_category", "category_id"),
    )

    article_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("articles.id", ondelete="CASCADE"),
        nullable=False,
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="CASCADE"),
        nullable=False,
    )
    classified_by: Mapped[str] = mapped_column(
        String(20), nullable=False, default="rule",
        comment="rule | ai | manual"
    )
    confidence_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    article: Mapped["Article"] = relationship(back_populates="article_categories")
    category: Mapped["Category"] = relationship(back_populates="article_categories")


from .activity import UserCategory  # noqa: E402
from .news import Article  # noqa: E402