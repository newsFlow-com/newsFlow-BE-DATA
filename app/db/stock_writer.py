"""
app/db/stock_writer.py
주식 종목 마스터, 일별 주가, 기사-주식 연결을 PostgreSQL에 적재한다.
"""
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db.session import get_session
from app.models import Article, ArticleStock, Stock, StockPrice

logger = logging.getLogger(__name__)


def write_stock_masters(masters: list) -> int:
    """
    StockMaster 목록을 stocks 테이블에 upsert한다.
    이미 존재하는 ticker는 name/market만 갱신한다.

    Returns:
        upsert된 건수
    """
    if not masters:
        return 0

    count = 0
    with get_session() as session:
        for m in masters:
            stmt = (
                pg_insert(Stock)
                .values(
                    id=uuid.uuid4(),
                    ticker=m.ticker,
                    name=m.name,
                    market=m.market,
                    country_code=m.country_code,
                    sector=m.sector,
                    is_active=True,
                )
                .on_conflict_do_update(
                    index_elements=["ticker"],
                    set_={"name": m.name, "market": m.market, "is_active": True},
                )
            )
            session.execute(stmt)
            count += 1

    logger.info(f"[StockWriter] 종목 마스터 upsert: {count}건")
    return count


def write_stock_prices(prices: list) -> int:
    """
    StockOHLCV 목록을 stock_prices 테이블에 upsert한다.
    동일 (stock_id, price_date) 이면 가격 정보를 갱신한다.

    Returns:
        upsert된 건수
    """
    if not prices:
        return 0

    count = 0
    with get_session() as session:
        # ticker → stock_id 매핑 조회
        ticker_map: dict[str, uuid.UUID] = {
            row[0]: row[1]
            for row in session.execute(
                select(Stock.ticker, Stock.id).where(Stock.is_active.is_(True))
            ).fetchall()
        }

        for p in prices:
            stock_id = ticker_map.get(p.ticker)
            if not stock_id:
                continue

            stmt = (
                pg_insert(StockPrice)
                .values(
                    id=uuid.uuid4(),
                    stock_id=stock_id,
                    price_date=p.price_date,
                    open_price=p.open_price,
                    close_price=p.close_price,
                    high_price=p.high_price,
                    low_price=p.low_price,
                    volume=p.volume,
                    change_rate=p.change_rate,
                )
                .on_conflict_do_update(
                    index_elements=["stock_id", "price_date"],
                    set_={
                        "open_price": p.open_price,
                        "close_price": p.close_price,
                        "high_price": p.high_price,
                        "low_price": p.low_price,
                        "volume": p.volume,
                        "change_rate": p.change_rate,
                    },
                )
            )
            session.execute(stmt)
            count += 1

    logger.info(f"[StockWriter] 주가 upsert: {count}건")
    return count


def write_article_stocks(article_url: str, links: list) -> int:
    """
    StockLink 목록을 article_stocks 테이블에 upsert한다.

    Args:
        article_url: 연결할 기사의 original_url
        links: StockLink 리스트

    Returns:
        upsert된 건수
    """
    if not links:
        return 0

    count = 0
    with get_session() as session:
        article_id = session.execute(
            select(Article.id).where(Article.original_url == article_url)
        ).scalar_one_or_none()

        if not article_id:
            return 0

        ticker_map: dict[str, uuid.UUID] = {
            row[0]: row[1]
            for row in session.execute(
                select(Stock.ticker, Stock.id)
            ).fetchall()
        }

        for link in links:
            stock_id = ticker_map.get(link.ticker)
            if not stock_id:
                continue

            stmt = (
                pg_insert(ArticleStock)
                .values(
                    id=uuid.uuid4(),
                    article_id=article_id,
                    stock_id=stock_id,
                    mention_score=link.mention_score,
                    linked_by=link.linked_by,
                )
                .on_conflict_do_update(
                    index_elements=["article_id", "stock_id"],
                    set_={"mention_score": link.mention_score},
                )
            )
            session.execute(stmt)
            count += 1

    return count
