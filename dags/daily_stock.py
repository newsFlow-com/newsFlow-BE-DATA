"""
dags/daily_stock.py
일별 주식 데이터 수집 DAG.

실행 흐름:
  1. upsert_stock_masters  — 종목 마스터 갱신 (월 1회 권장이나 매일 실행해도 무방)
  2. collect_stock_prices  — 전일 OHLCV 수집 및 적재
  3. link_article_stocks   — 당일 수집 기사에 종목 연결
  4. analyze_impact        — 기사-종목 연결의 발행 전후 주가 변동 계산
"""
import os
import subprocess
import sys
import logging
from datetime import datetime, timedelta

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


def upsert_stock_masters(**context):
    _run_subprocess("upsert_stock_masters.py")


def collect_stock_prices(**context):
    execution_date = context["execution_date"]
    target_date = (execution_date - timedelta(days=1)).date().isoformat()
    _run_subprocess("collect_stock_prices.py", "--target_date", target_date)


def link_article_stocks(**context):
    execution_date = context["execution_date"]
    target_date = (execution_date - timedelta(days=1)).date().isoformat()
    _run_subprocess("link_article_stocks.py", "--target_date", target_date)


def analyze_impact(**context):
    _run_subprocess("analyze_impact.py", "--limit", "200")


with DAG(
        dag_id="daily_stock",
        default_args=default_args,
        description="일별 주식 종목 마스터·주가 수집 및 기사-종목 연결",
        schedule_interval="0 17 * * 1-5",  # 평일 오후 5시 (장 마감 후)
        start_date=datetime(2025, 1, 1),
        catchup=False,
) as dag:

    task_masters = PythonOperator(
        task_id="upsert_stock_masters",
        python_callable=upsert_stock_masters,
    )

    task_prices = PythonOperator(
        task_id="collect_stock_prices",
        python_callable=collect_stock_prices,
    )

    task_links = PythonOperator(
        task_id="link_article_stocks",
        python_callable=link_article_stocks,
    )

    task_impact = PythonOperator(
        task_id="analyze_impact",
        python_callable=analyze_impact,
    )

    task_masters >> task_prices >> task_links >> task_impact
