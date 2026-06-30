"""
user.py — 사용자 & 인증 관련 모델
  - users
  - social_accounts
  - refresh_tokens
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Index, String, Text, func
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, UUIDMixin


class User(UUIDMixin, TimestampMixin, Base):
    """
    사용자 통합 테이블.
    role = 'user'  → 일반 사용자 게이트 (newsflow.com)
    role = 'admin' → 관리자 게이트  (admin.newsflow.com)
    두 게이트는 같은 users 테이블을 바라보되,
    refresh_tokens.gate 컬럼으로 토큰을 분리 발급한다.
    """
    __tablename__ = "users"
    __table_args__ = (
        Index("ix_users_email", "email", unique=True),
        Index("ix_users_role_status", "role", "status"),
    )

    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    password_hash: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, comment="소셜 전용 계정은 NULL"
    )
    nickname: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    profile_image_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    role: Mapped[str] = mapped_column(
        String(20), nullable=False, default="user",
        comment="user | admin"
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active",
        comment="active | suspended | deleted"
    )
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ── Relations ──────────────────────────────────────────────
    social_accounts: Mapped[list["SocialAccount"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    bookmarks: Mapped[list["Bookmark"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    user_categories: Mapped[list["UserCategory"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    share_logs: Mapped[list["ShareLog"]] = relationship(back_populates="user")
    admin_logs: Mapped[list["AdminLog"]] = relationship(back_populates="admin")
    article_views: Mapped[list["ArticleView"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    subscriptions: Mapped[list["Subscription"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    notifications: Mapped[list["UserNotification"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class SocialAccount(UUIDMixin, Base):
    """
    소셜 OAuth 계정 연동 (카카오, 구글 등).
    provider 추가 시 이 테이블만 확장하면 된다.
    """
    __tablename__ = "social_accounts"
    __table_args__ = (
        Index("ix_social_provider_uid", "provider", "provider_uid", unique=True),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(
        String(30), nullable=False, comment="kakao | google | naver …"
    )
    provider_uid: Mapped[str] = mapped_column(String(255), nullable=False)
    access_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    refresh_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    token_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="social_accounts")


class RefreshToken(UUIDMixin, Base):
    """
    Refresh Token 관리.
    gate = 'user'  → 일반 사용자 토큰
    gate = 'admin' → 관리자 토큰 (별도 시크릿으로 서명)
    """
    __tablename__ = "refresh_tokens"
    __table_args__ = (
        Index("ix_refresh_token_hash", "token_hash", unique=True),
        Index("ix_refresh_user_gate", "user_id", "gate"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(512), nullable=False, unique=True)
    gate: Mapped[str] = mapped_column(
        String(10), nullable=False, default="user",
        comment="user | admin"
    )
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="refresh_tokens")


# 순환 참조 방지용 지연 import
from .activity import ArticleView, Bookmark, ShareLog, UserCategory  # noqa: E402
from .admin import AdminLog  # noqa: E402