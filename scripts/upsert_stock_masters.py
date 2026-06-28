"""KOSPI/KOSDAQ 종목 마스터 수집 및 upsert 독립 실행 스크립트."""
import os
import sys
import logging

_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _project_root)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

from crawlers.stock.stock_collector import collect_stock_masters
from app.db.stock_writer import write_stock_masters

masters = collect_stock_masters()
count = write_stock_masters(masters)
logger.info(f"[upsert_stock_masters] 완료: {count}건")
