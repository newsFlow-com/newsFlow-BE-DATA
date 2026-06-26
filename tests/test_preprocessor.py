"""
전처리 파이프라인 단위 테스트.
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import patch

from pipelines.preprocessor import (
    _clean_url,
    _clean_title,
    _clean_html,
    preprocess,
    preprocess_all,
)
from crawlers.base_collector import RawArticle


def _make_article(**kwargs) -> RawArticle:
    base: RawArticle = {
        "source_domain": "example.com",
        "source_name": "테스트",
        "feed_url": "https://example.com/rss",
        "original_url": "https://example.com/article/1",
        "title": "테스트 기사 제목",
        "summary": "테스트 요약",
        "content": None,
        "thumbnail_url": None,
        "author": None,
        "published_at": datetime(2025, 5, 18, tzinfo=timezone.utc),
        "language_code": "ko",
        "feed_type": "rss",
    }
    base.update(kwargs)
    return base


class TestCleanUrl:
    def test_트래킹_파라미터_제거(self):
        url = "https://example.com/article?utm_source=naver&utm_medium=news&id=1"
        result = _clean_url(url)
        assert "utm_source" not in result
        assert "id=1" in result

    def test_fragment_제거(self):
        url = "https://example.com/article#section1"
        result = _clean_url(url)
        assert "#section1" not in result

    def test_trailing_slash_제거(self):
        url = "https://example.com/article/"
        assert not _clean_url(url).endswith("/")


class TestCleanTitle:
    def test_언론사_접미사_제거(self):
        title = "삼성전자 실적 발표 - 한국경제"
        assert _clean_title(title) == "삼성전자 실적 발표"

    def test_공백_정리(self):
        title = "AI  기술  발전   속도"
        assert "  " not in _clean_title(title)

    def test_접미사_없으면_유지(self):
        title = "반도체 수출 증가"
        assert _clean_title(title) == "반도체 수출 증가"


class TestCleanHtml:
    def test_태그_제거(self):
        assert _clean_html("<b>굵은 글씨</b>") == "굵은 글씨"

    def test_html_엔티티_제거(self):
        result = _clean_html("A&amp;B")
        assert "&amp;" not in result

    def test_none_입력(self):
        assert _clean_html(None) is None

    def test_빈_문자열(self):
        assert _clean_html("   ") is None


class TestPreprocess:
    def test_정상_기사_통과(self):
        article = _make_article()
        with patch("pipelines.preprocessor._fetch_content", return_value=None):
            result = preprocess(article)
        assert result is not None
        assert result["title"] == "테스트 기사 제목"

    def test_빈_제목_제외(self):
        article = _make_article(title="")
        with patch("pipelines.preprocessor._fetch_content", return_value=None):
            result = preprocess(article)
        assert result is None

    def test_빈_url_제외(self):
        article = _make_article(original_url="")
        with patch("pipelines.preprocessor._fetch_content", return_value=None):
            result = preprocess(article)
        assert result is None

    def test_발행시각_없으면_현재시각_보정(self):
        article = _make_article(published_at=None)
        with patch("pipelines.preprocessor._fetch_content", return_value=None):
            result = preprocess(article)
        assert result is not None
        assert result["published_at"] is not None

    def test_content_없으면_newspaper_크롤링_시도(self):
        article = _make_article(content=None)
        with patch("pipelines.preprocessor._fetch_content", return_value="본문 내용입니다.") as mock_fetch:
            result = preprocess(article)
        assert result["content"] == "본문 내용입니다."
        mock_fetch.assert_called_once()

    def test_content_있으면_newspaper_미호출(self):
        article = _make_article(content="이미 있는 본문")
        with patch("pipelines.preprocessor._fetch_content") as mock_fetch:
            result = preprocess(article)
        assert result["content"] == "이미 있는 본문"
        mock_fetch.assert_not_called()


class TestPreprocessAll:
    def test_일부_제외_후_반환(self):
        articles = [
            _make_article(),
            _make_article(title=""),  # 제외 대상
            _make_article(original_url=""),  # 제외 대상
        ]
        with patch("pipelines.preprocessor._fetch_content", return_value=None):
            result = preprocess_all(articles)
        assert len(result) == 1
