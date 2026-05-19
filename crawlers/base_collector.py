"""
crawlers/base_collector.py
모든 수집기가 구현해야 하는 추상 베이스 클래스.

수집기 교체 시 이 인터페이스만 유지하면 DAG 코드 변경 없이 교체 가능.
반환 타입을 RawArticle TypedDict 로 통일해 파이프라인 전체에서 동일한 구조를 보장한다.
"""
from abc import ABC, abstractmethod
from typing import TypedDict, Optional
from datetime import datetime


class RawArticle(TypedDict):
    """
    수집기가 반환하는 원시 기사 데이터 구조.
    모든 수집기는 이 구조로 정규화해서 반환해야 한다.
    """
    source_domain: str          # 언론사 도메인 (예: "hani.co.kr")
    source_name: str            # 언론사 이름 (예: "한겨레")
    original_url: str           # 기사 원문 URL (중복 제거 키)
    title: str                  # 기사 제목
    summary: Optional[str]      # 요약 / 리드문 (없으면 None)
    content: Optional[str]      # 본문 (RSS는 보통 None)
    thumbnail_url: Optional[str]  # 썸네일 이미지 URL
    author: Optional[str]       # 저자
    published_at: Optional[datetime]  # 발행 시각 (파싱 실패 시 None)
    language_code: str          # "ko" | "en" 등
    feed_type: str              # "rss" | "newsapi" | "crawl"


class BaseCollector(ABC):
    """수집기 추상 베이스."""

    @abstractmethod
    def fetch(self, **kwargs) -> list[RawArticle]:
        """
        기사 목록을 수집해서 RawArticle 리스트로 반환.
        구현체는 내부 예외를 잡아서 빈 리스트 또는 부분 결과를 반환해야 한다.
        DAG 레이어까지 예외가 올라오지 않도록 한다.
        """
        ...

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}>"