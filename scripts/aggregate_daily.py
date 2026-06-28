"""기사 일별 통계 집계 독립 실행 스크립트.

Usage:
    python scripts/aggregate_daily.py --target_date 2025-06-27
"""
import argparse
import os
import sys
import logging
from datetime import date

_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _project_root)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

parser = argparse.ArgumentParser()
parser.add_argument("--target_date", required=True, help="집계 대상 날짜 (YYYY-MM-DD)")
args = parser.parse_args()

target_date = date.fromisoformat(args.target_date)

from app.db.aggregator import aggregate_daily_article_stats

count = aggregate_daily_article_stats(target_date=target_date)
logger.info(f"[aggregate_daily] 완료: {count}건 ({target_date})")
