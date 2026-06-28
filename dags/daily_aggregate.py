import os
import subprocess
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


def aggregate_daily(**context):
    execution_date = context["execution_date"]
    target_date = (execution_date - timedelta(days=1)).date().isoformat()
    _run_subprocess("aggregate_daily.py", "--target_date", target_date)


def aggregate_user_stats(**context):
    execution_date = context["execution_date"]
    target_date = (execution_date - timedelta(days=1)).date().isoformat()
    _run_subprocess("aggregate_user_stats.py", "--target_date", target_date)


def aggregate_pipeline_stats(**context):
    dag_run = context["dag_run"]
    started_at = (dag_run.start_date or datetime.now(tz=timezone.utc)).isoformat()
    _run_subprocess(
        "aggregate_pipeline_stats.py",
        "--dag_id", "daily_aggregate",
        "--run_id", dag_run.run_id,
        "--started_at", started_at,
    )


def collect_trending_keywords(**context):
    execution_date = context["execution_date"]
    target_date = (execution_date - timedelta(days=1)).date().isoformat()
    _run_subprocess("collect_trending_keywords.py", "--target_date", target_date)


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
