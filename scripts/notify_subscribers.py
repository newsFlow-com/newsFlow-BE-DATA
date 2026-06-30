"""
scripts/notify_subscribers.py
최근 N시간 내 적재된 기사 중 알림 미발송 기사에 대해 구독 매칭 알림을 발송한다.

Usage:
    python scripts/notify_subscribers.py [--hours 2]
"""
import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.db.session import get_session
from app.db.notifier import notify_subscribers
from app.models.news import Article
from app.models.notification import UserNotification


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hours", type=int, default=2)
    args = parser.parse_args()

    since = datetime.now(tz=timezone.utc) - timedelta(hours=args.hours)

    with get_session() as session:
        # 이미 알림이 발송된 article_id 집합
        notified_ids = set(session.execute(
            select(UserNotification.article_id)
            .where(UserNotification.sent_at >= since)
        ).scalars().all())

        # 새로 적재된 기사 중 알림 미발송 기사
        article_ids = session.execute(
            select(Article.id)
            .where(Article.collected_at >= since)
            .where(Article.status == "active")
            .where(Article.id.not_in(notified_ids) if notified_ids else True)
        ).scalars().all()

    if not article_ids:
        print("[notify] 처리할 기사 없음")
        return

    count = notify_subscribers(list(article_ids))
    print(f"[notify] 완료 — {count}건 알림 생성")


if __name__ == "__main__":
    main()
