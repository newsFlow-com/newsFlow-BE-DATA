"""Redis trending:articles Sorted Set 시딩 스크립트.

Usage:
    python scripts/seed_redis_trending.py
    python scripts/seed_redis_trending.py --days 3 --top_n 50
"""
import argparse
import logging
import os
import sys

_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _project_root)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

parser = argparse.ArgumentParser()
parser.add_argument("--days",  type=int, default=7,   help="집계 기간 (기본 7일)")
parser.add_argument("--top_n", type=int, default=100, help="시딩 기사 수 (기본 100)")
args = parser.parse_args()

from app.db.redis_seeder import seed_trending_articles

count = seed_trending_articles(days=args.days, top_n=args.top_n)
logger.info(f"[seed_redis_trending] 완료: {count}건")
