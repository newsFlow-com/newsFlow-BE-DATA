"""
분류 파이프라인 단위 테스트.
"""
from datetime import datetime, timezone
from unittest.mock import patch

from pipelines.classifier import classify_category, extract_keywords, classify, classify_all
from crawlers.base_collector import RawArticle


def _make_article(title: str, summary: str = "") -> RawArticle:
    return {
        "source_domain": "example.com",
        "source_name": "테스트",
        "feed_url": None,
        "original_url": "https://example.com/1",
        "title": title,
        "summary": summary,
        "content": None,
        "thumbnail_url": None,
        "author": None,
        "published_at": datetime(2025, 5, 18, tzinfo=timezone.utc),
        "language_code": "ko",
        "feed_type": "rss",
    }


class TestClassifyCategory:
    def test_정치_분류(self):
        article = _make_article("대통령 국무회의 주재, 주요 정책 논의")
        result = classify_category(article)
        slugs = [c["slug"] for c in result]
        assert "politics" in slugs

    def test_경제_분류(self):
        article = _make_article("금리 인상 결정, 환율 급등")
        result = classify_category(article)
        slugs = [c["slug"] for c in result]
        assert "economy" in slugs

    def test_기술_분류(self):
        article = _make_article("인공지능 반도체 시장 급성장", "AI 빅테크 투자 확대")
        result = classify_category(article)
        slugs = [c["slug"] for c in result]
        assert "technology" in slugs

    def test_매칭_없으면_general(self):
        article = _make_article("asdfjklqwerty 알수없는내용")
        result = classify_category(article)
        assert result[0]["slug"] == "general"

    def test_confidence_범위(self):
        article = _make_article("대통령 선거 국회 정당")
        result = classify_category(article)
        for cat in result:
            assert 0.0 <= cat["confidence"] <= 1.0

    def test_최대_2개_반환(self):
        article = _make_article("대통령 금리 인공지능 주식 사건 전쟁")
        result = classify_category(article)
        assert len(result) <= 2


class TestExtractKeywords:
    def test_키워드_추출(self):
        article = _make_article("삼성전자 반도체 실적 발표", "반도체 수출 증가")
        with patch("pipelines.classifier.Kiwi") as MockKiwi:
            mock_kiwi = MockKiwi.return_value
            mock_kiwi.tokenize.return_value = []
            result = extract_keywords(article)
        assert isinstance(result, list)

    def test_빈_텍스트(self):
        article = _make_article("")
        result = extract_keywords(article)
        assert result == []


class TestClassify:
    def test_반환_타입(self):
        from pipelines.classifier import ClassifiedArticle
        article = _make_article("경제 금리 인상 결정")
        result = classify(article)
        assert isinstance(result, ClassifiedArticle)
        assert len(result.categories) > 0

    def test_classify_all(self):
        articles = [
            _make_article("대통령 발언"),
            _make_article("주식 시장 급락"),
        ]
        results = classify_all(articles)
        assert len(results) == 2
