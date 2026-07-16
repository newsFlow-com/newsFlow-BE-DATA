"""
scripts/notify_breaking_issues.py
매체 2곳 이상이 다룬 속보 이슈에 대해 카테고리 구독자에게 알림을 발송한다.

Usage:
    python scripts/notify_breaking_issues.py [--hours 2]
"""
import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.notifier import notify_breaking_issues


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hours", type=int, default=2)
    args = parser.parse_args()

    count = notify_breaking_issues(hours=args.hours)
    print(f"[notify_breaking] 완료 — {count}건 알림 생성")


if __name__ == "__main__":
    main()
