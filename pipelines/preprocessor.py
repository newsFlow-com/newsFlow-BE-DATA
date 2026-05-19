"""
pipelines/preprocessor.py
수집된 RawArticle 을 DB 적재 전에 정제·정규화하는 파이프라인.

처리 순서:
  1. URL 정규화 (쿼리 파라미터 중 트래킹 파라미터 제거)
  2. 제목 정제 (언론사명 접미사 제거, 공백 정리)
  3. 요약 정제 (HTML 태그 제거, 길이 제한)
  4. 발행 시각 보정 (None 이면 수집 시각으로 대체)
  5. 언론사 도메인 → sources 테이블 매핑 (upsert 준비)
"""
import logging
import re
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse, urlunparse, urlencode, parse_qsl

from crawlers.base_collector import RawArticle

logger = logging.getLogger(__name__)

# ── 제거할 URL 트래킹 파라미터 ────────────────────────────────────────
_TRACKING_PARAMS = frozenset({
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "fbclid", "gclid", "ref", "from", "_source",
})

# ── 제목에서 제거할 언론사 접미사 패턴 ───────────────────────────────────
# 예: "삼성전자 실적 발표 - 한국경제" → "삼성전자 실적 발표"
_TITLE_SUFFIX_RE = re.compile(
    r"\s*[-–|]\s*(한국경제|매일경제|조선일보|중앙일보|동아일보|한겨레|경향신문"
    r"|KBS|MBC|SBS|연합뉴스|뉴시스|뉴스1|전자신문|ZDNet|서울경제"
    r"|Reuters|BBC|AP|Bloomberg|CNN|NYT|The Guardian)\s*$",
    re.IGNORECASE,
)

# 요약 최대 길이 (DB summary 컬럼에 저장되는 길이)
_SUMMARY_MAX_LEN = 500


def _clean_url(url: str) -> str:
    """트래킹 파라미터를 제거하고 URL 을 정규화한다."""
    try:
        parsed = urlparse(url)
        clean_qs = urlencode(
            [(k, v) for k, v in parse_qsl(parsed.query) if k not in _TRACKING_PARAMS]
        )
        cleaned = urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            clean_qs,
            "",         # fragment 제거
        ))
        return cleaned.rstrip("/")
    except Exception:
        return url


def _clean_title(title: str) -> str:
    """제목 정제: 언론사 접미사 제거 + 공백 정리."""
    title = _TITLE_SUFFIX_RE.sub("", title)
    title = re.sub(r"\s+", " ", title).strip()
    return title


def _clean_html(text: Optional[str]) -> Optional[str]:
    """HTML 태그를 제거하고 공백을 정리한다."""
    if not text:
        return None
    cleaned = re.sub(r"<[^>]+>", "", text)
    cleaned = re.sub(r"&[a-zA-Z]+;", " ", cleaned)   # HTML 엔티티
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned or None


def _truncate(text: Optional[str], max_len: int) -> Optional[str]:
    if not text:
        return None
    return text[:max_len] if len(text) > max_len else text


def preprocess(article: RawArticle) -> Optional[RawArticle]:
    """
    RawArticle 하나를 정제해서 반환.
    치명적인 필드(url, title)가 정제 후에도 없으면 None 반환 → 적재 제외.

    Args:
        article: 수집기에서 넘어온 원시 기사 데이터

    Returns:
        정제된 RawArticle 또는 None
    """
    # 1. URL 정규화
    clean_url = _clean_url(article["original_url"])
    if not clean_url:
        logger.debug(f"[전처리] URL 없음 → skip: {article['title'][:30]}")
        return None

    # 2. 제목 정제
    clean_title = _clean_title(article["title"])
    if not clean_title:
        logger.debug(f"[전처리] 제목 없음 → skip: {clean_url}")
        return None

    # 3. 요약 정제 + 길이 제한
    clean_summary = _truncate(_clean_html(article.get("summary")), _SUMMARY_MAX_LEN)

    # 4. 발행 시각 보정
    published_at = article.get("published_at")
    if published_at is None:
        published_at = datetime.now(tz=timezone.utc)
        logger.debug(f"[전처리] 발행 시각 없음 → 수집 시각으로 대체: {clean_title[:30]}")

    # 5. 정제된 RawArticle 반환
    return RawArticle(
        source_domain=article["source_domain"],
        source_name=article["source_name"],
        original_url=clean_url,
        title=clean_title,
        summary=clean_summary,
        content=article.get("content"),
        thumbnail_url=article.get("thumbnail_url"),
        author=article.get("author"),
        published_at=published_at,
        language_code=article.get("language_code", "ko"),
        feed_type=article.get("feed_type", "rss"),
    )


def preprocess_all(articles: list[RawArticle]) -> list[RawArticle]:
    """
    RawArticle 리스트 전체를 정제한다.
    None 반환 항목(불완전 기사)은 제외한다.

    Args:
        articles: 수집기에서 넘어온 원시 기사 목록

    Returns:
        정제 완료된 기사 목록
    """
    result: list[RawArticle] = []
    skip_count = 0

    for article in articles:
        cleaned = preprocess(article)
        if cleaned:
            result.append(cleaned)
        else:
            skip_count += 1

    logger.info(
        f"[전처리] 완료 — 입력: {len(articles)}건 / "
        f"통과: {len(result)}건 / 제외: {skip_count}건"
    )
    return result