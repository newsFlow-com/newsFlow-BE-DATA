"""
app/db/writer.py
파이프라인 결과(ClassifiedArticle)를 PostgreSQL 에 적재하는 레이어.

처리 순서:
  1. Source upsert       — sources 테이블에 언론사 등록/갱신
  2. Article upsert      — articles 테이블에 기사 적재 (URL 중복 시 skip)
  3. Category upsert     — categories 테이블에 카테고리 등록
  4. ArticleCategory     — article_categories 연결 테이블 적재
  5. Keyword upsert      — keywords 테이블에 키워드 등록
  6. ArticleKeyword      — article_keywords 연결 테이블 적재
  7. CollectLog          — 수집 이력 기록 (관리자 대시보드용)

upsert 전략:
  - articles: original_url 이 이미 존재하면 skip (ON CONFLICT DO NOTHING)
  - sources, categories, keywords: 이미 존재하면 skip
  - article_categories, article_keywords: 중복 시 skip
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.models import (
    Article,
    ArticleCategory,
    ArticleKeyword,
    Category,
    CollectLog,
    Keyword,
    Source,
)
from pipelines.classifier import ClassifiedArticle

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════
# 1. Source upsert
# ══════════════════════════════════════════════════════════════════

def _upsert_source(session: Session, article: ClassifiedArticle) -> uuid.UUID:
    """
    sources 테이블에 언론사를 등록하고 ID 를 반환한다.
    이미 존재하면 last_fetched_at 만 갱신한다.
    """
    raw = article.article
    domain = raw["source_domain"]

    stmt = (
        pg_insert(Source)
        .values(
            id=uuid.uuid4(),
            name=raw["source_name"],
            domain=domain,
            feed_url=None,          # RSS URL 은 수집기가 알고 있음 — 추후 연결
            feed_type=raw["feed_type"],
            language_code=raw["language_code"],
            tier="domestic" if raw["language_code"] == "ko" else "international",
            is_active=True,
            last_fetched_at=datetime.now(tz=timezone.utc),
        )
        .on_conflict_do_update(
            index_elements=["domain"],
            set_={"last_fetched_at": datetime.now(tz=timezone.utc)},
        )
        .returning(Source.id)
    )
    result = session.execute(stmt)
    row = result.fetchone()

    if row:
        return row[0]

    # conflict 로 반환값 없는 경우 — 기존 레코드 ID 조회
    existing = session.execute(
        select(Source.id).where(Source.domain == domain)
    ).scalar_one()
    return existing


# ══════════════════════════════════════════════════════════════════
# 2. Article upsert
# ══════════════════════════════════════════════════════════════════

def _upsert_article(
        session: Session,
        article: ClassifiedArticle,
        source_id: uuid.UUID,
) -> Optional[uuid.UUID]:
    """
    articles 테이블에 기사를 적재한다.
    original_url 이 이미 존재하면 None 을 반환한다 (skip).

    Returns:
        새로 삽입된 article ID 또는 None (중복)
    """
    raw = article.article
    article_id = uuid.uuid4()

    stmt = (
        pg_insert(Article)
        .values(
            id=article_id,
            source_id=source_id,
            original_url=raw["original_url"],
            title=raw["title"],
            summary=raw["summary"],
            content=raw["content"],
            thumbnail_url=raw["thumbnail_url"],
            author=raw["author"],
            language_code=raw["language_code"],
            status="active",
            view_count=0,
            published_at=raw["published_at"],
            collected_at=datetime.now(tz=timezone.utc),
        )
        .on_conflict_do_nothing(index_elements=["original_url"])
        .returning(Article.id)
    )
    result = session.execute(stmt)
    row = result.fetchone()

    if row:
        return row[0]

    # 이미 존재하는 URL → skip
    logger.debug(f"[Writer] 중복 URL skip: {raw['original_url'][:60]}")
    return None


# ══════════════════════════════════════════════════════════════════
# 3. Category upsert + ArticleCategory 연결
# ══════════════════════════════════════════════════════════════════

def _upsert_categories(
        session: Session,
        article_id: uuid.UUID,
        categories: list[dict],
) -> None:
    """
    분류 결과를 categories 와 article_categories 에 적재한다.
    """
    for cat in categories:
        slug = cat["slug"]

        # categories upsert
        cat_stmt = (
            pg_insert(Category)
            .values(
                id=uuid.uuid4(),
                name=cat["name"],
                slug=slug,
                is_active=True,
                display_order=0,
            )
            .on_conflict_do_nothing(index_elements=["slug"])
            .returning(Category.id)
        )
        result = session.execute(cat_stmt)
        row = result.fetchone()

        if row:
            category_id = row[0]
        else:
            category_id = session.execute(
                select(Category.id).where(Category.slug == slug)
            ).scalar_one()

        # article_categories 연결
        ac_stmt = (
            pg_insert(ArticleCategory)
            .values(
                id=uuid.uuid4(),
                article_id=article_id,
                category_id=category_id,
                classified_by=cat.get("classified_by", "rule"),
                confidence_score=cat.get("confidence"),
            )
            .on_conflict_do_nothing(
                index_elements=["article_id", "category_id"]
            )
        )
        session.execute(ac_stmt)


# ══════════════════════════════════════════════════════════════════
# 4. Keyword upsert + ArticleKeyword 연결
# ══════════════════════════════════════════════════════════════════

def _upsert_keywords(
        session: Session,
        article_id: uuid.UUID,
        keywords: list[dict],
        language_code: str = "ko",
) -> None:
    """
    키워드 추출 결과를 keywords 와 article_keywords 에 적재한다.
    """
    for kw in keywords:
        word = kw["word"]

        # keywords upsert
        kw_stmt = (
            pg_insert(Keyword)
            .values(
                id=uuid.uuid4(),
                word=word,
                word_normalized=word.lower(),
                language_code=language_code,
            )
            .on_conflict_do_nothing(index_elements=["word"])
            .returning(Keyword.id)
        )
        result = session.execute(kw_stmt)
        row = result.fetchone()

        if row:
            keyword_id = row[0]
        else:
            keyword_id = session.execute(
                select(Keyword.id).where(Keyword.word == word)
            ).scalar_one()

        # article_keywords 연결
        ak_stmt = (
            pg_insert(ArticleKeyword)
            .values(
                id=uuid.uuid4(),
                article_id=article_id,
                keyword_id=keyword_id,
                relevance_score=kw.get("score"),
                extracted_by=kw.get("extracted_by", "tfidf"),
            )
            .on_conflict_do_nothing(
                index_elements=["article_id", "keyword_id"]
            )
        )
        session.execute(ak_stmt)


# ══════════════════════════════════════════════════════════════════
# 5. CollectLog 기록
# ══════════════════════════════════════════════════════════════════

def _write_collect_log(
        session: Session,
        source_id: uuid.UUID,
        collected: int,
        duplicate: int,
        error: int,
        started_at: datetime,
        error_message: Optional[str] = None,
) -> None:
    """소스별 수집 이력을 collect_logs 에 기록한다."""
    session.add(CollectLog(
        id=uuid.uuid4(),
        source_id=source_id,
        status="success" if error == 0 else "partial",
        collected_count=collected,
        duplicate_count=duplicate,
        error_count=error,
        error_message=error_message,
        started_at=started_at,
        ended_at=datetime.now(tz=timezone.utc),
    ))


# ══════════════════════════════════════════════════════════════════
# 6. 전체 적재 진입점
# ══════════════════════════════════════════════════════════════════

class WriteResult:
    """적재 결과 요약."""
    __slots__ = ("inserted", "skipped", "errors")

    def __init__(self) -> None:
        self.inserted = 0
        self.skipped = 0
        self.errors = 0

    def __repr__(self) -> str:
        return (
            f"<WriteResult inserted={self.inserted} "
            f"skipped={self.skipped} errors={self.errors}>"
        )


def write_articles(classified_articles: list[ClassifiedArticle]) -> WriteResult:
    """
    분류 완료된 기사 목록을 PostgreSQL 에 적재한다.
    DAG 의 각 수집 태스크 마지막에서 호출하는 진입점.

    Args:
        classified_articles: classifier.classify_all() 의 반환값

    Returns:
        WriteResult (inserted / skipped / errors 건수)
    """
    result = WriteResult()
    started_at = datetime.now(tz=timezone.utc)

    # 소스별로 collect_log 를 모아서 한 번에 기록
    source_stats: dict[uuid.UUID, dict] = {}

    with get_session() as session:
        for ca in classified_articles:
            source_id: Optional[uuid.UUID] = None
            try:
                # 1. Source
                source_id = _upsert_source(session, ca)

                # 2. Article
                article_id = _upsert_article(session, ca, source_id)

                if article_id is None:
                    result.skipped += 1
                    source_stats.setdefault(source_id, {"inserted": 0, "dup": 0, "err": 0, "err_msg": None})
                    source_stats[source_id]["dup"] += 1
                    continue

                # 3. Categories
                _upsert_categories(session, article_id, ca.categories)

                # 4. Keywords
                _upsert_keywords(session, article_id, ca.keywords, ca.article["language_code"])

                result.inserted += 1
                source_stats.setdefault(source_id, {"inserted": 0, "dup": 0, "err": 0, "err_msg": None})
                source_stats[source_id]["inserted"] += 1

            except Exception as e:
                result.errors += 1
                err_str = str(e)
                logger.error(
                    f"[Writer] 적재 실패: {ca.article['original_url'][:60]} — {err_str}"
                )
                if source_id is not None:
                    source_stats.setdefault(source_id, {"inserted": 0, "dup": 0, "err": 0, "err_msg": None})
                    source_stats[source_id]["err"] += 1
                    source_stats[source_id]["err_msg"] = err_str[:500]

        # 5. CollectLog 기록
        for src_id, stats in source_stats.items():
            _write_collect_log(
                session,
                source_id=src_id,
                collected=stats["inserted"],
                duplicate=stats["dup"],
                error=stats["err"],
                error_message=stats["err_msg"],
                started_at=started_at,
            )

    logger.info(
        f"[Writer] 완료 — 적재: {result.inserted}건 / "
        f"중복 skip: {result.skipped}건 / 오류: {result.errors}건"
    )
    return result


def fetch_existing_urls(limit: int = 50_000) -> set[str]:
    """
    DB 에 이미 존재하는 URL 셋을 반환한다.
    deduplicator 의 URL 중복 제거에 사용한다.

    Args:
        limit: 최대 조회 건수 (기본 5만건 — 메모리 초과 방지)

    Returns:
        existing URL 문자열 셋
    """
    with get_session() as session:
        rows = session.execute(
            select(Article.original_url).limit(limit)
        ).fetchall()
    return {row[0] for row in rows}