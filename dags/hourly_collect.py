from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta

default_args = {
    "owner": "newsflow",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}


def collect_rss():
    from crawlers.rss.rss_collector import collect_all_rss
    articles = collect_all_rss()
    print(f"RSS 수집 완료: {len(articles)}건")


def collect_news_api():
    print("뉴스 API 수집 시작 (추후 구현)")


with DAG(
        dag_id="hourly_collect",
        default_args=default_args,
        description="시간별 뉴스 기사 수집",
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