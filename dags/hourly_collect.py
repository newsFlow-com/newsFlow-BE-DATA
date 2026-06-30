import os
import subprocess
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


_NEWSFLOW_PYTHON = os.environ.get("NEWSFLOW_PYTHON", sys.executable)


def _run_subprocess(script_name: str, *args) -> None:
    """scripts/ 디렉토리의 스크립트를 venv Python으로 실행한다 (SQLAlchemy 2.0 환경)."""
    script_path = os.path.join(_project_root, "scripts", script_name)
    env = {**os.environ, "PYTHONPATH": _project_root}
    proc = subprocess.run(
        [_NEWSFLOW_PYTHON, script_path, *args],
        cwd=_project_root,
        env=env,
        timeout=600,
        capture_output=True,
        text=True,
    )
    if proc.stdout:
        logger.info(f"[{script_name}]\n{proc.stdout[-2000:]}")
    if proc.returncode != 0:
        logger.error(f"[{script_name}] stderr:\n{proc.stderr[-1000:]}")
        raise RuntimeError(f"[{script_name}] 종료 코드 {proc.returncode}")


def collect_rss(**context):
    _run_subprocess("collect_rss.py")


def collect_news_api(**context):
    _run_subprocess("collect_news_api.py")


def collect_naver_news(**context):
    _run_subprocess("collect_naver_news.py")


def summarize_articles(**context):
    _run_subprocess("summarize_articles.py", "--hours", "2", "--limit", "50")


def notify_subscribers(**context):
    _run_subprocess("notify_subscribers.py", "--hours", "2")


def collect_scrapy(spider_name: str, **context):
    """
    Scrapy 스파이더를 subprocess로 실행한다.
    Twisted reactor는 프로세스 내 재시작이 불가능하므로
    매 호출마다 새 subprocess를 생성해 실행한다.
    적재는 Scrapy 파이프라인(NewsFlowPipeline)이 직접 처리한다.
    """
    env = {
        **os.environ,
        "PYTHONPATH": _project_root,
        "SCRAPY_SETTINGS_MODULE": "crawlers.scrapy_spiders.settings",
    }
    proc = subprocess.run(
        [_NEWSFLOW_PYTHON, "-m", "scrapy", "crawl", spider_name],
        cwd=_project_root,
        env=env,
        timeout=600,
        capture_output=True,
        text=True,
    )
    if proc.stdout:
        logger.info(f"[Scrapy:{spider_name}]\n{proc.stdout[-2000:]}")
    if proc.returncode != 0:
        logger.error(f"[Scrapy:{spider_name}] stderr:\n{proc.stderr[-1000:]}")
        raise RuntimeError(f"[Scrapy:{spider_name}] 종료 코드 {proc.returncode}")


with DAG(
        dag_id="hourly_collect",
        default_args=default_args,
        description="15분 주기 뉴스 기사 수집 → 전처리 → 분류",
        schedule_interval="*/15 * * * *",
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

    task_naver = PythonOperator(
        task_id="collect_naver_news",
        python_callable=collect_naver_news,
    )

    task_chosun = PythonOperator(
        task_id="collect_scrapy_chosun",
        python_callable=collect_scrapy,
        op_kwargs={"spider_name": "chosun"},
    )

    task_joongang = PythonOperator(
        task_id="collect_scrapy_joongang",
        python_callable=collect_scrapy,
        op_kwargs={"spider_name": "joongang"},
    )

    task_yonhap = PythonOperator(
        task_id="collect_scrapy_yonhap",
        python_callable=collect_scrapy,
        op_kwargs={"spider_name": "yonhap"},
    )

    task_zdnet = PythonOperator(
        task_id="collect_scrapy_zdnet",
        python_callable=collect_scrapy,
        op_kwargs={"spider_name": "zdnet"},
    )

    task_summarize = PythonOperator(
        task_id="summarize_articles",
        python_callable=summarize_articles,
    )

    task_notify = PythonOperator(
        task_id="notify_subscribers",
        python_callable=notify_subscribers,
    )

    scrapy_tasks = [task_chosun, task_joongang, task_yonhap, task_zdnet]

    # RSS → NewsAPI → 네이버 순차, 네이버 완료 후 Scrapy 4개 병렬
    # Scrapy 완료 후 AI 요약 → 알림 발송 순차 실행
    task_rss >> task_api >> task_naver >> scrapy_tasks
    scrapy_tasks >> task_summarize >> task_notify
