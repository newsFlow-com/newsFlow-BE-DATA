"""
admin.py — 관리자 전용 모델
  ─ 관찰(Observation) ────────────────────────────────────────────
  - admin_logs          : 관리자 행위 감사 로그
  - collect_logs        : 소스별 수집 실행 이력
  - content_quality_logs: AI 분류 품질 감사
  ─ 조작(Operation) ──────────────────────────────────────────────
  - article_reports     : 사용자 신고 → 관리자 처리 큐
  - notices             : 공지사항 (사용자 게이트 노출)
  - banners             : 배너 관리 (위치·기간 설정)
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Index,
    Integer, String, Text, func
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, UUIDMixin


# ══════════════════════════════════════════════════════
# 관찰(Observation) 테이블
# ══════════════════════════════════════════════════════

class AdminLog(UUIDMixin, Base):
    """
    관리자 행위 전체 감사 추적 (Audit Trail).
    before_value / after_value 를 JSONB 로 보관해
    어떤 엔티티든 변경 이력을 추적할 수 있다.
    target_type + target_id 조합으로 특정 엔티티의 변경 이력을 조회한다.
    """
    __tablename__ = "admin_logs"
    __table_args__ = (
        Index("ix_al_admin_created", "admin_id", "created_at"),
        Index("ix_al_target", "target_type", "target_id"),
        Index("ix_al_action", "action"),
        Index("ix_al_created", "created_at"),
    )

    admin_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    action: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="article.hide | article.delete | source.deactivate | user.suspend …"
    )
    target_type: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="article | source | user | category | banner | notice …"
    )
    target_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    before_value: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    after_value: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    admin: Mapped[Optional["User"]] = relationship(back_populates="admin_logs")


class CollectLog(UUIDMixin, Base):
    """
    소스별 수집 실행 이력.
    pipeline_stats 는 DAG 전체 지표이고,
    collect_logs 는 개별 소스 단위의 상세 이력이다.
    error_message 에 스택트레이스 일부를 저장해 디버깅에 활용한다.
    """
    __tablename__ = "collect_logs"
    __table_args__ = (
        Index("ix_cl_source_started", "source_id", "started_at"),
        Index("ix_cl_status", "status"),
        Index("ix_cl_started", "started_at"),
    )

    source_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sources.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False,
        comment="success | fail | partial"
    )
    collected_count: Mapped[int] = mapped_column(Integer, default=0)
    duplicate_count: Mapped[int] = mapped_column(Integer, default=0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    source: Mapped[Optional["Source"]] = relationship(back_populates="collect_logs")


class ContentQualityLog(UUIDMixin, Base):
    """
    관리자 대시보드 — AI 분류 품질 감사.
    AI가 분류한 결과를 관리자 또는 배치 검수가 확인하고 정오를 기록한다.
    check_type: ai_category (카테고리 분류) | duplicate (중복 감지) | keyword (키워드 추출)
    is_correct: 관리자가 판단한 정확성 여부.
    correction: 오류 시 올바른 값 (JSONB).
    """
    __tablename__ = "content_quality_logs"
    __table_args__ = (
        Index("ix_cql_article", "article_id"),
        Index("ix_cql_check_type", "check_type"),
        Index("ix_cql_is_correct", "is_correct"),
        Index("ix_cql_created", "created_at"),
    )

    article_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("articles.id", ondelete="CASCADE"),
        nullable=False,
    )
    check_type: Mapped[str] = mapped_column(
        String(30), nullable=False,
        comment="ai_category | duplicate | keyword | stock_link"
    )
    is_correct: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    original_value: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    correction: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    checked_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True, comment="관리자 ID (자동 검수는 NULL)"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    article: Mapped["Article"] = relationship(back_populates="quality_logs")


# ══════════════════════════════════════════════════════
# 조작(Operation) 테이블
# ══════════════════════════════════════════════════════

class ArticleReport(UUIDMixin, Base):
    """
    사용자 기사 신고 → 관리자 처리 큐.
    reason: 신고 사유 코드 (spam | misinformation | inappropriate | duplicate | other)
    status: pending → reviewing → resolved | dismissed
    resolved_by: 처리한 관리자 ID.
    resolution: 처리 내용 메모.
    """
    __tablename__ = "article_reports"
    __table_args__ = (
        Index("ix_ar_article", "article_id"),
        Index("ix_ar_status", "status"),
        Index("ix_ar_reporter", "reporter_id"),
        Index("ix_ar_created", "created_at"),
    )

    article_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("articles.id", ondelete="CASCADE"),
        nullable=False,
    )
    reporter_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="비로그인 신고는 NULL"
    )
    reason: Mapped[str] = mapped_column(
        String(30), nullable=False,
        comment="spam | misinformation | inappropriate | duplicate | other"
    )
    detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending",
        comment="pending | reviewing | resolved | dismissed"
    )
    resolved_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    resolution: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    article: Mapped["Article"] = relationship(back_populates="reports")


class Notice(UUIDMixin, TimestampMixin, Base):
    """
    공지사항.
    is_pinned: 상단 고정 여부.
    published_at / expired_at: 노출 기간 제어.
    target_gate: user(전체) | admin(관리자 전용) | all.
    """
    __tablename__ = "notices"
    __table_args__ = (
        Index("ix_notices_published", "published_at"),
        Index("ix_notices_target", "target_gate"),
        Index("ix_notices_pinned", "is_pinned"),
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    author_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    target_gate: Mapped[str] = mapped_column(
        String(10), nullable=False, default="user",
        comment="user | admin | all"
    )
    published_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    expired_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    author: Mapped[Optional["User"]] = relationship()


class Banner(UUIDMixin, TimestampMixin, Base):
    """
    배너 관리.
    position: 노출 위치 코드 (main_top | sidebar | article_bottom …).
    link_url: 클릭 시 이동 URL.
    display_order: 같은 position 내 우선순위.
    start_at / end_at: 노출 기간.
    click_count / impression_count: 성과 지표 (Redis 집계 후 배치 반영).
    """
    __tablename__ = "banners"
    __table_args__ = (
        Index("ix_banners_position_active", "position", "is_active"),
        Index("ix_banners_start_end", "start_at", "end_at"),
    )

    title: Mapped[str] = mapped_column(String(100), nullable=False)
    image_url: Mapped[str] = mapped_column(Text, nullable=False)
    link_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    position: Mapped[str] = mapped_column(
        String(30), nullable=False,
        comment="main_top | sidebar | article_bottom | popup …"
    )
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    start_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    end_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    click_count: Mapped[int] = mapped_column(Integer, default=0)
    impression_count: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    creator: Mapped[Optional["User"]] = relationship()


from .news import Article, Source  # noqa: E402
from .user import User  # noqa: E402