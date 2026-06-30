"""
scripts/summarize_articles.py
최근 N시간 내 ai_summary 없는 기사를 BE-AI에 요약 요청한다.

Usage:
    python scripts/summarize_articles.py [--hours 2] [--limit 50]
"""
import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.db.session import get_session
from app.models.news import Article
from pipelines.summarizer import summarize_and_update


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hours", type=int, default=2)
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()

    since = datetime.now(tz=timezone.utc) - timedelta(hours=args.hours)

    with get_session() as session:
        rows = session.execute(
            select(Article.id)
            .where(Article.collected_at >= since)
            .where(Article.ai_summary.is_(None))
            .where(Article.status == "active")
            .limit(args.limit)
        ).scalars().all()

    if not rows:
        print("[summarize] 처리할 기사 없음")
        return

    count = summarize_and_update(list(rows))
    print(f"[summarize] 완료 — {count}/{len(rows)}건")


if __name__ == "__main__":
    main()
