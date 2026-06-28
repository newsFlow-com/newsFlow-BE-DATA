"""Google Trends 키워드 수집 → trending_keywords 적재 독립 실행 스크립트.

Usage:
    python scripts/collect_trending_keywords.py --target_date 2025-06-27
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
parser.add_argument("--target_date", required=True, help="수집 대상 날짜 (YYYY-MM-DD)")
args = parser.parse_args()

target_date = date.fromisoformat(args.target_date)

from crawlers.trends.trends_collector import collect_trends
from app.db.writer import write_trending_keywords

results = collect_trends(target_date=target_date)
count = write_trending_keywords(results)
logger.info(f"[collect_trending_keywords] 완료: {count}건 ({target_date})")
