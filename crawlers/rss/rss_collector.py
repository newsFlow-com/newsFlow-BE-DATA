"""
crawlers/rss/rss_collector.py
국내·해외 언론사 RSS/Atom 피드 수집기.

"""
import logging
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Optional
from urllib.parse import urlparse

import feedparser
import httpx

from crawlers.base_collector import BaseCollector, RawArticle

logger = logging.getLogger(__name__)

# ── 수집 대상 RSS 피드 정의 ──────────────────────────────────────────
RSS_SOURCES: list[tuple[str, str, str, str]] = [

    # ── SBS 섹션별 ────────────────────────────────────────────────
    ("SBS-정치",   "news.sbs.co.kr", "https://news.sbs.co.kr/news/SectionRssFeed.do?sectionId=01&plink=RSSREADER", "ko"),
    ("SBS-경제",   "news.sbs.co.kr", "https://news.sbs.co.kr/news/SectionRssFeed.do?sectionId=02&plink=RSSREADER", "ko"),
    ("SBS-사회",   "news.sbs.co.kr", "https://news.sbs.co.kr/news/SectionRssFeed.do?sectionId=03&plink=RSSREADER", "ko"),
    ("SBS-국제",   "news.sbs.co.kr", "https://news.sbs.co.kr/news/SectionRssFeed.do?sectionId=07&plink=RSSREADER", "ko"),
    ("SBS-문화",   "news.sbs.co.kr", "https://news.sbs.co.kr/news/SectionRssFeed.do?sectionId=08&plink=RSSREADER", "ko"),
    ("SBS-스포츠", "news.sbs.co.kr", "https://news.sbs.co.kr/news/SectionRssFeed.do?sectionId=09&plink=RSSREADER", "ko"),

    # ── 동아일보 섹션별 ───────────────────────────────────────────
    ("동아-정치",  "donga.com", "https://rss.donga.com/politics.xml",     "ko"),
    ("동아-경제",  "donga.com", "https://rss.donga.com/economy.xml",      "ko"),
    ("동아-사회",  "donga.com", "https://rss.donga.com/national.xml",     "ko"),
    ("동아-국제",  "donga.com", "https://rss.donga.com/international.xml","ko"),
    ("동아-과학",  "donga.com", "https://rss.donga.com/science.xml",      "ko"),
    ("동아-문화",  "donga.com", "https://rss.donga.com/culture.xml",      "ko"),

    # ── 경향신문 섹션별 ───────────────────────────────────────────
    ("경향신문",  "khan.co.kr", "https://www.khan.co.kr/rss/rssdata/total_news.xml", "ko"),

    # ── 한겨레 전체 ───────────────────────────────────────────────
    ("한겨레",     "hani.co.kr", "https://www.hani.co.kr/rss/", "ko"),

    # ── 한국경제 전체 ─────────────────────────────────────────────
    ("한국경제",   "hankyung.com", "https://www.hankyung.com/feed/all-news", "ko"),

    # ── 매일경제 섹션별 ───────────────────────────────────────────
    ("매경-경제",  "mk.co.kr", "https://www.mk.co.kr/rss/30100041/", "ko"),
    ("매경-정치",  "mk.co.kr", "https://www.mk.co.kr/rss/30200030/", "ko"),
    ("매경-사회",  "mk.co.kr", "https://www.mk.co.kr/rss/50400012/", "ko"),
    ("매경-국제",  "mk.co.kr", "https://www.mk.co.kr/rss/30300018/", "ko"),
    ("매경-기업",  "mk.co.kr", "https://www.mk.co.kr/rss/50100032/", "ko"),
    ("매경-증권",  "mk.co.kr", "https://www.mk.co.kr/rss/50200011/", "ko"),

    # ── 연합뉴스 전체 ─────────────────────────────────────────────
    ("연합뉴스",   "yna.co.kr", "https://www.yna.co.kr/rss/news.xml", "ko"),

    # ── 노컷뉴스 섹션별 ───────────────────────────────────────────
    ("노컷뉴스",  "nocutnews.co.kr", "https://rss.nocutnews.co.kr/nocutnews.xml", "ko"),

    # ── 해외 (영문) ───────────────────────────────────────────────
    ("BBC",           "bbc.com",       "https://feeds.bbci.co.uk/news/rss.xml",                "en"),
    ("BBC-비즈니스",  "bbc.com",       "https://feeds.bbci.co.uk/news/business/rss.xml",       "en"),
    ("BBC-기술",      "bbc.com",       "https://feeds.bbci.co.uk/news/technology/rss.xml",     "en"),
    ("BBC-세계",      "bbc.com",       "https://feeds.bbci.co.uk/news/world/rss.xml",          "en"),
]


def _parse_published_at(entry: feedparser.FeedParserDict) -> Optional[datetime]:
    """
    feedparser entry 에서 발행 시각을 파싱한다.
    published_parsed → published → updated_parsed → updated 순으로 시도.
    모두 실패하면 None 반환.
    """
    # 1) feedparser 가 자동 파싱한 time.struct_time
    for attr in ("published_parsed", "updated_parsed"):
        ts = getattr(entry, attr, None)
        if ts:
            try:
                return datetime(*ts[:6], tzinfo=timezone.utc)
            except Exception:
                pass

    # 2) RFC 2822 문자열 직접 파싱
    for attr in ("published", "updated"):
        raw = getattr(entry, attr, None)
        if raw:
            try:
                return parsedate_to_datetime(raw)
            except Exception:
                pass

    return None


def _extract_thumbnail(entry: feedparser.FeedParserDict) -> Optional[str]:
    """media:thumbnail, enclosure, img 태그 순으로 썸네일을 추출한다."""
    # media:thumbnail
    media_thumbnail = getattr(entry, "media_thumbnail", None)
    if media_thumbnail and isinstance(media_thumbnail, list):
        return media_thumbnail[0].get("url")

    # enclosure (팟캐스트/미디어 첨부)
    enclosures = getattr(entry, "enclosures", [])
    for enc in enclosures:
        if enc.get("type", "").startswith("image/"):
            return enc.get("href") or enc.get("url")

    return None


def _normalize_entry(
        entry: feedparser.FeedParserDict,
        source_name: str,
        source_domain: str,
        language_code: str,
) -> Optional[RawArticle]:
    """
    feedparser entry 하나를 RawArticle 로 변환.
    URL 이 없거나 제목이 없으면 None 을 반환해 수집에서 제외.
    """
    url = entry.get("link") or entry.get("id")
    title = entry.get("title", "").strip()

    if not url or not title:
        return None

    # 요약: summary → description → content[0] 순으로 시도
    summary: Optional[str] = None
    raw_summary = entry.get("summary") or entry.get("description")
    if raw_summary:
        # HTML 태그 제거 (간단한 strip)
        import re
        summary = re.sub(r"<[^>]+>", "", raw_summary).strip() or None

    if not summary:
        content_list = entry.get("content", [])
        if content_list:
            import re
            summary = re.sub(r"<[^>]+>", "", content_list[0].get("value", "")).strip() or None

    return RawArticle(
        source_domain=source_domain,
        source_name=source_name,
        original_url=url.strip(),
        title=title,
        summary=summary,
        content=None,           # RSS 는 본문 전체를 제공하지 않음
        thumbnail_url=_extract_thumbnail(entry),
        author=entry.get("author"),
        published_at=_parse_published_at(entry),
        language_code=language_code,
        feed_type="rss",
    )


class RssCollector(BaseCollector):
    """
    단일 RSS 소스 수집기.
    하나의 소스(name, domain, feed_url)에서 기사를 수집한다.
    """

    def __init__(
            self,
            source_name: str,
            source_domain: str,
            feed_url: str,
            language_code: str = "ko",
            timeout: int = 10,
    ) -> None:
        self.source_name = source_name
        self.source_domain = source_domain
        self.feed_url = feed_url
        self.language_code = language_code
        self.timeout = timeout

    def fetch(self, **kwargs) -> list[RawArticle]:
        """
        RSS 피드를 파싱해 RawArticle 리스트 반환.
        네트워크 오류나 파싱 실패 시 빈 리스트를 반환하고 로그만 남긴다.
        """
        try:
            # feedparser 는 내부적으로 urllib 를 쓰므로 timeout 제어를 위해
            # httpx 로 먼저 raw response 를 받아서 feedparser 에 넘긴다.
            response = httpx.get(self.feed_url, timeout=self.timeout, follow_redirects=True)
            response.raise_for_status()
            feed = feedparser.parse(response.text)
        except httpx.HTTPError as e:
            logger.warning(f"[RSS] {self.source_name} 네트워크 오류: {e}")
            return []
        except Exception as e:
            logger.warning(f"[RSS] {self.source_name} 파싱 오류: {e}")
            return []

        if feed.bozo and not feed.entries:
            logger.warning(f"[RSS] {self.source_name} 피드 파싱 실패 (bozo): {feed.bozo_exception}")
            return []

        articles: list[RawArticle] = []
        for entry in feed.entries:
            article = _normalize_entry(
                entry, self.source_name, self.source_domain, self.language_code
            )
            if article:
                articles.append(article)

        logger.info(f"[RSS] {self.source_name}: {len(articles)}건 수집")
        return articles


def collect_all_rss(
        sources: list[tuple[str, str, str, str]] = RSS_SOURCES,
) -> list[RawArticle]:
    """
    RSS_SOURCES 에 정의된 모든 소스를 순차 수집해 합산 반환.
    DAG 의 collect_rss() 태스크에서 호출하는 진입점.

    """
    all_articles: list[RawArticle] = []

    for name, domain, feed_url, lang in sources:
        collector = RssCollector(
            source_name=name,
            source_domain=domain,
            feed_url=feed_url,
            language_code=lang,
        )
        articles = collector.fetch()
        all_articles.extend(articles)

    logger.info(f"[RSS 전체] 총 {len(all_articles)}건 수집 완료 ({len(sources)}개 소스)")
    return all_articles