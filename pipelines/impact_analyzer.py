"""
pipelines/impact_analyzer.py — 뉴스-주가 영향도 분석 파이프라인

기사 발행 시점 전후의 주가 변동을 계산해 article_stocks 에 기록한다.
⚠ 인과관계를 증명하는 지표가 아니라 "발행 시점 전후 주가 동조화" 참고 지표다.

계산 항목:
  1. price_change_publish_day — 발행일 기준 가장 가까운 거래일의 등락률(%)
  2. price_change_3d          — 발행일 종가 → 3거래일 후 종가까지 누적 변동률(%)

impact_analyzed_at IS NULL 인 연결만 대상으로 하며, price_change_3d 까지
계산 가능한 경우에만 impact_analyzed_at 을 채운다. 아직 3거래일 후 가격이
없으면 price_change_publish_day만 채우고 다음 배치에서 재처리한다.
"""
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.models import Article, ArticleStock, StockPrice

logger = logging.getLogger(__name__)

LOOKBACK_DAYS = 60       # 이보다 오래된 기사-종목 연결은 재처리 대상에서 제외
FORWARD_TRADING_DAYS = 3
BATCH_SIZE = 200


def _find_baseline_price(session: Session, stock_id, publish_date: date) -> Optional[StockPrice]:
    """발행일 이후 가장 가까운 거래일의 주가를 반환한다."""
    return session.execute(
        select(StockPrice)
        .where(StockPrice.stock_id == stock_id, StockPrice.price_date >= publish_date)
        .order_by(StockPrice.price_date.asc())
        .limit(1)
    ).scalar_one_or_none()


def _find_price_after(
        session: Session, stock_id, base_date: date, trading_days: int
) -> Optional[StockPrice]:
    """base_date 이후 N번째 거래일의 주가를 반환한다. 데이터가 부족하면 None."""
    rows = session.execute(
        select(StockPrice)
        .where(StockPrice.stock_id == stock_id, StockPrice.price_date > base_date)
        .order_by(StockPrice.price_date.asc())
        .limit(trading_days)
    ).scalars().all()
    if len(rows) < trading_days:
        return None
    return rows[-1]


def analyze_link_impact(session: Session, link: ArticleStock, publish_date: date) -> bool:
    """
    단일 article_stocks 연결의 영향도를 계산해 반영한다.
    price_change_3d 까지 계산 완료되면 True (impact_analyzed_at 도 함께 채워짐).
    """
    baseline = _find_baseline_price(session, link.stock_id, publish_date)
    if baseline is None:
        return False  # 발행일 이후 주가 데이터가 아직 없음

    link.price_change_publish_day = (
        float(baseline.change_rate) if baseline.change_rate is not None else None
    )

    after = _find_price_after(session, link.stock_id, baseline.price_date, FORWARD_TRADING_DAYS)
    if after is None or not baseline.close_price or not after.close_price:
        return False  # 3거래일 후 데이터가 아직 없음 → 다음 배치에서 재시도

    link.price_change_3d = round(
        float((after.close_price - baseline.close_price) / baseline.close_price) * 100, 4
    )
    link.impact_analyzed_at = datetime.now(tz=timezone.utc)
    return True


def run_impact_analysis(limit: int = BATCH_SIZE) -> int:
    """impact_analyzed_at IS NULL인 최근 기사-종목 연결의 영향도를 계산한다."""
    since = datetime.now(tz=timezone.utc) - timedelta(days=LOOKBACK_DAYS)
    completed = 0

    with get_session() as session:
        rows = session.execute(
            select(ArticleStock, Article.published_at)
            .join(Article, Article.id == ArticleStock.article_id)
            .where(
                ArticleStock.impact_analyzed_at.is_(None),
                Article.published_at.is_not(None),
                Article.published_at >= since,
            )
            .order_by(Article.published_at.asc())
            .limit(limit)
        ).all()

        for link, published_at in rows:
            try:
                if analyze_link_impact(session, link, published_at.date()):
                    completed += 1
            except Exception as e:
                logger.warning("영향도 분석 실패 (article_stock_id=%s): %s", link.id, e)

    logger.info("영향도 분석 완료: %d건 (대상 %d건)", completed, len(rows))
    return completed
