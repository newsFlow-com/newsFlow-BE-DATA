"""
scripts/reindex_all.py
전체 기사를 Elasticsearch 에 재인덱싱하는 CLI.
"""
import argparse
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.db.es_indexer import reindex_all


def main():
    parser = argparse.ArgumentParser(description="Elasticsearch 전체 재인덱싱")
    parser.add_argument("--limit", type=int, default=0, help="최대 처리 건수 (0 = 전체)")
    args = parser.parse_args()

    count = reindex_all(limit=args.limit)
    print(f"재인덱싱 완료: {count}건")


if __name__ == "__main__":
    main()
