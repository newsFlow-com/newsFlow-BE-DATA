"""
keyword.py — 키워드 & 트렌드
  - keywords
  - article_keywords
  - trending_keywords
"""
import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    Date, DateTime, Float, ForeignKey, Index,
    Integer, String, func
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, UUIDMixin


class Keyword(UUIDMixin, Base):
    """
    정규화된 키워드 사전.
    word_normalized 로 형태소 분석 결과를 저장해 중복 집계를 방지한다.
    """
    __tablename__ = "keywords"
    __table_args__ = (
        Index("ix_keywords_word", "word", unique=True),
        Index("ix_keywords_normalized", "word_normalized"),
        Index("ix_keywords_language", "language_code"),
    )

    word: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    word_normalized: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    language_code: Mapped[str] = mapped_column(String(10), nullable=False, default="ko")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    article_keywords: Mapped[list["ArticleKeyword"]] = relationship(
        back_populates="keyword"
    )
    trending_keywords: Mapped[list["TrendingKeyword"]] = relationship(
        back_populates="keyword"
    )


class ArticleKeyword(UUIDMixin, Base):
    """
    기사-키워드 N:M 연결.
    relevance_score 로 키워드 중요도를 수치화한다.
    extracted_by 로 추출 방식을 추적해 AI 정확도 개선에 활용한다.
    """
    __tablename__ = "article_keywords"
    __table_args__ = (
        Index("ix_ak_article_keyword", "article_id", "keyword_id", unique=True),
        Index("ix_ak_keyword", "keyword_id"),
        Index("ix_ak_relevance", "relevance_score"),
    )

    article_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("articles.id", ondelete="CASCADE"),
        nullable=False,
    )
    keyword_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("keywords.id", ondelete="CASCADE"),
        nullable=False,
    )
    relevance_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    extracted_by: Mapped[str] = mapped_column(
        String(20), nullable=False, default="tfidf",
        comment="tfidf | ai | rule"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    article: Mapped["Article"] = relationship(back_populates="article_keywords")
    keyword: Mapped["Keyword"] = relationship(back_populates="article_keywords")


class TrendingKeyword(UUIDMixin, Base):
    """
    일별/실시간 급등 키워드.
    source 로 PyTrends vs 내부 집계를 구분한다.
    rank 는 해당 날짜 기준 순위.
    search_volume_index 는 PyTrends 0-100 지수.
    """
    __tablename__ = "trending_keywords"
    __table_args__ = (
        Index("ix_tk_date_rank", "trend_date", "rank"),
        Index("ix_tk_keyword_date", "keyword_id", "trend_date", unique=True),
        Index("ix_tk_type", "trend_type"),
    )

    keyword_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("keywords.id", ondelete="CASCADE"),
        nullable=False,
    )
    trend_date: Mapped[date] = mapped_column(Date, nullable=False)
    trend_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="daily",
        comment="daily | realtime"
    )
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    search_volume_index: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pytrends",
        comment="pytrends | internal"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    keyword: Mapped["Keyword"] = relationship(back_populates="trending_keywords")


from .news import Article  # noqa: E402