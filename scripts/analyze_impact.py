#!/usr/bin/env python3
"""
scripts/analyze_impact.py
사용법: python scripts/analyze_impact.py [--limit N]
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipelines.impact_analyzer import run_impact_analysis

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="뉴스-주가 영향도 분석")
    parser.add_argument("--limit", type=int, default=200, help="처리할 연결 건수 (기본 200)")
    args = parser.parse_args()

    count = run_impact_analysis(limit=args.limit)
    print(f"영향도 분석 완료: {count}건")
