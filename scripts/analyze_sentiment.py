#!/usr/bin/env python3
"""
scripts/analyze_sentiment.py
사용법: python scripts/analyze_sentiment.py [--limit N]
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipelines.sentiment import run_sentiment_analysis

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="뉴스 기사 감성 분석")
    parser.add_argument("--limit", type=int, default=50, help="처리할 기사 수 (기본 50)")
    args = parser.parse_args()

    count = run_sentiment_analysis(limit=args.limit)
    print(f"감성 분석 완료: {count}건")
