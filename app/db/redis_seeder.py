"""
app/db/redis_seeder.py
daily_article_stats.trending_score → Redis trending:articles Sorted Set 시딩.

Redis 재시작 등으로 Sorted Set 데이터가 소실된 경우,
최근 N일 trending_score 합산값을 기반으로 재구성한다.
Airflow daily_aggregate DAG의 aggregate_daily 태스크 완료 후 호출한다.
"""
import logging
from datetime import date, timedelta

from sqlalchemy import func, select, and_

from app.db.redis_client import get_redis
from app.db.session import get_session
from app.models import Article, DailyArticleStat

TRENDING_KEY = "trending:articles"
# 25시간: 매일 DAG가 실행되므로 다음 seeding 전까지 충분히 유지
TRENDING_TTL_SECONDS = 25 * 3600

logger = logging.getLogger(__name__)


def seed_trending_articles(days: int = 7, top_n: int = 100) -> int:
    """
    최근 `days`일 trending_score 합산 기준 상위 `top_n`개 기사를
    Redis `trending:articles` Sorted Set에 ZADD한다.

    기존 키를 파이프라인으로 원자적으로 교체(DEL → ZADD → EXPIRE)하여
    조회 중 빈 상태가 발생하지 않도록 한다.

    Args:
        days:  집계 기간 (기본 7일)
        top_n: Sorted Set에 올릴 기사 수 (기본 100)

    Returns:
        시딩된 기사 수
    """
    since = date.today() - timedelta(days=days)

    with get_session() as session:
        rows = session.execute(
            select(
                DailyArticleStat.article_id,
                func.sum(DailyArticleStat.trending_score).label("total_score"),
            )
            .join(Article, Article.id == DailyArticleStat.article_id)
            .where(
                and_(
                    DailyArticleStat.stat_date >= since,
                    Article.status == "active",
                )
            )
            .group_by(DailyArticleStat.article_id)
            .order_by(func.sum(DailyArticleStat.trending_score).desc())
            .limit(top_n)
        ).fetchall()

    if not rows:
        logger.warning("[redis_seeder] 시딩 대상 기사 없음 (daily_article_stats 비어 있음)")
        return 0

    # {article_id_str: score} 형태로 변환
    score_map = {str(row.article_id): float(row.total_score) for row in rows}

    r = get_redis()
    pipe = r.pipeline()
    pipe.delete(TRENDING_KEY)
    pipe.zadd(TRENDING_KEY, score_map)
    pipe.expire(TRENDING_KEY, TRENDING_TTL_SECONDS)
    pipe.execute()

    count = len(score_map)
    logger.info(f"[redis_seeder] trending:articles 시딩 완료: {count}건 (최근 {days}일, top {top_n})")
    return count
