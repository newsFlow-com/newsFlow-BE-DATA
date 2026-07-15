"""
pipelines/issue_clusterer.py — 이슈 클러스터링 파이프라인

같은 사건을 다루는 여러 매체의 기사를 하나의 Issue로 묶는다.
deduplicator.py가 배치 내에서 "동일 기사"를 제거하는 것과 달리,
이 모듈은 DB 전체를 대상으로 "다른 기사지만 같은 사건"을 시간에 걸쳐 클러스터링한다.

알고리즘:
  1. 기사의 상위 키워드 집합 + 대표 카테고리를 구한다.
  2. 같은 카테고리 · 최근 CLUSTER_WINDOW_HOURS 이내에 갱신된 active 이슈 중
     공유 키워드가 MIN_SHARED_KEYWORDS개 이상인 후보를 SQL로 좁힌다.
  3. 후보들에 대해 정확한 키워드 Jaccard 유사도를 계산해 최댓값을 선택한다.
  4. SIMILARITY_THRESHOLD 이상이면 기존 이슈에 병합, 아니면 새 이슈를 생성한다.

재클러스터링은 하지 않는다 — 이슈는 최초 배정 이후 title/category가 고정된다.
"""
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.models import Article, ArticleCategory, ArticleKeyword, Issue, IssueKeyword

logger = logging.getLogger(__name__)

CLUSTER_WINDOW_HOURS = 48
SIMILARITY_THRESHOLD = 0.35
MIN_SHARED_KEYWORDS = 2
TOP_KEYWORDS_PER_ARTICLE = 10
BATCH_SIZE = 100


def _load_article_keywords(session: Session, article_id: uuid.UUID) -> dict[uuid.UUID, float]:
    """기사의 상위 키워드를 relevance_score 순으로 조회한다."""
    rows = session.execute(
        select(ArticleKeyword.keyword_id, ArticleKeyword.relevance_score)
        .where(ArticleKeyword.article_id == article_id)
        .order_by(ArticleKeyword.relevance_score.desc().nullslast())
        .limit(TOP_KEYWORDS_PER_ARTICLE)
    ).all()
    return {row.keyword_id: (row.relevance_score or 0.0) for row in rows}


def _load_top_category(session: Session, article_id: uuid.UUID) -> Optional[uuid.UUID]:
    """기사의 최상위(confidence 가장 높은) 카테고리를 조회한다."""
    row = session.execute(
        select(ArticleCategory.category_id)
        .where(ArticleCategory.article_id == article_id)
        .order_by(ArticleCategory.confidence_score.desc().nullslast())
        .limit(1)
    ).first()
    return row.category_id if row else None


def _find_candidate_issue_ids(
        session: Session,
        category_id: uuid.UUID,
        keyword_ids: set[uuid.UUID],
        since: datetime,
) -> list[uuid.UUID]:
    """
    같은 카테고리 · 시간 윈도우 내에서 공유 키워드가 MIN_SHARED_KEYWORDS개 이상인
    이슈 후보를 SQL로 좁힌다 (정밀 Jaccard 계산 전 1차 필터).
    """
    rows = session.execute(
        select(IssueKeyword.issue_id, func.count(IssueKeyword.keyword_id).label("shared"))
        .join(Issue, Issue.id == IssueKeyword.issue_id)
        .where(
            Issue.status == "active",
            Issue.category_id == category_id,
            Issue.last_published_at >= since,
            IssueKeyword.keyword_id.in_(keyword_ids),
        )
        .group_by(IssueKeyword.issue_id)
        .having(func.count(IssueKeyword.keyword_id) >= MIN_SHARED_KEYWORDS)
    ).all()
    return [row.issue_id for row in rows]


def _issue_keyword_ids(session: Session, issue_id: uuid.UUID) -> set[uuid.UUID]:
    rows = session.execute(
        select(IssueKeyword.keyword_id).where(IssueKeyword.issue_id == issue_id)
    ).all()
    return {row.keyword_id for row in rows}


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    union = len(a | b)
    return len(a & b) / union if union else 0.0


def _pick_best_issue_id(
        session: Session,
        candidate_ids: list[uuid.UUID],
        keyword_ids: set[uuid.UUID],
) -> tuple[Optional[uuid.UUID], float]:
    """후보 이슈들 중 정밀 Jaccard 유사도가 가장 높은 이슈를 선택한다."""
    best_id, best_score = None, 0.0
    for issue_id in candidate_ids:
        score = _jaccard(keyword_ids, _issue_keyword_ids(session, issue_id))
        if score > best_score:
            best_id, best_score = issue_id, score
    return best_id, best_score


def _merge_into_issue(
        session: Session,
        issue: Issue,
        article: Article,
        keyword_scores: dict[uuid.UUID, float],
) -> None:
    """기사를 기존 이슈에 편입한다. 키워드 집합은 합집합으로 확장한다."""
    existing_keyword_ids = _issue_keyword_ids(session, issue.id)
    for keyword_id, score in keyword_scores.items():
        if keyword_id in existing_keyword_ids:
            continue
        session.add(IssueKeyword(
            id=uuid.uuid4(), issue_id=issue.id, keyword_id=keyword_id, weight=score,
        ))

    existing_source_ids = set(session.execute(
        select(Article.source_id).where(Article.issue_id == issue.id).distinct()
    ).scalars().all())

    article.issue_id = issue.id
    issue.article_count += 1
    issue.source_count = len(existing_source_ids | {article.source_id})

    if article.published_at:
        if issue.last_published_at is None or article.published_at > issue.last_published_at:
            issue.last_published_at = article.published_at
        if issue.first_published_at is None or article.published_at < issue.first_published_at:
            issue.first_published_at = article.published_at


def _create_issue(
        session: Session,
        article: Article,
        category_id: Optional[uuid.UUID],
        keyword_scores: dict[uuid.UUID, float],
) -> Issue:
    """새 이슈를 생성하고 기사를 그 이슈의 최초 구성원으로 배정한다."""
    issue_id = uuid.uuid4()
    issue = Issue(
        id=issue_id,
        title=article.title,
        representative_article_id=article.id,
        category_id=category_id,
        article_count=1,
        source_count=1,
        first_published_at=article.published_at,
        last_published_at=article.published_at,
        status="active",
    )
    session.add(issue)

    for keyword_id, score in keyword_scores.items():
        session.add(IssueKeyword(
            id=uuid.uuid4(), issue_id=issue_id, keyword_id=keyword_id, weight=score,
        ))

    article.issue_id = issue_id
    return issue


def cluster_article(session: Session, article: Article) -> None:
    """단일 기사를 기존 이슈에 병합하거나 새 이슈로 생성한다."""
    keyword_scores = _load_article_keywords(session, article.id)
    category_id = _load_top_category(session, article.id)
    keyword_ids = set(keyword_scores.keys())

    if len(keyword_ids) < MIN_SHARED_KEYWORDS or category_id is None or article.published_at is None:
        _create_issue(session, article, category_id, keyword_scores)
        return

    since = article.published_at - timedelta(hours=CLUSTER_WINDOW_HOURS)
    candidate_ids = _find_candidate_issue_ids(session, category_id, keyword_ids, since)
    best_id, best_score = _pick_best_issue_id(session, candidate_ids, keyword_ids)

    if best_id is not None and best_score >= SIMILARITY_THRESHOLD:
        issue = session.get(Issue, best_id)
        _merge_into_issue(session, issue, article, keyword_scores)
    else:
        _create_issue(session, article, category_id, keyword_scores)


def run_issue_clustering(hours: int = 2, limit: int = BATCH_SIZE) -> int:
    """issue_id IS NULL인 최근 활성 기사를 발행 시각순으로 클러스터링한다."""
    since = datetime.now(tz=timezone.utc) - timedelta(hours=hours)
    processed = 0

    with get_session() as session:
        articles = session.execute(
            select(Article)
            .where(
                Article.status == "active",
                Article.issue_id.is_(None),
                Article.collected_at >= since,
            )
            .order_by(Article.published_at.asc().nullslast())
            .limit(limit)
        ).scalars().all()

        for article in articles:
            try:
                cluster_article(session, article)
                processed += 1
            except Exception as e:
                logger.warning("이슈 클러스터링 실패 (article_id=%s): %s", article.id, e)

    logger.info("이슈 클러스터링 완료: %d건", processed)
    return processed
