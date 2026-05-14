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


with DAG(
        dag_id="daily_aggregate",
        default_args=default_args,
        description="일별 기사 집계",
        schedule_interval="@daily",
        start_date=datetime(2025, 1, 1),
        catchup=False,
) as dag:

    task_aggregate = PythonOperator(
        task_id="aggregate_daily",
        python_callable=aggregate_daily,
    )