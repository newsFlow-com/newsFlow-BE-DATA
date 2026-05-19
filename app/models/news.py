"""
news.py — 뉴스 소스 & 기사 관련 모델
  - sources
  - articles
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger, DateTime, ForeignKey, Index,
    Integer, String, Text, func
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, UUIDMixin


class Source(UUIDMixin, TimestampMixin, Base):
    """
    뉴스 수집 소스.
    feed_type 으로 수집기를 라우팅 → 수집기 교체 시 코드 변경 없음.
    tier로 국내/국제 구분.
    """
    __tablename__ = "sources"
    __table_args__ = (
        Index("ix_sources_domain", "domain", unique=True),
        Index("ix_sources_active_tier", "is_active", "tier"),
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    domain: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    feed_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    feed_type: Mapped[str] = mapped_column(
        String(20), nullable=False,
        comment="rss | api | crawl"
    )
    country_code: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    language_code: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    tier: Mapped[str] = mapped_column(
        String(20), nullable=False, default="domestic",
        comment="domestic | international"
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_fetched_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ── Relations ──────────────────────────────────────────────
    articles: Mapped[list["Article"]] = relationship(back_populates="source")
    collect_logs: Mapped[list["CollectLog"]] = relationship(back_populates="source")


class Article(UUIDMixin, TimestampMixin, Base):
    """
    수집된 뉴스 기사 원문 및 메타데이터.
    status 로 관리자가 노출 여부를 제어한다.
    view_count는 Redis incr → 배치 반영 방식으로 업데이트한다.
    """
    __tablename__ = "articles"
    __table_args__ = (
        Index("ix_articles_url", "original_url", unique=True),
        Index("ix_articles_published", "published_at"),
        Index("ix_articles_source_published", "source_id", "published_at"),
        Index("ix_articles_status", "status"),
        Index("ix_articles_language", "language_code"),
    )

    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sources.id", ondelete="SET NULL"),
        nullable=True
    )
    original_url: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    thumbnail_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    author: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    language_code: Mapped[str] = mapped_column(String(10), nullable=False, default="ko")

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active",
        comment="active | hidden | deleted"
    )
    view_count: Mapped[int] = mapped_column(Integer, default=0)
    published_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # ── Relations ──────────────────────────────────────────────
    source: Mapped[Optional["Source"]] = relationship(back_populates="articles")
    article_categories: Mapped[list["ArticleCategory"]] = relationship(
        back_populates="article", cascade="all, delete-orphan"
    )
    article_keywords: Mapped[list["ArticleKeyword"]] = relationship(
        back_populates="article", cascade="all, delete-orphan"
    )
    article_stocks: Mapped[list["ArticleStock"]] = relationship(
        back_populates="article", cascade="all, delete-orphan"
    )
    daily_stats: Mapped[list["DailyArticleStat"]] = relationship(
        back_populates="article", cascade="all, delete-orphan"
    )
    bookmarks: Mapped[list["Bookmark"]] = relationship(
        back_populates="article", cascade="all, delete-orphan"
    )
    share_logs: Mapped[list["ShareLog"]] = relationship(back_populates="article")
    reports: Mapped[list["ArticleReport"]] = relationship(
        back_populates="article", cascade="all, delete-orphan"
    )
    quality_logs: Mapped[list["ContentQualityLog"]] = relationship(
        back_populates="article", cascade="all, delete-orphan"
    )


# 순환 참조 방지
from sqlalchemy import Boolean  # noqa: E402 — Boolean은 Source에서도 필요

from .activity import Bookmark, ShareLog  # noqa: E402
from .admin import AdminLog, ArticleReport, CollectLog, ContentQualityLog  # noqa: E402
from .category import ArticleCategory  # noqa: E402
from .keyword import ArticleKeyword  # noqa: E402
from .stats import DailyArticleStat  # noqa: E402
from .stock import ArticleStock  # noqa: E402