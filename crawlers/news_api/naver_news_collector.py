"""
crawlers/news_api/naver_news_collector.py
네이버 뉴스 검색 API 기반 국내 뉴스 수집기.

네이버 검색 API 제약:
  - 1일 25,000 호출 (클라이언트 ID 기준)
  - 1회 최대 100건
  - 검색어(query) 기반 수집 → 카테고리별 대표 키워드로 분산

카테고리별 키워드를 순회하며 각 20건씩 수집한다.
"""
import logging
import os
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse

import httpx

from crawlers.base_collector import BaseCollector, RawArticle

logger = logging.getLogger(__name__)

_API_URL = "https://openapi.naver.com/v1/search/news.json"

# 카테고리별 대표 검색어 — (slug, 검색어, 수집 건수)
NAVER_QUERIES: list[tuple[str, str, int]] = [
    ("정치",   "정치 국회",   20),
    ("경제",   "경제 금리",   20),
    ("주식",   "주식 증시",   20),
    ("기술",   "IT 인공지능", 20),
    ("사회",   "사회 사건",   20),
    ("국제",   "국제 외교",   20),
]


def _parse_pub_date(raw: Optional[str]) -> Optional[datetime]:
    """
    네이버 API 날짜 형식(RFC 1123) → datetime.
    예: "Mon, 19 May 2025 10:00:00 +0900"
    """
    if not raw:
        return None
    try:
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(raw).astimezone(timezone.utc)
    except Exception:
        return None


def _strip_html(text: Optional[str]) -> Optional[str]:
    """네이버 API 응답의 <b> 태그 등 HTML 제거."""
    if not text:
        return None
    import re
    return re.sub(r"<[^>]+>", "", text).strip() or None


def _normalize_item(item: dict) -> Optional[RawArticle]:
    """
    네이버 뉴스 API item dict → RawArticle.
    originallink(언론사 원문) 우선, 없으면 link(네이버 뉴스) 사용.
    """
    url = (item.get("originallink") or item.get("link") or "").strip()
    title = _strip_html(item.get("title"))

    if not url or not title:
        return None

    try:
        source_domain = urlparse(url).netloc.lstrip("www.")
    except Exception:
        source_domain = "naver.com"

    return RawArticle(
        source_domain=source_domain,
        source_name=source_domain,
        feed_url=_API_URL,
        original_url=url,
        title=title,
        summary=_strip_html(item.get("description")),
        content=None,
        thumbnail_url=None,
        author=None,
        published_at=_parse_pub_date(item.get("pubDate")),
        language_code="ko",
        feed_type="newsapi",
    )


class NaverNewsCollector(BaseCollector):
    """
    네이버 뉴스 검색 API 수집기.
    NAVER_QUERIES 에 정의된 카테고리별 키워드를 순회하며 수집한다.
    """

    def __init__(
            self,
            client_id: Optional[str] = None,
            client_secret: Optional[str] = None,
            queries: list[tuple[str, str, int]] = NAVER_QUERIES,
    ) -> None:
        self.client_id = client_id or os.getenv("NAVER_CLIENT_ID")
        self.client_secret = client_secret or os.getenv("NAVER_CLIENT_SECRET")
        if not self.client_id or not self.client_secret:
            raise ValueError(
                "NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 환경변수가 설정되지 않았습니다."
            )
        self.queries = queries

    def fetch(self, **kwargs) -> list[RawArticle]:
        """카테고리별 키워드로 뉴스를 수집해 RawArticle 리스트 반환."""
        headers = {
            "X-Naver-Client-Id": self.client_id,
            "X-Naver-Client-Secret": self.client_secret,
        }
        all_articles: list[RawArticle] = []

        with httpx.Client(timeout=10) as client:
            for category, query, display in self.queries:
                try:
                    resp = client.get(
                        _API_URL,
                        headers=headers,
                        params={"query": query, "display": display, "sort": "date"},
                    )
                    resp.raise_for_status()
                    items = resp.json().get("items", [])
                    count_before = len(all_articles)

                    for item in items:
                        article = _normalize_item(item)
                        if article:
                            all_articles.append(article)

                    logger.info(
                        f"[NaverNews] category={category}: "
                        f"{len(all_articles) - count_before}건 수집"
                    )
                except httpx.HTTPError as e:
                    logger.warning(f"[NaverNews] category={category} 네트워크 오류: {e}")
                except Exception as e:
                    logger.warning(f"[NaverNews] category={category} 수집 실패: {e}")

        logger.info(f"[NaverNews 전체] 총 {len(all_articles)}건 수집 완료")
        return all_articles


def collect_naver_news() -> list[RawArticle]:
    """DAG의 collect_naver_news() 태스크에서 호출하는 진입점."""
    try:
        collector = NaverNewsCollector()
        return collector.fetch()
    except ValueError as e:
        logger.warning(f"[NaverNews] 수집 건너뜀: {e}")
        return []
