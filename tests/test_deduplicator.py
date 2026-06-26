"""
중복 제거 파이프라인 단위 테스트.
"""
from datetime import datetime, timezone

from pipelines.deduplicator import deduplicate_by_url, deduplicate_by_title, deduplicate
from crawlers.base_collector import RawArticle


def _make_article(url: str, title: str) -> RawArticle:
    return {
        "source_domain": "example.com",
        "source_name": "테스트",
        "feed_url": None,
        "original_url": url,
        "title": title,
        "summary": None,
        "content": None,
        "thumbnail_url": None,
        "author": None,
        "published_at": datetime(2025, 5, 18, tzinfo=timezone.utc),
        "language_code": "ko",
        "feed_type": "rss",
    }


class TestDeduplicateByUrl:
    def test_기존_url_제외(self):
        articles = [
            _make_article("https://a.com/1", "기사1"),
            _make_article("https://a.com/2", "기사2"),
        ]
        existing = {"https://a.com/1"}
        result = deduplicate_by_url(articles, existing)
        assert len(result) == 1
        assert result[0]["original_url"] == "https://a.com/2"

    def test_기존_url_없으면_전체_통과(self):
        articles = [_make_article(f"https://a.com/{i}", f"기사{i}") for i in range(5)]
        result = deduplicate_by_url(articles, set())
        assert len(result) == 5


class TestDeduplicateByTitle:
    def test_동일_제목_중복_제거(self):
        articles = [
            _make_article("https://a.com/1", "삼성전자 1분기 실적 발표"),
            _make_article("https://b.com/1", "삼성전자 1분기 실적 발표"),  # 동일 제목
        ]
        result = deduplicate_by_title(articles)
        assert len(result) == 1

    def test_유사_제목_중복_제거(self):
        articles = [
            _make_article("https://a.com/1", "삼성전자 1분기 실적 발표 깜짝 호실적"),
            _make_article("https://b.com/1", "삼성전자 1분기 실적발표 깜짝 호실적"),  # 매우 유사
        ]
        result = deduplicate_by_title(articles)
        assert len(result) == 1

    def test_다른_제목_모두_통과(self):
        articles = [
            _make_article("https://a.com/1", "삼성전자 실적 발표"),
            _make_article("https://b.com/1", "금리 인상 결정"),
            _make_article("https://c.com/1", "대통령 국회 연설"),
        ]
        result = deduplicate_by_title(articles)
        assert len(result) == 3

    def test_빈_목록(self):
        assert deduplicate_by_title([]) == []


class TestDeduplicate:
    def test_전체_파이프라인(self):
        articles = [
            _make_article("https://a.com/1", "기사 제목 A"),
            _make_article("https://a.com/1", "기사 제목 A"),  # URL 중복
            _make_article("https://b.com/1", "기사 제목 B"),
        ]
        result = deduplicate(articles, existing_urls={"https://a.com/1"})
        assert len(result) == 1
        assert result[0]["original_url"] == "https://b.com/1"
