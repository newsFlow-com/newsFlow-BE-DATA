"""
activity.py — 사용자 활동 모델
  - bookmarks
  - user_categories
  - share_logs
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, UUIDMixin


class Bookmark(UUIDMixin, Base):
    """사용자 기사 북마크."""
    __tablename__ = "bookmarks"
    __table_args__ = (
        Index("ix_bm_user_article", "user_id", "article_id", unique=True),
        Index("ix_bm_user", "user_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    article_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("articles.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="bookmarks")
    article: Mapped["Article"] = relationship(back_populates="bookmarks")


class UserCategory(UUIDMixin, Base):
    """
    사용자 관심 카테고리 등록.
    preference_weight: 사용자가 직접 설정하거나 행동 기반으로 자동 조정 (1-10).
    """
    __tablename__ = "user_categories"
    __table_args__ = (
        Index("ix_uc_user_category", "user_id", "category_id", unique=True),
        Index("ix_uc_user", "user_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="CASCADE"),
        nullable=False,
    )
    preference_weight: Mapped[int] = mapped_column(Integer, default=5)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="user_categories")
    category: Mapped["Category"] = relationship(back_populates="user_categories")


class ShareLog(UUIDMixin, Base):
    """
    공유 이벤트 로그.
    target_type 으로 기사/차트/주식 공유를 단일 테이블에서 관리.
    channel 로 카카오/링크복사/클립보드 등 채널별 분석 가능.
    """
    __tablename__ = "share_logs"
    __table_args__ = (
        Index("ix_sl_user", "user_id"),
        Index("ix_sl_target", "target_type", "target_id"),
        Index("ix_sl_channel", "channel"),
        Index("ix_sl_created", "created_at"),
    )

    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="비로그인 공유는 NULL"
    )
    target_type: Mapped[str] = mapped_column(
        String(20), nullable=False,
        comment="article | chart | stock"
    )
    target_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    channel: Mapped[str] = mapped_column(
        String(30), nullable=False,
        comment="kakao | link | clipboard | twitter …"
    )
    ip_address: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped[Optional["User"]] = relationship(back_populates="share_logs")


from .category import Category  # noqa: E402
from .user import User  # noqa: E402