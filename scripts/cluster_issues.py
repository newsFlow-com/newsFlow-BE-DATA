#!/usr/bin/env python3
"""
scripts/cluster_issues.py
사용법: python scripts/cluster_issues.py [--hours N] [--limit N]
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipelines.issue_clusterer import run_issue_clustering

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="뉴스 기사 이슈 클러스터링")
    parser.add_argument("--hours", type=int, default=2, help="조회 기준 시간 (기본 2시간)")
    parser.add_argument("--limit", type=int, default=100, help="처리할 기사 수 (기본 100)")
    args = parser.parse_args()

    count = run_issue_clustering(hours=args.hours, limit=args.limit)
    print(f"이슈 클러스터링 완료: {count}건")
