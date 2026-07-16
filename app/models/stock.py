"""
stock.py — 주식 종목 & 가격 연계
  - stocks
  - article_stocks
  - stock_prices
"""
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    BigInteger, Boolean, Date, DateTime, Float,
    ForeignKey, Index, Numeric, String, func
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, UUIDMixin


class Stock(UUIDMixin, TimestampMixin, Base):
    """
    상장 종목 마스터.
    market 컬럼으로 국내(KOSPI/KOSDAQ)/해외(NYSE/NASDAQ) 구분.
    sector 는 산업군 분류 (기사 카테고리와 연계 가능).
    """
    __tablename__ = "stocks"
    __table_args__ = (
        Index("ix_stocks_ticker", "ticker", unique=True),
        Index("ix_stocks_market_active", "market", "is_active"),
        Index("ix_stocks_sector", "sector"),
    )

    ticker: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    market: Mapped[str] = mapped_column(
        String(20), nullable=False,
        comment="KOSPI | KOSDAQ | NYSE | NASDAQ"
    )
    country_code: Mapped[str] = mapped_column(String(10), nullable=False, default="KR")
    sector: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    article_stocks: Mapped[list["ArticleStock"]] = relationship(
        back_populates="stock", cascade="all, delete-orphan"
    )
    stock_prices: Mapped[list["StockPrice"]] = relationship(
        back_populates="stock", cascade="all, delete-orphan"
    )


class ArticleStock(UUIDMixin, Base):
    """
    기사-종목 연결.
    mention_score: 기사에서 해당 종목이 얼마나 중요하게 언급됐는지 0-1 점수.
    linked_by: AI가 연결했는지, 규칙 기반인지 추적.

    영향도 분석(pipelines/impact_analyzer.py)이 채우는 필드:
      price_change_publish_day: 발행일 기준 가장 가까운 거래일의 주가 등락률(%)
      price_change_3d: 발행일 종가 → 3거래일 후 종가까지의 누적 변동률(%)
      impact_analyzed_at: price_change_3d 까지 계산 완료된 시각 (NULL이면 재처리 대상)

    ⚠ 인과관계를 증명하는 지표가 아니라 "발행 시점 전후 주가 동조화" 참고 지표다.
    """
    __tablename__ = "article_stocks"
    __table_args__ = (
        Index("ix_as_article_stock", "article_id", "stock_id", unique=True),
        Index("ix_as_stock", "stock_id"),
        Index("ix_as_impact_analyzed", "impact_analyzed_at"),
    )

    article_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("articles.id", ondelete="CASCADE"),
        nullable=False,
    )
    stock_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stocks.id", ondelete="CASCADE"),
        nullable=False,
    )
    mention_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    linked_by: Mapped[str] = mapped_column(
        String(20), nullable=False, default="rule",
        comment="ai | rule"
    )
    price_change_publish_day: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    price_change_3d: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    impact_analyzed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    article: Mapped["Article"] = relationship(back_populates="article_stocks")
    stock: Mapped["Stock"] = relationship(back_populates="article_stocks")


class StockPrice(UUIDMixin, Base):
    """
    일별 OHLCV (Open/High/Low/Close/Volume) 주가 데이터.
    BE-DATA 파이프라인이 매일 장 마감 후 적재한다.
    change_rate: 전일 대비 등락률 (%).
    """
    __tablename__ = "stock_prices"
    __table_args__ = (
        Index("ix_sp_stock_date", "stock_id", "price_date", unique=True),
        Index("ix_sp_date", "price_date"),
    )

    stock_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stocks.id", ondelete="CASCADE"),
        nullable=False,
    )
    price_date: Mapped[date] = mapped_column(Date, nullable=False)
    open_price: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(18, 4), nullable=True
    )
    close_price: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(18, 4), nullable=True
    )
    high_price: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(18, 4), nullable=True
    )
    low_price: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(18, 4), nullable=True
    )
    volume: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    change_rate: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(8, 4), nullable=True
    )
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    stock: Mapped["Stock"] = relationship(back_populates="stock_prices")


from .news import Article  # noqa: E402