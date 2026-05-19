"""
pipelines/classifier.py
기사 카테고리 분류 및 키워드 추출 파이프라인.

두 단계로 구성된다:
  1. 카테고리 분류 — 규칙 기반 키워드 매칭 (BE-AI 단계에서 AI 모델로 교체 예정)
  2. 키워드 추출  — kiwipiepy 형태소 분석 기반 명사 추출 + TF 점수화

classified_by = "rule" 로 기록해두어
추후 AI 분류 결과와 정확도 비교가 가능하도록 설계한다.
"""
import logging
import re
from typing import Optional

from crawlers.base_collector import RawArticle

logger = logging.getLogger(__name__)


# ── 카테고리 규칙 정의 ─────────────────────────────────────────────────
# (slug, 한국어명, 매칭 키워드 목록)
# 우선순위: 앞쪽 카테고리가 먼저 매칭됨
CATEGORY_RULES: list[tuple[str, str, list[str]]] = [
    ("politics", "정치", [
        "대통령", "국회", "정당", "여당", "야당", "의원", "선거", "정치",
        "국무총리", "장관", "정책", "법안", "국정",
    ]),
    ("economy", "경제", [
        "금리", "환율", "주가", "코스피", "코스닥", "gdp", "물가", "인플레",
        "경기", "수출", "무역", "재정", "예산", "경제", "증시", "채권",
    ]),
    ("stock", "주식", [
        "삼성전자", "sk하이닉스", "현대차", "카카오", "네이버", "lg",
        "주식", "종목", "시가총액", "배당", "공모주", "상장", "etf",
    ]),
    ("technology", "기술", [
        "ai", "인공지능", "반도체", "it", "빅테크", "스타트업", "앱",
        "소프트웨어", "데이터", "클라우드", "메타버스", "로봇", "자율주행",
    ]),
    ("society", "사회", [
        "사건", "사고", "범죄", "경찰", "검찰", "재판", "복지",
        "교육", "환경", "기후", "의료", "건강", "노동", "인권",
    ]),
    ("international", "국제", [
        "미국", "중국", "일본", "러시아", "유럽", "북한", "외교",
        "전쟁", "제재", "nato", "g7", "유엔", "국제",
    ]),
    ("culture", "문화", [
        "영화", "드라마", "음악", "공연", "전시", "문화", "예술",
        "책", "문학", "스포츠", "연예", "게임",
    ]),
    ("business", "비즈니스", [
        "기업", "실적", "매출", "영업이익", "인수합병", "ipo",
        "ceo", "경영", "투자", "펀드", "vc", "스타트업",
    ]),
]


class ClassifiedArticle:
    """
    분류 결과를 담는 데이터 클래스.
    DB 적재 레이어에서 article_categories, article_keywords 를 생성할 때 사용한다.
    """
    __slots__ = ("article", "categories", "keywords")

    def __init__(
            self,
            article: RawArticle,
            categories: list[dict],   # [{"slug": str, "name": str, "confidence": float}]
            keywords: list[dict],     # [{"word": str, "score": float}]
    ) -> None:
        self.article = article
        self.categories = categories
        self.keywords = keywords

    def __repr__(self) -> str:
        cats = [c["slug"] for c in self.categories]
        return f"<ClassifiedArticle title='{self.article['title'][:20]}' categories={cats}>"


# ── 1. 카테고리 분류 ───────────────────────────────────────────────────

def classify_category(article: RawArticle) -> list[dict]:
    """
    규칙 기반 카테고리 분류.
    제목 + 요약에서 카테고리 키워드를 찾아 매칭 점수를 계산한다.
    상위 2개 카테고리까지 반환 (confidence 0.5 이상만).

    Returns:
        [{"slug": str, "name": str, "confidence": float, "classified_by": "rule"}]
    """
    text = " ".join(filter(None, [
        article.get("title", ""),
        article.get("summary", ""),
    ])).lower()

    scores: list[tuple[str, str, float]] = []

    for slug, name, keywords in CATEGORY_RULES:
        matched = sum(1 for kw in keywords if kw.lower() in text)
        if matched > 0:
            # confidence = 매칭 키워드 수 / 전체 키워드 수 (0~1)
            confidence = min(matched / len(keywords), 1.0)
            scores.append((slug, name, confidence))

    # confidence 내림차순 정렬 후 상위 2개, 0.05 이상만
    scores.sort(key=lambda x: x[2], reverse=True)
    result = [
        {"slug": slug, "name": name, "confidence": round(conf, 4), "classified_by": "rule"}
        for slug, name, conf in scores[:2]
        if conf >= 0.05
    ]

    if not result:
        # 어떤 카테고리에도 매칭 안 되면 "general" 으로 분류
        result = [{"slug": "general", "name": "일반", "confidence": 0.0, "classified_by": "rule"}]

    return result


# ── 2. 키워드 추출 ────────────────────────────────────────────────────

def _extract_keywords_kiwi(text: str, top_n: int = 10) -> list[dict]:
    """
    kiwipiepy 형태소 분석기로 명사를 추출하고 TF 점수로 정렬한다.
    설치 실패 시 regex 폴백으로 전환.
    """
    try:
        from kiwipiepy import Kiwi
        kiwi = Kiwi()
        tokens = kiwi.tokenize(text)
        # NNG(일반명사), NNP(고유명사), SL(외국어) 품사만 추출
        nouns = [
            tok.form for tok in tokens
            if tok.tag in ("NNG", "NNP", "SL") and len(tok.form) >= 2
        ]
    except Exception:
        # kiwipiepy 사용 불가 시 간단한 regex 폴백
        nouns = re.findall(r"[가-힣a-zA-Z]{2,}", text)

    if not nouns:
        return []

    # TF 계산
    from collections import Counter
    counter = Counter(nouns)
    total = sum(counter.values())

    keywords = [
        {"word": word, "score": round(count / total, 4), "extracted_by": "tfidf"}
        for word, count in counter.most_common(top_n)
    ]
    return keywords


def extract_keywords(article: RawArticle, top_n: int = 10) -> list[dict]:
    """
    기사 제목 + 요약에서 키워드를 추출한다.

    Returns:
        [{"word": str, "score": float, "extracted_by": "tfidf"}]
    """
    text = " ".join(filter(None, [
        article.get("title", ""),
        article.get("summary", ""),
    ]))
    if not text.strip():
        return []

    return _extract_keywords_kiwi(text, top_n=top_n)


# ── 3. 통합 분류 진입점 ───────────────────────────────────────────────

def classify(article: RawArticle) -> ClassifiedArticle:
    """
    단일 기사에 대해 카테고리 분류 + 키워드 추출을 수행한다.
    """
    categories = classify_category(article)
    keywords = extract_keywords(article)
    return ClassifiedArticle(article=article, categories=categories, keywords=keywords)


def classify_all(articles: list[RawArticle]) -> list[ClassifiedArticle]:
    """
    전체 기사 분류 파이프라인 진입점.
    DAG 에서 전처리 + 중복제거 완료 후 이 함수를 호출한다.

    Args:
        articles: 중복 제거 완료된 기사 목록

    Returns:
        분류 결과 ClassifiedArticle 목록
    """
    results = [classify(article) for article in articles]
    logger.info(f"[분류] 완료 — {len(results)}건 처리")
    return results