"""
app/db/es_indexer.py
Elasticsearch 기사 인덱싱 레이어.

연결 실패 시 0 반환 (파이프라인 중단 없음).
"""
import logging
import os
import uuid

from elasticsearch import Elasticsearch, helpers
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.session import get_session
from app.models import Article, ArticleCategory, ArticleKeyword
from app.models.category import Category
from app.models.keyword import Keyword

logger = logging.getLogger(__name__)
ES_INDEX = "newsflow_articles"


def _get_client():
    url = os.getenv("ELASTICSEARCH_URL", "http://localhost:9200")
    try:
        client = Elasticsearch(url, request_timeout=5)
        if not client.ping():
            logger.warning("Elasticsearch 연결 실패: %s", url)
            return None
        return client
    except Exception as e:
        logger.warning("Elasticsearch 클라이언트 오류: %s", e)
        return None


def ensure_index(client: Elasticsearch) -> None:
    if client.indices.exists(index=ES_INDEX):
        return
    client.indices.create(index=ES_INDEX, body={
        "settings": {"number_of_shards": 1, "number_of_replicas": 0},
        "mappings": {
            "properties": {
                "title":         {"type": "text",    "analyzer": "standard"},
                "summary":       {"type": "text",    "analyzer": "standard"},
                "ai_summary":    {"type": "text",    "analyzer": "standard"},
                "content":       {"type": "text",    "analyzer": "standard"},
                "categories":    {"type": "keyword"},
                "keywords":      {"type": "keyword"},
                "published_at":  {"type": "date"},
                "thumbnail_url": {"type": "keyword", "index": False},
                "original_url":  {"type": "keyword", "index": False},
                "status":        {"type": "keyword"},
            }
        }
    })
    logger.info("Elasticsearch 인덱스 생성: %s", ES_INDEX)


def _to_actions(articles):
    for a in articles:
        cats = [ac.category.slug for ac in a.article_categories if ac.category]
        kws  = [ak.keyword.word  for ak in a.article_keywords   if ak.keyword]
        yield {
            "_index": ES_INDEX,
            "_id": str(a.id),
            "_source": {
                "title":         a.title,
                "summary":       a.summary or "",
                "ai_summary":    a.ai_summary or "",
                "content":       (a.content or "")[:5000],
                "categories":    cats,
                "keywords":      kws,
                "published_at":  a.published_at.isoformat() if a.published_at else None,
                "thumbnail_url": a.thumbnail_url,
                "original_url":  a.original_url,
                "status":        a.status,
            }
        }


def _load_articles(session, stmt):
    stmt = stmt.options(
        selectinload(Article.article_categories).selectinload(ArticleCategory.category),
        selectinload(Article.article_keywords).selectinload(ArticleKeyword.keyword),
    )
    return session.execute(stmt).scalars().all()


def index_articles(article_ids: list[uuid.UUID]) -> int:
    if not article_ids:
        return 0
    client = _get_client()
    if client is None:
        return 0
    ensure_index(client)

    with get_session() as session:
        articles = _load_articles(session, select(Article).where(Article.id.in_(article_ids)))
        actions = list(_to_actions(articles))

    if not actions:
        return 0
    success, _ = helpers.bulk(client, actions, raise_on_error=False)
    logger.info("ES 인덱싱: %d건", success)
    return success


def reindex_all(limit: int = 0) -> int:
    client = _get_client()
    if client is None:
        return 0
    ensure_index(client)

    stmt = select(Article).where(Article.status == "active")
    if limit > 0:
        stmt = stmt.limit(limit)

    with get_session() as session:
        articles = _load_articles(session, stmt)
        actions = list(_to_actions(articles))

    if not actions:
        return 0
    success, _ = helpers.bulk(client, actions, chunk_size=500, raise_on_error=False)
    logger.info("ES 전체 재인덱싱: %d건", success)
    return success
