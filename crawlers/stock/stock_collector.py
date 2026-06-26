"""
crawlers/stock/stock_collector.py
pykrx를 이용한 국내 주식 종목 마스터 및 일별 OHLCV 수집기.

수집 대상:
  - KOSPI / KOSDAQ 전 종목 마스터 (ticker, name, market)
  - 지정 날짜의 종목별 OHLCV + 등락률

pykrx는 한국거래소(KRX) 공개 데이터를 스크래핑하므로
장 마감 후(오후 4시 이후) 실행해야 당일 데이터가 조회된다.
"""
import logging
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class StockMaster:
    ticker: str
    name: str
    market: str          # KOSPI | KOSDAQ
    country_code: str = "KR"
    sector: Optional[str] = None


@dataclass
class StockOHLCV:
    ticker: str
    price_date: date
    open_price: Optional[float]
    close_price: Optional[float]
    high_price: Optional[float]
    low_price: Optional[float]
    volume: Optional[int]
    change_rate: Optional[float]  # 전일 대비 등락률(%)


def collect_stock_masters() -> list[StockMaster]:
    """
    KOSPI + KOSDAQ 전 종목 마스터를 수집한다.
    주기: 월 1회 또는 상장/폐지 이벤트 발생 시 실행 권장.
    """
    try:
        from pykrx import stock as krx
    except ImportError:
        logger.warning("[Stock] pykrx 미설치 — 수집 건너뜀")
        return []

    today = date.today().strftime("%Y%m%d")
    masters: list[StockMaster] = []

    for market in ("KOSPI", "KOSDAQ"):
        try:
            tickers = krx.get_market_ticker_list(today, market=market)
            for ticker in tickers:
                name = krx.get_market_ticker_name(ticker)
                masters.append(StockMaster(
                    ticker=ticker,
                    name=name,
                    market=market,
                ))
        except Exception as e:
            logger.warning(f"[Stock] {market} 마스터 수집 실패: {e}")

    logger.info(f"[Stock] 종목 마스터 수집 완료: {len(masters)}건")
    return masters


def collect_stock_prices(target_date: Optional[date] = None) -> list[StockOHLCV]:
    """
    target_date 기준 KOSPI + KOSDAQ 전 종목 OHLCV를 수집한다.

    Args:
        target_date: 수집 기준 날짜 (None이면 어제)

    Returns:
        StockOHLCV 리스트
    """
    try:
        from pykrx import stock as krx
    except ImportError:
        logger.warning("[Stock] pykrx 미설치 — 수집 건너뜀")
        return []

    if target_date is None:
        target_date = date.today() - timedelta(days=1)

    date_str = target_date.strftime("%Y%m%d")
    prices: list[StockOHLCV] = []

    for market in ("KOSPI", "KOSDAQ"):
        try:
            df = krx.get_market_ohlcv(date_str, market=market)
            if df.empty:
                continue

            tickers = krx.get_market_ticker_list(date_str, market=market)
            for ticker in tickers:
                if ticker not in df.index:
                    continue
                row = df.loc[ticker]
                prices.append(StockOHLCV(
                    ticker=ticker,
                    price_date=target_date,
                    open_price=float(row.get("시가", 0)) or None,
                    close_price=float(row.get("종가", 0)) or None,
                    high_price=float(row.get("고가", 0)) or None,
                    low_price=float(row.get("저가", 0)) or None,
                    volume=int(row.get("거래량", 0)) or None,
                    change_rate=float(row.get("등락률", 0)) or None,
                ))
        except Exception as e:
            logger.warning(f"[Stock] {market} 주가 수집 실패 ({date_str}): {e}")

    logger.info(f"[Stock] {target_date} 주가 수집 완료: {len(prices)}건")
    return prices
