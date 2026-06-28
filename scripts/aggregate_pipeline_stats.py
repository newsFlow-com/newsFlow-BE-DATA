"""파이프라인 실행 통계 집계 독립 실행 스크립트.

Usage:
    python scripts/aggregate_pipeline_stats.py --dag_id daily_aggregate --run_id <run_id> --started_at <iso8601>
"""
import argparse
import os
import sys
import logging
from datetime import datetime, timezone

_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _project_root)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

parser = argparse.ArgumentParser()
parser.add_argument("--dag_id", required=True)
parser.add_argument("--run_id", required=True)
parser.add_argument("--started_at", required=True, help="ISO 8601 UTC 시각")
args = parser.parse_args()

started_at = datetime.fromisoformat(args.started_at)
if started_at.tzinfo is None:
    started_at = started_at.replace(tzinfo=timezone.utc)

from app.db.aggregator import aggregate_pipeline_stats

aggregate_pipeline_stats(
    dag_id=args.dag_id,
    run_id=args.run_id,
    started_at=started_at,
)
logger.info(f"[aggregate_pipeline_stats] 완료 (dag={args.dag_id})")
