"""
stats.py — 통계 집계 테이블
  - daily_article_stats   : 기사별 일별 지표 (Airflow 배치)
  - daily_user_stats      : 사용자 현황 일별 스냅샷 (관리자 대시보드)
  - pipeline_stats        : 수집 파이프라인 실행 지표 (관리자 대시보드)
  - api_request_logs      : API 요청 성능 로그 (관리자 대시보드)
"""
import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    BigInteger, Date, DateTime, Float,
    ForeignKey, Index, Integer, String, func
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, UUIDMixin


# ── 1. 기사 일별 통계 ─────────────────────────────────────────────

class DailyArticleStat(UUIDMixin, Base):
    """
    기사 단위 일별 지표.
    Airflow daily_aggregate DAG 가 매일 자정 후 집계해 적재한다.
    trending_score 는 조회수·북마크·공유를 가중 합산한 점수.
    """
    __tablename__ = "daily_article_stats"
    __table_args__ = (
        Index("ix_das_article_date", "article_id", "stat_date", unique=True),
        Index("ix_das_date", "stat_date"),
        Index("ix_das_trending", "trending_score"),
    )

    article_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("articles.id", ondelete="CASCADE"),
        nullable=False,
    )
    stat_date: Mapped[date] = mapped_column(Date, nullable=False)
    view_count: Mapped[int] = mapped_column(Integer, default=0)
    bookmark_count: Mapped[int] = mapped_column(Integer, default=0)
    share_count: Mapped[int] = mapped_column(Integer, default=0)
    trending_score: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    article: Mapped["Article"] = relationship(back_populates="daily_stats")


# ── 2. 사용자 일별 현황 (관리자 관찰용) ────────────────────────────

class DailyUserStat(UUIDMixin, Base):
    """
    관리자 대시보드 — 사용자 지표 일별 스냅샷.
    DAU, 신규 가입, 이탈률 등을 Airflow 배치로 집계.
    churn_rate: 30일 이상 미접속 사용자 비율.
    kakao_signup_count: 소셜 로그인 유입 추적.
    """
    __tablename__ = "daily_user_stats"
    __table_args__ = (
        Index("ix_dus_date", "stat_date", unique=True),
    )

    stat_date: Mapped[date] = mapped_column(Date, nullable=False, unique=True)
    total_users: Mapped[int] = mapped_column(Integer, default=0)
    active_users: Mapped[int] = mapped_column(Integer, default=0, comment="DAU")
    new_users: Mapped[int] = mapped_column(Integer, default=0)
    suspended_users: Mapped[int] = mapped_column(Integer, default=0)
    deleted_users: Mapped[int] = mapped_column(Integer, default=0)
    kakao_signup_count: Mapped[int] = mapped_column(Integer, default=0)
    google_signup_count: Mapped[int] = mapped_column(Integer, default=0)
    churn_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    mau: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="MAU")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# ── 3. 수집 파이프라인 지표 (관리자 관찰용) ────────────────────────

class PipelineStat(UUIDMixin, Base):
    """
    관리자 대시보드 — Airflow DAG 실행 결과 지표.
    dag_id: Airflow DAG 식별자.
    run_id: Airflow run_id (외부 키 없이 문자열로 보관).
    collected_count: 이번 실행에서 새로 적재된 기사 수.
    duplicate_count: 중복으로 skip된 기사 수.
    error_count: 수집 실패한 기사/소스 수.
    duration_seconds: 실행 소요 시간.
    """
    __tablename__ = "pipeline_stats"
    __table_args__ = (
        Index("ix_ps_dag_started", "dag_id", "started_at"),
        Index("ix_ps_status", "status"),
        Index("ix_ps_started", "started_at"),
    )

    dag_id: Mapped[str] = mapped_column(String(100), nullable=False)
    run_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False,
        comment="success | partial | fail | running"
    )
    collected_count: Mapped[int] = mapped_column(Integer, default=0)
    duplicate_count: Mapped[int] = mapped_column(Integer, default=0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    source_count: Mapped[int] = mapped_column(
        Integer, default=0, comment="이번 실행에서 시도한 소스 수"
    )
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# ── 4. API 요청 성능 로그 (관리자 관찰용) ──────────────────────────

class ApiRequestLog(UUIDMixin, Base):
    """
    관리자 대시보드 — API 성능 모니터링.
    모든 요청을 로깅하는 것은 부하가 크므로,
    Middleware에서 샘플링(기본 10%) + 느린 요청(> 500ms) 전수 기록 방식을 권장.
    gate: 어느 게이트에서 발생한 요청인지 구분.
    response_time_ms: 응답 시간 (밀리초).
    """
    __tablename__ = "api_request_logs"
    __table_args__ = (
        Index("ix_arl_endpoint_created", "endpoint", "created_at"),
        Index("ix_arl_gate", "gate"),
        Index("ix_arl_status_code", "status_code"),
        Index("ix_arl_response_time", "response_time_ms"),
        Index("ix_arl_created", "created_at"),
    )

    gate: Mapped[str] = mapped_column(
        String(10), nullable=False,
        comment="user | admin"
    )
    method: Mapped[str] = mapped_column(String(10), nullable=False)
    endpoint: Mapped[str] = mapped_column(String(255), nullable=False)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    response_time_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True, comment="인증된 요청의 경우만"
    )
    ip_address: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


from .news import Article  # noqa: E402