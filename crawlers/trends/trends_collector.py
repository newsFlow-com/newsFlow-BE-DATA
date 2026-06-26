"""
crawlers/trends/trends_collector.py
pytrends를 이용해 Google 검색 트렌드 데이터를 수집한다.

수집 흐름:
  1. 기준 키워드 목록(SEED_KEYWORDS)을 5개씩 묶어 pytrends에 조회
  2. 각 키워드의 interest_over_time 에서 전일 검색량 지수(0-100)를 추출
  3. 지수 기준 내림차순 정렬 후 상위 N개를 반환
"""
import logging
from datetime import date, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

# pytrends는 한 번에 최대 5개 키워드 비교 가능
_BATCH_SIZE = 5

# 수집 대상 기준 키워드 — 국내 주요 뉴스 토픽
SEED_KEYWORDS: list[str] = [
    "정치", "경제", "주식", "부동산", "금리",
    "인공지능", "반도체", "삼성전자", "카카오", "네이버",
    "환율", "코스피", "코스닥", "인플레이션", "대통령",
    "국회", "선거", "외교", "북한", "미국",
]


class TrendsResult:
    """단일 키워드 트렌드 결과."""
    __slots__ = ("keyword", "search_volume_index", "trend_date")

    def __init__(self, keyword: str, search_volume_index: float, trend_date: date) -> None:
        self.keyword = keyword
        self.search_volume_index = search_volume_index
        self.trend_date = trend_date

    def __repr__(self) -> str:
        return f"<TrendsResult keyword='{self.keyword}' score={self.search_volume_index}>"


def collect_trends(
        keywords: list[str] = SEED_KEYWORDS,
        target_date: Optional[date] = None,
        top_n: int = 20,
) -> list[TrendsResult]:
    """
    pytrends로 전일 Google 검색 트렌드 지수를 수집한다.

    Args:
        keywords: 조회할 키워드 목록
        target_date: 기준 날짜 (None이면 어제)
        top_n: 반환할 상위 키워드 수

    Returns:
        TrendsResult 리스트 (search_volume_index 내림차순)
    """
    if target_date is None:
        target_date = date.today() - timedelta(days=1)

    timeframe = f"{target_date} {target_date}"

    try:
        from pytrends.request import TrendReq
    except ImportError:
        logger.warning("[Trends] pytrends 미설치 — 수집 건너뜀")
        return []

    pytrends = TrendReq(hl="ko", tz=540)  # 한국 시간대
    scores: dict[str, float] = {}

    # 5개씩 배치 처리
    for i in range(0, len(keywords), _BATCH_SIZE):
        batch = keywords[i: i + _BATCH_SIZE]
        try:
            pytrends.build_payload(batch, timeframe=timeframe, geo="KR")
            df = pytrends.interest_over_time()

            if df.empty:
                continue

            for kw in batch:
                if kw in df.columns:
                    scores[kw] = float(df[kw].mean())

        except Exception as e:
            logger.warning(f"[Trends] 배치 조회 실패 {batch}: {e}")

    results = [
        TrendsResult(kw, round(score, 2), target_date)
        for kw, score in sorted(scores.items(), key=lambda x: x[1], reverse=True)
        if score > 0
    ]

    logger.info(f"[Trends] {target_date} 기준 {len(results)}개 키워드 수집 완료")
    return results[:top_n]
