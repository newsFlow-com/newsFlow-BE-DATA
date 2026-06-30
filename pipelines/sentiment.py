"""
pipelines/sentiment.py — BE-AI /sentiment 호출 → articles.sentiment 업데이트
"""
import logging
import os

import requests
from sqlalchemy import select, update

from app.db.session import get_session
from app.models import Article

logger = logging.getLogger(__name__)

AI_SERVER_URL = os.getenv("AI_SERVER_URL", "http://localhost:8000")
BATCH_SIZE = 50


def _call_ai_sentiment(article_id: str) -> dict | None:
    try:
        resp = requests.post(
            f"{AI_SERVER_URL}/sentiment",
            json={"article_id": article_id},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.warning("감성 분석 API 오류 (id=%s): %s", article_id, e)
        return None


def run_sentiment_analysis(limit: int = BATCH_SIZE) -> int:
    """sentiment IS NULL인 활성 기사를 limit개 처리."""
    updated = 0

    with get_session() as db:
        stmt = (
            select(Article.id, Article.title)
            .where(Article.status == "active", Article.sentiment.is_(None))
            .order_by(Article.collected_at.desc())
            .limit(limit)
        )
        rows = db.execute(stmt).all()

    for row in rows:
        result = _call_ai_sentiment(str(row.id))
        if result is None:
            continue

        sentiment = result.get("sentiment", "neutral")
        score = float(result.get("score", 0.5))

        with get_session() as db:
            db.execute(
                update(Article)
                .where(Article.id == row.id)
                .values(sentiment=sentiment, sentiment_score=score)
            )
            db.commit()
        updated += 1

    logger.info("감성 분석 완료: %d건", updated)
    return updated
