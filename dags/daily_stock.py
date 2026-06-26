"""
dags/daily_stock.py
일별 주식 데이터 수집 DAG.

실행 흐름:
  1. upsert_stock_masters  — 종목 마스터 갱신 (월 1회 권장이나 매일 실행해도 무방)
  2. collect_stock_prices  — 전일 OHLCV 수집 및 적재
  3. link_article_stocks   — 당일 수집 기사에 종목 연결
"""
import os
import sys
import logging
from datetime import datetime, timezone, timedelta

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


def upsert_stock_masters(**context):
    """KOSPI/KOSDAQ 종목 마스터 수집 및 upsert."""
    from crawlers.stock.stock_collector import collect_stock_masters
    from app.db.stock_writer import write_stock_masters

    masters = collect_stock_masters()
    count = write_stock_masters(masters)
    context["ti"].xcom_push(key="master_count", value=count)
    logger.info(f"[DAG] upsert_stock_masters 완료: {count}건")


def collect_stock_prices(**context):
    """전일 OHLCV 수집 및 stock_prices 적재."""
    from crawlers.stock.stock_collector import collect_stock_prices
    from app.db.stock_writer import write_stock_prices

    execution_date = context["execution_date"]
    target_date = (execution_date - timedelta(days=1)).date()

    prices = collect_stock_prices(target_date=target_date)
    count = write_stock_prices(prices)
    context["ti"].xcom_push(key="price_count", value=count)
    logger.info(f"[DAG] collect_stock_prices 완료: {count}건 ({target_date})")


def link_article_stocks(**context):
    """당일 수집 기사에 종목 연결."""
    from sqlalchemy import select
    from datetime import date
    from app.db.session import get_session
    from app.models import Article
    from crawlers.stock.stock_collector import collect_stock_masters
    from pipelines.stock_linker import build_stock_index, link_stocks
    from app.db.stock_writer import write_article_stocks
    from crawlers.base_collector import RawArticle

    execution_date = context["execution_date"]
    target_date = (execution_date - timedelta(days=1)).date()
    start_dt = datetime.combine(target_date, datetime.min.time()).replace(tzinfo=timezone.utc)
    end_dt = datetime.combine(target_date, datetime.max.time()).replace(tzinfo=timezone.utc)

    masters = collect_stock_masters()
    stock_index = build_stock_index(masters)

    total_links = 0
    with get_session() as session:
        rows = session.execute(
            select(Article.original_url, Article.title, Article.summary, Article.content)
            .where(Article.collected_at.between(start_dt, end_dt))
        ).fetchall()

    for url, title, summary, content in rows:
        article: RawArticle = {
            "source_domain": "", "source_name": "", "feed_url": None,
            "original_url": url, "title": title or "", "summary": summary,
            "content": content, "thumbnail_url": None, "author": None,
            "published_at": None, "language_code": "ko", "feed_type": "rss",
        }
        links = link_stocks(article, stock_index)
        total_links += write_article_stocks(url, links)

    context["ti"].xcom_push(key="link_count", value=total_links)
    logger.info(f"[DAG] link_article_stocks 완료: {total_links}건")


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

    task_masters >> task_prices >> task_links
