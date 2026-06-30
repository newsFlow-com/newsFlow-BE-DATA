"""
app/db/notifier.py
새 기사의 키워드/카테고리를 구독 중인 사용자에게 알림을 생성하고 이메일을 발송한다.
"""
import logging
import os
import smtplib
import uuid
from datetime import datetime, timezone
from email.mime.text import MIMEText

from sqlalchemy import select

from app.db.session import get_session
from app.models.keyword import ArticleKeyword, Keyword
from app.models.category import ArticleCategory, Category
from app.models.news import Article
from app.models.notification import Subscription, UserNotification
from app.models.user import User

logger = logging.getLogger(__name__)

_SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
_SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
_SMTP_USER = os.getenv("SMTP_USER", "")
_SMTP_PASS = os.getenv("SMTP_PASS", "")
_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:3000")


def _send_email(to_email: str, article_title: str, article_id: uuid.UUID,
                subscription_type: str, value: str) -> None:
    if not _SMTP_USER or not _SMTP_PASS:
        logger.warning("[Notifier] SMTP 자격증명 없음 — 이메일 스킵")
        return

    article_url = f"{_BASE_URL}/articles/{article_id}"
    label = "키워드" if subscription_type == "keyword" else "카테고리"
    body = (
        f"구독하신 {label} '{value}'에 관련된 새 기사가 등록되었습니다.\n\n"
        f"제목: {article_title}\n"
        f"링크: {article_url}\n\n"
        f"NewsFlow에서 더 많은 기사를 확인하세요."
    )

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = f"[NewsFlow] 새 기사 알림 — {article_title[:30]}"
    msg["From"] = _SMTP_USER
    msg["To"] = to_email

    try:
        with smtplib.SMTP(_SMTP_HOST, _SMTP_PORT) as server:
            server.starttls()
            server.login(_SMTP_USER, _SMTP_PASS)
            server.send_message(msg)
    except Exception as e:
        logger.warning(f"[Notifier] 이메일 발송 실패: {to_email} — {e}")


def notify_subscribers(article_ids: list[uuid.UUID]) -> int:
    """
    새로 적재된 기사의 키워드/카테고리에 매칭되는 구독자에게
    user_notifications 레코드를 생성하고 이메일을 발송한다.

    Returns:
        생성된 알림 수
    """
    if not article_ids:
        return 0

    notification_count = 0

    with get_session() as session:
        for article_id in article_ids:
            article = session.get(Article, article_id)
            if article is None:
                continue

            # 해당 기사의 키워드 단어 목록
            keyword_rows = session.execute(
                select(Keyword.word)
                .join(ArticleKeyword, ArticleKeyword.keyword_id == Keyword.id)
                .where(ArticleKeyword.article_id == article_id)
            ).scalars().all()

            # 해당 기사의 카테고리 slug 목록
            category_rows = session.execute(
                select(Category.slug)
                .join(ArticleCategory, ArticleCategory.category_id == Category.id)
                .where(ArticleCategory.article_id == article_id)
            ).scalars().all()

            # 매칭 구독 조회 (키워드 또는 카테고리)
            subs = session.execute(
                select(Subscription)
                .where(Subscription.is_active == True)  # noqa: E712
                .where(
                    (
                        (Subscription.subscription_type == "keyword") &
                        Subscription.value.in_(keyword_rows)
                    ) |
                    (
                        (Subscription.subscription_type == "category") &
                        Subscription.value.in_(category_rows)
                    )
                )
            ).scalars().all()

            # 사용자당 중복 알림 방지 (동일 기사에 여러 구독이 매칭돼도 1건만)
            notified_users: set[uuid.UUID] = set()
            for sub in subs:
                if sub.user_id in notified_users:
                    continue
                notified_users.add(sub.user_id)

                user = session.get(User, sub.user_id)
                if user is None or not user.email:
                    continue

                notification = UserNotification(
                    id=uuid.uuid4(),
                    user_id=sub.user_id,
                    article_id=article_id,
                    subscription_id=sub.id,
                    is_read=False,
                    sent_at=datetime.now(tz=timezone.utc),
                )
                session.add(notification)
                notification_count += 1

                _send_email(
                    to_email=user.email,
                    article_title=article.title,
                    article_id=article_id,
                    subscription_type=sub.subscription_type,
                    value=sub.value,
                )

    logger.info(f"[Notifier] 완료 — {notification_count}건 알림 생성")
    return notification_count
