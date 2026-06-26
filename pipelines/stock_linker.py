"""
pipelines/stock_linker.py
기사 제목/요약에서 주식 종목을 감지해 article_stocks 연결을 준비한다.

규칙 기반:
  - 종목명 또는 티커가 텍스트에 등장하면 연결 대상으로 판단
  - mention_score = 등장 횟수 / 전체 단어 수 (0~1)
  - 상위 5개 종목만 연결 (과도한 연결 방지)
"""
import logging
import re
from dataclasses import dataclass
from typing import Optional

from crawlers.base_collector import RawArticle

logger = logging.getLogger(__name__)

_MAX_STOCKS_PER_ARTICLE = 5


@dataclass
class StockLink:
    ticker: str
    mention_score: float
    linked_by: str = "rule"


def link_stocks(
        article: RawArticle,
        stock_index: dict[str, str],  # {종목명: ticker} 또는 {ticker: ticker}
) -> list[StockLink]:
    """
    기사 텍스트에서 종목을 탐지해 StockLink 목록을 반환한다.

    Args:
        article: 분류 완료된 기사
        stock_index: {검색어: ticker} 매핑 (종목명 + 티커 모두 포함)

    Returns:
        StockLink 리스트 (mention_score 내림차순, 최대 5개)
    """
    text = " ".join(filter(None, [
        article.get("title", ""),
        article.get("summary", ""),
        article.get("content", "") or "",
    ])).lower()

    if not text:
        return []

    words = re.findall(r"[가-힣a-zA-Z0-9]+", text)
    total_words = max(len(words), 1)

    counts: dict[str, int] = {}
    for term, ticker in stock_index.items():
        if term.lower() in text:
            count = text.count(term.lower())
            counts[ticker] = counts.get(ticker, 0) + count

    results = [
        StockLink(
            ticker=ticker,
            mention_score=round(count / total_words, 4),
        )
        for ticker, count in sorted(counts.items(), key=lambda x: x[1], reverse=True)
    ]

    return results[:_MAX_STOCKS_PER_ARTICLE]


def build_stock_index(masters: list) -> dict[str, str]:
    """
    StockMaster 목록에서 {종목명: ticker, ticker: ticker} 인덱스를 생성한다.
    link_stocks() 에 전달할 검색 딕셔너리.
    """
    index: dict[str, str] = {}
    for m in masters:
        index[m.name] = m.ticker
        index[m.ticker] = m.ticker
    return index
