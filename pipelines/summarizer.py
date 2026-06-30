"""
pipelines/summarizer.py
새로 적재된 기사를 BE-AI에 일괄 요약 요청하고 articles.ai_summary를 업데이트한다.
"""
import logging
import os
import uuid

import httpx
from sqlalchemy import update

from app.db.session import get_session
from app.models.news import Article

logger = logging.getLogger(__name__)

_BE_AI_URL = os.getenv("BE_AI_URL", "http://localhost:8000")
_TIMEOUT = 30


def _call_summarize(client: httpx.Client, article_id: uuid.UUID) -> str | None:
    try:
        resp = client.post(
            f"{_BE_AI_URL}/summarize",
            json={"article_id": str(article_id)},
            timeout=_TIMEOUT,
        )
        if resp.status_code == 200:
            return resp.json().get("ai_summary")
        logger.warning(f"[Summarizer] BE-AI {resp.status_code}: {article_id}")
    except Exception as e:
        logger.warning(f"[Summarizer] 요약 실패: {article_id} — {e}")
    return None


def summarize_and_update(article_ids: list[uuid.UUID]) -> int:
    """
    article_ids 목록을 BE-AI에 요약 요청하고 DB를 업데이트한다.

    Returns:
        업데이트된 기사 수
    """
    if not article_ids:
        return 0

    summaries: dict[uuid.UUID, str] = {}
    with httpx.Client() as client:
        for article_id in article_ids:
            result = _call_summarize(client, article_id)
            if result:
                summaries[article_id] = result

    if not summaries:
        return 0

    with get_session() as session:
        for article_id, ai_summary in summaries.items():
            session.execute(
                update(Article)
                .where(Article.id == article_id)
                .values(ai_summary=ai_summary)
            )

    logger.info(f"[Summarizer] 완료 — {len(summaries)}/{len(article_ids)}건 요약")
    return len(summaries)
