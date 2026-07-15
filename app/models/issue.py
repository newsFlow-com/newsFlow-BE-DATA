"""
issue.py — 이슈 클러스터링 모델
  - issues         : 동일 사건을 다루는 기사들의 클러스터
  - issue_keywords : 이슈 대표 키워드 (article_keywords와 동일 N:M 패턴)
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, UUIDMixin


class Issue(UUIDMixin, Base):
    """
    같은 사건을 다루는 여러 매체 기사를 묶는 클러스터.
    키워드 Jaccard 유사도 기반으로 pipelines/issue_clusterer.py 가 배정하며,
    최초 배정 이후 재클러스터링은 하지 않는다 (title/category는 최초 기사 기준 고정).
    """
    __tablename__ = "issues"
    __table_args__ = (
        Index("ix_issues_category_last_published", "category_id", "last_published_at"),
        Index("ix_issues_status", "status"),
    )

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    representative_article_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("articles.id", ondelete="SET NULL"), nullable=True
    )
    category_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categories.id", ondelete="SET NULL"), nullable=True
    )
    article_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    source_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    first_published_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_published_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active", comment="active | archived"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    representative_article: Mapped[Optional["Article"]] = relationship(
        foreign_keys=[representative_article_id]
    )
    category: Mapped[Optional["Category"]] = relationship()
    articles: Mapped[list["Article"]] = relationship(
        back_populates="issue", foreign_keys="Article.issue_id"
    )
    issue_keywords: Mapped[list["IssueKeyword"]] = relationship(
        back_populates="issue", cascade="all, delete-orphan"
    )


class IssueKeyword(UUIDMixin, Base):
    """
    이슈-키워드 N:M 연결. article_keywords와 동일 패턴.
    weight로 클러스터 내 키워드 누적 중요도를 저장해 Jaccard 유사도 계산에 사용한다.
    """
    __tablename__ = "issue_keywords"
    __table_args__ = (
        Index("ix_ik_issue_keyword", "issue_id", "keyword_id", unique=True),
        Index("ix_ik_keyword", "keyword_id"),
    )

    issue_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("issues.id", ondelete="CASCADE"), nullable=False
    )
    keyword_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("keywords.id", ondelete="CASCADE"), nullable=False
    )
    weight: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    issue: Mapped["Issue"] = relationship(back_populates="issue_keywords")
    keyword: Mapped["Keyword"] = relationship()


from .category import Category  # noqa: E402
from .keyword import Keyword  # noqa: E402
from .news import Article  # noqa: E402
