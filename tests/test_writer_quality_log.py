"""
writer.py — content_quality_logs 기록 단위 테스트.
"""
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch, call

import pytest

from app.db.writer import _write_quality_log
from app.models.admin import ContentQualityLog
from crawlers.base_collector import RawArticle
from pipelines.classifier import ClassifiedArticle


def _make_raw_article(**kwargs) -> RawArticle:
    base: RawArticle = {
        "source_domain": "example.com",
        "source_name": "테스트",
        "feed_url": None,
        "original_url": "https://example.com/1",
        "title": "테스트 기사",
        "summary": "테스트 요약",
        "content": None,
        "thumbnail_url": None,
        "author": None,
        "published_at": datetime(2025, 6, 1, tzinfo=timezone.utc),
        "language_code": "ko",
        "feed_type": "rss",
    }
    base.update(kwargs)
    return base


def _make_classified(title: str = "경제 기사") -> ClassifiedArticle:
    raw = _make_raw_article(title=title)
    return ClassifiedArticle(
        article=raw,
        categories=[{"slug": "economy", "name": "경제", "confidence": 0.3, "classified_by": "rule"}],
        keywords=[{"word": "금리", "score": 0.5}, {"word": "환율", "score": 0.3}],
    )


class TestWriteQualityLog:

    def test_session_add가_한_번_호출된다(self):
        session = MagicMock()
        article_id = uuid.uuid4()
        categories = [{"slug": "economy", "confidence": 0.3}]
        keywords = [{"word": "금리"}]

        _write_quality_log(session, article_id, categories, keywords)

        session.add.assert_called_once()

    def test_ContentQualityLog_인스턴스가_추가된다(self):
        session = MagicMock()
        article_id = uuid.uuid4()

        _write_quality_log(session, article_id, [], [])

        added = session.add.call_args[0][0]
        assert isinstance(added, ContentQualityLog)

    def test_article_id가_정확히_기록된다(self):
        session = MagicMock()
        article_id = uuid.uuid4()

        _write_quality_log(session, article_id, [], [])

        added = session.add.call_args[0][0]
        assert added.article_id == article_id

    def test_check_type이_ai_category다(self):
        session = MagicMock()

        _write_quality_log(session, uuid.uuid4(), [], [])

        added = session.add.call_args[0][0]
        assert added.check_type == "ai_category"

    def test_is_correct가_None이다(self):
        """관리자 검수 전이므로 미판정 상태"""
        session = MagicMock()

        _write_quality_log(session, uuid.uuid4(), [], [])

        added = session.add.call_args[0][0]
        assert added.is_correct is None

    def test_original_value에_categories가_포함된다(self):
        session = MagicMock()
        categories = [{"slug": "tech", "name": "기술", "confidence": 0.5, "classified_by": "rule"}]

        _write_quality_log(session, uuid.uuid4(), categories, [])

        added = session.add.call_args[0][0]
        assert added.original_value["categories"] == categories

    def test_original_value에_keyword_count가_포함된다(self):
        session = MagicMock()
        keywords = [{"word": "ai"}, {"word": "반도체"}, {"word": "클라우드"}]

        _write_quality_log(session, uuid.uuid4(), [], keywords)

        added = session.add.call_args[0][0]
        assert added.original_value["top_keyword_count"] == 3

    def test_keyword가_없어도_오류_없이_기록된다(self):
        session = MagicMock()

        _write_quality_log(session, uuid.uuid4(), [], [])

        session.add.assert_called_once()
        added = session.add.call_args[0][0]
        assert added.original_value["top_keyword_count"] == 0


class TestWriteArticlesQualityLogIntegration:

    def test_신규_기사_적재_시_quality_log가_기록된다(self):
        """write_articles가 새 기사를 저장할 때 _write_quality_log를 호출한다."""
        ca = _make_classified()

        with patch("app.db.writer.get_session") as mock_get_session, \
             patch("app.db.writer._upsert_source", return_value=uuid.uuid4()), \
             patch("app.db.writer._upsert_article", return_value=uuid.uuid4()) as mock_article, \
             patch("app.db.writer._upsert_categories"), \
             patch("app.db.writer._upsert_keywords"), \
             patch("app.db.writer._write_quality_log") as mock_quality_log, \
             patch("app.db.writer._write_collect_log"):

            mock_session = MagicMock()
            mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

            from app.db.writer import write_articles
            write_articles([ca])

        mock_quality_log.assert_called_once()

    def test_중복_기사는_quality_log를_기록하지_않는다(self):
        """article_id가 None(중복)이면 quality log를 건너뛴다."""
        ca = _make_classified()

        with patch("app.db.writer.get_session") as mock_get_session, \
             patch("app.db.writer._upsert_source", return_value=uuid.uuid4()), \
             patch("app.db.writer._upsert_article", return_value=None), \
             patch("app.db.writer._write_quality_log") as mock_quality_log, \
             patch("app.db.writer._write_collect_log"):

            mock_session = MagicMock()
            mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

            from app.db.writer import write_articles
            write_articles([ca])

        mock_quality_log.assert_not_called()

    def test_여러_기사_적재_시_각각_quality_log가_기록된다(self):
        """3개 기사 중 2개 신규, 1개 중복이면 quality log 2건 기록."""
        articles = [_make_classified(f"기사{i}") for i in range(3)]
        article_ids = [uuid.uuid4(), None, uuid.uuid4()]  # 두 번째가 중복

        with patch("app.db.writer.get_session") as mock_get_session, \
             patch("app.db.writer._upsert_source", return_value=uuid.uuid4()), \
             patch("app.db.writer._upsert_article", side_effect=article_ids), \
             patch("app.db.writer._upsert_categories"), \
             patch("app.db.writer._upsert_keywords"), \
             patch("app.db.writer._write_quality_log") as mock_quality_log, \
             patch("app.db.writer._write_collect_log"):

            mock_session = MagicMock()
            mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

            from app.db.writer import write_articles
            write_articles(articles)

        assert mock_quality_log.call_count == 2
