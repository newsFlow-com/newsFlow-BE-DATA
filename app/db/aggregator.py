"""
app/db/aggregator.py
Airflow daily_aggregate DAG 에서 호출하는 집계 쿼리 모음.

집계 항목:
  1. daily_article_stats  — 기사별 일별 조회수·북마크·공유·트렌드 점수
  2. daily_user_stats     — 사용자 현황 스냅샷 (DAU, 신규, 이탈 등)
  3. pipeline_stats       — 당일 수집 파이프라인 요약 지표
"""
import logging
import uuid
from datetime import date, datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import func, select, and_, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db.session import get_session
from app.models import (
    Article,
    Bookmark,
    CollectLog,
    DailyArticleStat,
    DailyUserStat,
    PipelineStat,
    ShareLog,
    SocialAccount,
    User,
)

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════
# 1. 기사 일별 통계 집계
# ══════════════════════════════════════════════════════════════════

def aggregate_daily_article_stats(target_date: Optional[date] = None) -> int:
    """
    target_date 기준 기사별 집계 지표를 daily_article_stats 에 upsert.
    target_date 기본값: 어제 (Airflow @daily 는 전날 데이터를 집계)

    trending_score 계산:
        view_count * 1.0 + bookmark_count * 3.0 + share_count * 2.0

    Returns:
        집계된 기사 건수
    """
    if target_date is None:
        target_date = (datetime.now(tz=timezone.utc) - timedelta(days=1)).date()

    start_dt = datetime.combine(target_date, datetime.min.time()).replace(tzinfo=timezone.utc)
    end_dt = datetime.combine(target_date, datetime.max.time()).replace(tzinfo=timezone.utc)

    with get_session() as session:
        # 당일 발행 또는 수집된 기사 ID 목록
        article_ids = session.execute(
            select(Article.id, Article.view_count)
            .where(
                and_(
                    Article.status == "active",
                    Article.collected_at.between(start_dt, end_dt),
                    )
            )
        ).fetchall()

        if not article_ids:
            logger.info(f"[집계] {target_date} 집계 대상 기사 없음")
            return 0

        # 기사별 북마크 수
        bookmark_counts = dict(
            session.execute(
                select(Bookmark.article_id, func.count(Bookmark.id).label("cnt"))
                .where(Bookmark.created_at.between(start_dt, end_dt))
                .group_by(Bookmark.article_id)
            ).fetchall()
        )

        # 기사별 공유 수
        share_counts = dict(
            session.execute(
                select(ShareLog.target_id, func.count(ShareLog.id).label("cnt"))
                .where(
                    and_(
                        ShareLog.target_type == "article",
                        ShareLog.created_at.between(start_dt, end_dt),
                        )
                )
                .group_by(ShareLog.target_id)
            ).fetchall()
        )

        upsert_count = 0
        for article_id, view_count in article_ids:
            bm = bookmark_counts.get(article_id, 0)
            sh = share_counts.get(article_id, 0)
            trending_score = view_count * 1.0 + bm * 3.0 + sh * 2.0

            stmt = (
                pg_insert(DailyArticleStat)
                .values(
                    id=uuid.uuid4(),
                    article_id=article_id,
                    stat_date=target_date,
                    view_count=view_count,
                    bookmark_count=bm,
                    share_count=sh,
                    trending_score=trending_score,
                )
                .on_conflict_do_update(
                    index_elements=["article_id", "stat_date"],
                    set_={
                        "view_count": view_count,
                        "bookmark_count": bm,
                        "share_count": sh,
                        "trending_score": trending_score,
                    },
                )
            )
            session.execute(stmt)
            upsert_count += 1

    logger.info(f"[집계] daily_article_stats: {upsert_count}건 완료 ({target_date})")
    return upsert_count


# ══════════════════════════════════════════════════════════════════
# 2. 사용자 현황 일별 스냅샷
# ══════════════════════════════════════════════════════════════════

def aggregate_daily_user_stats(target_date: Optional[date] = None) -> None:
    """
    target_date 기준 사용자 현황을 daily_user_stats 에 upsert.

    - DAU: target_date 당일 로그인한 사용자 수
    - 신규 가입: target_date 당일 created_at 기준
    - MAU: 최근 30일 로그인 사용자 수
    - churn_rate: 30일 이상 미접속 비율
    """
    if target_date is None:
        target_date = (datetime.now(tz=timezone.utc) - timedelta(days=1)).date()

    start_dt = datetime.combine(target_date, datetime.min.time()).replace(tzinfo=timezone.utc)
    end_dt = datetime.combine(target_date, datetime.max.time()).replace(tzinfo=timezone.utc)
    thirty_days_ago = start_dt - timedelta(days=30)

    with get_session() as session:
        total = session.execute(
            select(func.count(User.id)).where(User.status != "deleted")
        ).scalar() or 0

        active_today = session.execute(
            select(func.count(User.id)).where(
                User.last_login_at.between(start_dt, end_dt)
            )
        ).scalar() or 0

        new_users = session.execute(
            select(func.count(User.id)).where(
                User.created_at.between(start_dt, end_dt)
            )
        ).scalar() or 0

        suspended = session.execute(
            select(func.count(User.id)).where(User.status == "suspended")
        ).scalar() or 0

        deleted = session.execute(
            select(func.count(User.id)).where(User.status == "deleted")
        ).scalar() or 0

        kakao_signups = session.execute(
            select(func.count(User.id))
            .join(SocialAccount, SocialAccount.user_id == User.id)
            .where(
                and_(
                    SocialAccount.provider == "kakao",
                    User.created_at.between(start_dt, end_dt),
                )
            )
        ).scalar() or 0

        # MAU
        mau = session.execute(
            select(func.count(User.id)).where(
                User.last_login_at >= thirty_days_ago
            )
        ).scalar() or 0

        # churn_rate: 30일 이상 미접속 / 전체 활성 사용자
        churned = session.execute(
            select(func.count(User.id)).where(
                and_(
                    User.status == "active",
                    User.last_login_at < thirty_days_ago,
                    )
            )
        ).scalar() or 0
        churn_rate = round(churned / total, 4) if total > 0 else 0.0

        stmt = (
            pg_insert(DailyUserStat)
            .values(
                id=uuid.uuid4(),
                stat_date=target_date,
                total_users=total,
                active_users=active_today,
                new_users=new_users,
                suspended_users=suspended,
                deleted_users=deleted,
                kakao_signup_count=kakao_signups,
                google_signup_count=0,   # 추후 구글 OAuth 추가 시 집계
                churn_rate=churn_rate,
                mau=mau,
            )
            .on_conflict_do_update(
                index_elements=["stat_date"],
                set_={
                    "total_users": total,
                    "active_users": active_today,
                    "new_users": new_users,
                    "suspended_users": suspended,
                    "deleted_users": deleted,
                    "kakao_signup_count": kakao_signups,
                    "churn_rate": churn_rate,
                    "mau": mau,
                },
            )
        )
        session.execute(stmt)

    logger.info(f"[집계] daily_user_stats 완료 ({target_date}) — DAU: {active_today}, 신규: {new_users}")


# ══════════════════════════════════════════════════════════════════
# 3. 파이프라인 지표 집계
# ══════════════════════════════════════════════════════════════════

def aggregate_pipeline_stats(
        dag_id: str,
        run_id: Optional[str],
        started_at: datetime,
) -> None:
    """
    당일 수집 파이프라인 실행 결과를 pipeline_stats 에 기록.
    daily_aggregate DAG 마지막 태스크에서 호출.

    Args:
        dag_id:     Airflow DAG ID
        run_id:     Airflow run_id
        started_at: DAG 시작 시각
    """
    target_date = started_at.date()
    start_dt = datetime.combine(target_date, datetime.min.time()).replace(tzinfo=timezone.utc)
    end_dt = datetime.now(tz=timezone.utc)

    with get_session() as session:
        # 당일 collect_logs 에서 소스별 집계
        rows = session.execute(
            select(
                func.count(CollectLog.id).label("source_count"),
                func.sum(CollectLog.collected_count).label("total_collected"),
                func.sum(CollectLog.duplicate_count).label("total_duplicate"),
                func.sum(CollectLog.error_count).label("total_error"),
            ).where(CollectLog.started_at.between(start_dt, end_dt))
        ).fetchone()

        source_count   = int(rows.source_count or 0)
        total_collected = int(rows.total_collected or 0)
        total_duplicate = int(rows.total_duplicate or 0)
        total_error     = int(rows.total_error or 0)

        status = "success" if total_error == 0 else "partial"
        duration = (end_dt - started_at).total_seconds()

        session.add(PipelineStat(
            id=uuid.uuid4(),
            dag_id=dag_id,
            run_id=run_id,
            status=status,
            collected_count=total_collected,
            duplicate_count=total_duplicate,
            error_count=total_error,
            source_count=source_count,
            duration_seconds=round(duration, 2),
            started_at=started_at,
            ended_at=end_dt,
        ))

    logger.info(
        f"[집계] pipeline_stats 완료 — "
        f"수집: {total_collected}건 / 중복: {total_duplicate}건 / 오류: {total_error}건"
    )