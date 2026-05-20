"""
app/db/session.py
SQLAlchemy 엔진 및 세션 팩토리 설정.

환경변수 DATABASE_URL 을 읽어 엔진을 생성한다.
수집 파이프라인(Airflow DAG)과 CLI 스크립트 모두 이 모듈을 통해 세션을 얻는다.
"""
import os
from contextlib import contextmanager
from typing import Generator

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

load_dotenv()

# ── 엔진 생성 ─────────────────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL 환경변수가 설정되지 않았습니다. "
        ".env 파일을 확인하세요."
    )

engine = create_engine(
    DATABASE_URL,
    pool_size=5,           # 기본 커넥션 풀 크기
    max_overflow=10,       # 풀 초과 시 최대 추가 커넥션
    pool_pre_ping=True,    # 커넥션 유효성 사전 확인 (장시간 유휴 후 재접속 대응)
    echo=False,            # SQL 로깅: 디버깅 시 True 로 변경
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,  # commit 후 객체 재조회 방지 (수집 파이프라인 성능 최적화)
)


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """
    컨텍스트 매니저로 세션을 제공한다.
    정상 종료 시 commit, 예외 발생 시 rollback 후 세션을 닫는다.

    사용 예:
        with get_session() as session:
            session.add(article)
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def check_connection() -> bool:
    """DB 연결 상태를 확인한다. 헬스체크 / 초기화 시 사용."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False