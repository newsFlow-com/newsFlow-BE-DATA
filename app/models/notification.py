"""
notification.py — 구독 및 사용자 알림 모델
  - subscriptions     : 키워드/카테고리 구독 설정
  - user_notifications: 발송된 알림 이력
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, UUIDMixin


class Subscription(UUIDMixin, Base):
    """
    사용자 구독 설정.
    subscription_type + value 조합으로 새 기사 매칭 여부를 판단한다.
    """
    __tablename__ = "subscriptions"
    __table_args__ = (
        Index("ix_sub_user_type_value", "user_id", "subscription_type", "value", unique=True),
        Index("ix_sub_type_value_active", "subscription_type", "value", "is_active"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    subscription_type: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="keyword | category"
    )
    value: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="키워드 단어 또는 카테고리 slug"
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="subscriptions")
    notifications: Mapped[list["UserNotification"]] = relationship(
        back_populates="subscription", cascade="all, delete-orphan"
    )


class UserNotification(UUIDMixin, Base):
    """
    알림 발송 이력.
    subscription 매칭으로 생성되고 이메일 발송 후 기록한다.
    """
    __tablename__ = "user_notifications"
    __table_args__ = (
        Index("ix_un_user_read", "user_id", "is_read"),
        Index("ix_un_article", "article_id"),
        Index("ix_un_sent", "sent_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    article_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("articles.id", ondelete="CASCADE"), nullable=False
    )
    subscription_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subscriptions.id", ondelete="SET NULL"), nullable=True
    )
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="notifications")
    article: Mapped["Article"] = relationship()
    subscription: Mapped[Optional["Subscription"]] = relationship(
        back_populates="notifications"
    )


from .news import Article  # noqa: E402
from .user import User  # noqa: E402
