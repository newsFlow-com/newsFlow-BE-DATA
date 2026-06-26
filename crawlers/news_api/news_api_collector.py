"""
crawlers/news_api/news_api_collector.py
NewsAPI.org 기반 해외 뉴스 수집기.

무료 플랜 제약:
  - 100건 / 일
  - 24시간 딜레이
  - 프로덕션 사용 불가 → 배포 시 NewsData.io 로 교체 예정

하루 100건 제한을 카테고리별로 분산해서 사용한다.
  business 25건 / technology 25건 / science 25건 / health 25건
"""
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Optional

from newsapi import NewsApiClient
from newsapi.newsapi_exception import NewsAPIException

from crawlers.base_collector import BaseCollector, RawArticle

logger = logging.getLogger(__name__)

# ── 카테고리별 수집 설정 ──────────────────────────────────────────────
# 하루 총 100건을 4개 카테고리에 25건씩 분배
CATEGORIES: list[tuple[str, int]] = [
    ("business",   25),
    ("technology", 25),
    ("science",    25),
    ("health",     25),
]

# 수집 대상 국가 코드
COUNTRY = "us"


def _parse_published_at(raw: Optional[str]) -> Optional[datetime]:
    """
    NewsAPI 날짜 문자열(ISO 8601)을 datetime 으로 변환.
    예: "2025-05-18T12:00:00Z"
    """
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except Exception:
        return None


def _normalize_article(item: dict, category: str) -> Optional[RawArticle]:
    """
    NewsAPI article dict 를 RawArticle 로 변환.
    url 또는 title 이 없으면 None 반환.
    """
    url = (item.get("url") or "").strip()
    title = (item.get("title") or "").strip()

    if not url or not title or title == "[Removed]":
        return None

    source_info = item.get("source") or {}
    source_name = source_info.get("name") or "Unknown"

    # domain 추출
    try:
        from urllib.parse import urlparse
        source_domain = urlparse(url).netloc.lstrip("www.")
    except Exception:
        source_domain = source_name.lower().replace(" ", "") + ".com"

    return RawArticle(
        source_domain=source_domain,
        source_name=source_name,
        feed_url="https://newsapi.org/v2/top-headlines",
        original_url=url,
        title=title,
        summary=item.get("description"),
        content=None,   # 무료 플랜은 본문 200자만 제공 → 사용하지 않음
        thumbnail_url=item.get("urlToImage"),
        author=item.get("author"),
        published_at=_parse_published_at(item.get("publishedAt")),
        language_code="en",
        feed_type="newsapi",
    )


class NewsApiCollector(BaseCollector):
    """
    NewsAPI.org 수집기.
    카테고리별로 top-headlines 를 수집해 RawArticle 리스트로 반환한다.
    """

    def __init__(
            self,
            api_key: Optional[str] = None,
            categories: list[tuple[str, int]] = CATEGORIES,
            country: str = COUNTRY,
    ) -> None:
        self.api_key = api_key or os.getenv("NEWS_API_KEY")
        if not self.api_key:
            raise ValueError(
                "NEWS_API_KEY 환경변수가 설정되지 않았습니다. "
                ".env 파일을 확인하세요."
            )
        self.client = NewsApiClient(api_key=self.api_key)
        self.categories = categories
        self.country = country

    def fetch(self, **kwargs) -> list[RawArticle]:
        """
        카테고리별 top-headlines 수집.
        API 오류 시 해당 카테고리를 skip 하고 나머지 결과를 반환한다.
        """
        all_articles: list[RawArticle] = []

        for category, page_size in self.categories:
            try:
                response = self.client.get_top_headlines(
                    country=self.country,
                    category=category,
                    page_size=page_size,
                    language="en",
                )
                items = response.get("articles") or []
                count_before = len(all_articles)

                for item in items:
                    article = _normalize_article(item, category)
                    if article:
                        all_articles.append(article)

                logger.info(
                    f"[NewsAPI] category={category}: "
                    f"{len(all_articles) - count_before}건 수집"
                )

            except NewsAPIException as e:
                logger.warning(f"[NewsAPI] category={category} API 오류: {e}")
            except Exception as e:
                logger.warning(f"[NewsAPI] category={category} 수집 실패: {e}")

        logger.info(f"[NewsAPI 전체] 총 {len(all_articles)}건 수집 완료")
        return all_articles


def collect_news_api() -> list[RawArticle]:
    """
    DAG 의 collect_news_api() 태스크에서 호출하는 진입점.
    API 키가 없으면 빈 리스트를 반환하고 경고 로그만 남긴다.
    """
    try:
        collector = NewsApiCollector()
        return collector.fetch()
    except ValueError as e:
        logger.warning(f"[NewsAPI] 수집 건너뜀: {e}")
        return []