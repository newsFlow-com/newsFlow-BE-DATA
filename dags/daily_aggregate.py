import os
import sys

# hourly_collect.py 와 동일한 PYTHONPATH 보정
_project_root = os.environ.get("PYTHONPATH", os.path.join(os.path.dirname(__file__), ".."))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta

default_args = {
    "owner": "newsflow",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}


def aggregate_daily():
    print("일별 기사 집계 시작 (추후 구현)")


def aggregate_user_stats():
    print("일별 사용자 통계 집계 시작 (추후 구현)")


def aggregate_pipeline_stats():
    print("수집 파이프라인 지표 집계 시작 (추후 구현)")


with DAG(
        dag_id="daily_aggregate",
        default_args=default_args,
        description="일별 기사 및 통계 집계",
        schedule_interval="@daily",
        start_date=datetime(2025, 1, 1),
        catchup=False,
) as dag:

    task_aggregate = PythonOperator(
        task_id="aggregate_daily",
        python_callable=aggregate_daily,
    )

    task_user_stats = PythonOperator(
        task_id="aggregate_user_stats",
        python_callable=aggregate_user_stats,
    )

    task_pipeline_stats = PythonOperator(
        task_id="aggregate_pipeline_stats",
        python_callable=aggregate_pipeline_stats,
    )

    # 기사 집계 → 사용자 통계 → 파이프라인 지표 순서로 실행
    task_aggregate >> task_user_stats >> task_pipeline_stats