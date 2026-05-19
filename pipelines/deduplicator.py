"""
pipelines/deduplicator.py
기사 중복 제거 파이프라인.

두 단계로 중복을 걸러낸다:
  1. URL 정확 매칭  — DB 에 이미 존재하는 original_url 은 즉시 제외
  2. 제목 유사도    — MinHash LSH 로 제목이 90% 이상 유사한 기사 제외
                     (같은 내용을 여러 언론사가 다른 URL 로 배포하는 경우 대응)

datasketch 라이브러리의 MinHash + LSHForest 를 사용한다.
"""
import logging
import re
from typing import Optional

from datasketch import MinHash, MinHashLSH

from crawlers.base_collector import RawArticle

logger = logging.getLogger(__name__)

# MinHash 설정
_NUM_PERM = 128         # 해시 함수 개수 (높을수록 정확, 느림)
_THRESHOLD = 0.9        # Jaccard 유사도 임계값 (0.9 = 90% 이상 유사하면 중복)


def _tokenize(text: str) -> set[str]:
    """
    제목을 2-gram 토큰 셋으로 변환.
    한국어는 어절 분리보다 2-gram 이 중복 감지에 효과적이다.
    """
    text = re.sub(r"\s+", " ", text.lower().strip())
    if len(text) < 2:
        return {text}
    return {text[i:i+2] for i in range(len(text) - 1)}


def _make_minhash(text: str) -> MinHash:
    """텍스트를 MinHash 로 변환."""
    mh = MinHash(num_perm=_NUM_PERM)
    for token in _tokenize(text):
        mh.update(token.encode("utf-8"))
    return mh


def deduplicate_by_url(
        articles: list[RawArticle],
        existing_urls: set[str],
) -> list[RawArticle]:
    """
    Step 1: DB 에 이미 존재하는 URL 을 가진 기사를 제외한다.

    Args:
        articles: 전처리 완료된 기사 목록
        existing_urls: DB 에서 조회한 기존 URL 셋

    Returns:
        URL 중복이 제거된 기사 목록
    """
    result = [a for a in articles if a["original_url"] not in existing_urls]
    skipped = len(articles) - len(result)
    if skipped:
        logger.info(f"[중복제거-URL] {skipped}건 제외 (기존 URL 매칭)")
    return result


def deduplicate_by_title(
        articles: list[RawArticle],
        threshold: float = _THRESHOLD,
) -> list[RawArticle]:
    """
    Step 2: 제목 유사도 기반 중복 제거 (MinHash LSH).
    같은 배치 내에서 유사한 제목의 기사를 중복으로 처리한다.
    먼저 등장한 기사를 우선 채택한다.

    Args:
        articles: URL 중복 제거 완료된 기사 목록
        threshold: Jaccard 유사도 임계값 (기본 0.9)

    Returns:
        제목 중복이 제거된 기사 목록
    """
    if not articles:
        return []

    lsh = MinHashLSH(threshold=threshold, num_perm=_NUM_PERM)
    result: list[RawArticle] = []
    skipped = 0

    for idx, article in enumerate(articles):
        key = f"article_{idx}"
        mh = _make_minhash(article["title"])

        try:
            neighbors = lsh.query(mh)
            if neighbors:
                # 유사한 기사가 이미 LSH 에 등록돼 있음 → 중복
                logger.debug(
                    f"[중복제거-제목] 유사 기사 발견 → skip: '{article['title'][:30]}'"
                )
                skipped += 1
                continue

            lsh.insert(key, mh)
            result.append(article)

        except Exception as e:
            # LSH 오류 시 해당 기사는 통과시켜 안전하게 처리
            logger.warning(f"[중복제거] LSH 오류 (통과 처리): {e}")
            result.append(article)

    if skipped:
        logger.info(f"[중복제거-제목] {skipped}건 제외 (유사 제목 매칭)")

    return result


def deduplicate(
        articles: list[RawArticle],
        existing_urls: Optional[set[str]] = None,
) -> list[RawArticle]:
    """
    전체 중복 제거 파이프라인 진입점.
    URL 중복 → 제목 유사도 중복 순서로 처리한다.

    Args:
        articles: 전처리 완료된 기사 목록
        existing_urls: DB 에서 조회한 기존 URL 셋 (None 이면 URL 중복 제거 skip)

    Returns:
        최종 중복 제거된 기사 목록
    """
    original_count = len(articles)

    # Step 1: URL 중복 제거
    if existing_urls:
        articles = deduplicate_by_url(articles, existing_urls)

    # Step 2: 제목 유사도 중복 제거
    articles = deduplicate_by_title(articles)

    logger.info(
        f"[중복제거] 완료 — 입력: {original_count}건 / "
        f"최종: {len(articles)}건 / "
        f"제외: {original_count - len(articles)}건"
    )
    return articles