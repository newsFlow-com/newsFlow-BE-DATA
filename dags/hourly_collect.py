import os
import sys
import logging

# Airflow 컨테이너 내 PYTHONPATH 보정
_project_root = os.environ.get("PYTHONPATH", os.path.join(os.path.dirname(__file__), ".."))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

default_args = {
    "owner": "newsflow",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}


def collect_rss(**context):
    """RSS 수집 → 전처리 → 중복제거 → 분류 → DB 적재."""
    from crawlers.rss.rss_collector import collect_all_rss
    from pipelines.preprocessor import preprocess_all
    from pipelines.deduplicator import deduplicate
    from pipelines.classifier import classify_all
    from app.db.writer import write_articles, fetch_existing_urls

    # 1. 수집
    raw = collect_all_rss()
    logger.info(f"[RSS] 수집: {len(raw)}건")

    # 2. 전처리
    cleaned = preprocess_all(raw)

    # 3. 중복 제거 (DB 기존 URL + 배치 내 유사 제목)
    existing_urls = fetch_existing_urls()
    deduped = deduplicate(cleaned, existing_urls=existing_urls)

    # 4. 분류
    classified = classify_all(deduped)
    logger.info(f"[RSS] 최종 적재 대상: {len(classified)}건")

    # 5. DB 적재
    result = write_articles(classified)
    logger.info(f"[RSS] DB 적재 완료: {result}")

    # 6. XCom push (모니터링용)
    context["ti"].xcom_push(key="rss_inserted", value=result.inserted)
    context["ti"].xcom_push(key="rss_skipped", value=result.skipped)
    return result.inserted


def collect_news_api(**context):
    """NewsAPI 수집 → 전처리 → 중복제거 → 분류 → DB 적재."""
    from crawlers.news_api.news_api_collector import collect_news_api as fetch_api
    from pipelines.preprocessor import preprocess_all
    from pipelines.deduplicator import deduplicate
    from pipelines.classifier import classify_all
    from app.db.writer import write_articles, fetch_existing_urls

    raw = fetch_api()
    logger.info(f"[NewsAPI] 수집: {len(raw)}건")

    cleaned = preprocess_all(raw)
    existing_urls = fetch_existing_urls()
    deduped = deduplicate(cleaned, existing_urls=existing_urls)
    classified = classify_all(deduped)

    result = write_articles(classified)
    logger.info(f"[NewsAPI] DB 적재 완료: {result}")

    context["ti"].xcom_push(key="newsapi_inserted", value=result.inserted)
    context["ti"].xcom_push(key="newsapi_skipped", value=result.skipped)
    return result.inserted


with DAG(
        dag_id="hourly_collect",
        default_args=default_args,
        description="시간별 뉴스 기사 수집 → 전처리 → 분류",
        schedule_interval="@hourly",
        start_date=datetime(2025, 1, 1),
        catchup=False,
) as dag:

    task_rss = PythonOperator(
        task_id="collect_rss",
        python_callable=collect_rss,
    )

    task_api = PythonOperator(
        task_id="collect_news_api",
        python_callable=collect_news_api,
    )

    task_rss >> task_api