import os
import sys
import logging
from datetime import datetime, timezone, timedelta

# Airflow 컨테이너 내 PYTHONPATH 보정
_project_root = os.environ.get("PYTHONPATH", os.path.join(os.path.dirname(__file__), ".."))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from airflow import DAG
from airflow.operators.python import PythonOperator

logger = logging.getLogger(__name__)

default_args = {
    "owner": "newsflow",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}


def aggregate_daily(**context):
    """기사별 일별 조회수·북마크·공유·트렌드 점수 집계."""
    from app.db.aggregator import aggregate_daily_article_stats

    execution_date = context["execution_date"]
    target_date = (execution_date - timedelta(days=1)).date()

    count = aggregate_daily_article_stats(target_date=target_date)
    context["ti"].xcom_push(key="article_stat_count", value=count)
    logger.info(f"[DAG] aggregate_daily 완료: {count}건 ({target_date})")


def aggregate_user_stats(**context):
    """사용자 현황 일별 스냅샷 (DAU/MAU/신규/이탈률) 집계."""
    from app.db.aggregator import aggregate_daily_user_stats

    execution_date = context["execution_date"]
    target_date = (execution_date - timedelta(days=1)).date()

    aggregate_daily_user_stats(target_date=target_date)
    logger.info(f"[DAG] aggregate_user_stats 완료 ({target_date})")


def aggregate_pipeline_stats(**context):
    """당일 수집 파이프라인 실행 요약 지표 기록."""
    from app.db.aggregator import aggregate_pipeline_stats

    dag_run = context["dag_run"]
    started_at = dag_run.start_date or datetime.now(tz=timezone.utc)

    aggregate_pipeline_stats(
        dag_id="daily_aggregate",
        run_id=dag_run.run_id,
        started_at=started_at,
    )
    logger.info("[DAG] aggregate_pipeline_stats 완료")


def collect_trending_keywords(**context):
    """Google Trends 키워드 수집 → trending_keywords 적재."""
    from crawlers.trends.trends_collector import collect_trends
    from app.db.writer import write_trending_keywords

    execution_date = context["execution_date"]
    target_date = (execution_date - timedelta(days=1)).date()

    results = collect_trends(target_date=target_date)
    count = write_trending_keywords(results)
    context["ti"].xcom_push(key="trending_keyword_count", value=count)
    logger.info(f"[DAG] collect_trending_keywords 완료: {count}건 ({target_date})")


with DAG(
        dag_id="daily_aggregate",
        default_args=default_args,
        description="일별 기사·사용자·파이프라인 통계 집계",
        schedule_interval="@daily",
        start_date=datetime(2025, 1, 1),
        catchup=False,
) as dag:

    task_article = PythonOperator(
        task_id="aggregate_daily",
        python_callable=aggregate_daily,
    )

    task_user = PythonOperator(
        task_id="aggregate_user_stats",
        python_callable=aggregate_user_stats,
    )

    task_pipeline = PythonOperator(
        task_id="aggregate_pipeline_stats",
        python_callable=aggregate_pipeline_stats,
    )

    task_trends = PythonOperator(
        task_id="collect_trending_keywords",
        python_callable=collect_trending_keywords,
    )

    task_article >> task_user >> task_pipeline >> task_trends