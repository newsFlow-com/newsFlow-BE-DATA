"""
tests/test_source_sentiment_aggregator.py
매체×카테고리별 일별 감성 집계 — mock 기반 검증
"""
import uuid
from datetime import date
from unittest.mock import MagicMock, patch

from app.db.aggregator import aggregate_source_sentiment_stats


def _mock_session_ctx():
    mock_ctx = MagicMock()
    mock_ctx.__enter__ = MagicMock(return_value=MagicMock())
    mock_ctx.__exit__ = MagicMock(return_value=False)
    return mock_ctx


class TestAggregateSourceSentimentStats:

    def test_대상_기사_없으면_0_반환(self):
        with patch("app.db.aggregator.get_session") as mock_session:
            mock_ctx = _mock_session_ctx()
            mock_session.return_value = mock_ctx
            db = mock_ctx.__enter__.return_value
            db.execute.return_value.all.return_value = []

            result = aggregate_source_sentiment_stats(target_date=date(2026, 7, 15))

        assert result == 0

    def test_카테고리_없는_기사는_집계에서_제외(self):
        article_id = uuid.uuid4()
        source_id = uuid.uuid4()
        article_row = MagicMock(id=article_id, source_id=source_id, sentiment="positive")

        with patch("app.db.aggregator.get_session") as mock_session, \
             patch("app.db.aggregator.pg_insert"):
            mock_ctx = _mock_session_ctx()
            mock_session.return_value = mock_ctx
            db = mock_ctx.__enter__.return_value

            db.execute.side_effect = [
                MagicMock(all=MagicMock(return_value=[article_row])),
                MagicMock(all=MagicMock(return_value=[])),  # 카테고리 없음
            ]

            result = aggregate_source_sentiment_stats(target_date=date(2026, 7, 15))

        assert result == 0

    def test_매체별_감성_카운트가_정확히_집계된다(self):
        source_id = uuid.uuid4()
        category_id = uuid.uuid4()
        a1, a2, a3 = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()

        articles = [
            MagicMock(id=a1, source_id=source_id, sentiment="positive"),
            MagicMock(id=a2, source_id=source_id, sentiment="positive"),
            MagicMock(id=a3, source_id=source_id, sentiment="negative"),
        ]
        categories = [(a1, category_id), (a2, category_id), (a3, category_id)]

        with patch("app.db.aggregator.get_session") as mock_session, \
             patch("app.db.aggregator.pg_insert") as mock_pg_insert:
            mock_ctx = _mock_session_ctx()
            mock_session.return_value = mock_ctx
            db = mock_ctx.__enter__.return_value

            db.execute.side_effect = [
                MagicMock(all=MagicMock(return_value=articles)),
                MagicMock(all=MagicMock(return_value=categories)),
                MagicMock(),  # upsert
            ]
            mock_pg_insert.return_value.values.return_value.on_conflict_do_update.return_value = "STMT"

            result = aggregate_source_sentiment_stats(target_date=date(2026, 7, 15))

        assert result == 1
        values_kwargs = mock_pg_insert.return_value.values.call_args.kwargs
        assert values_kwargs["positive_count"] == 2
        assert values_kwargs["negative_count"] == 1
        assert values_kwargs["neutral_count"] == 0
        assert values_kwargs["source_id"] == source_id
        assert values_kwargs["category_id"] == category_id

    def test_서로_다른_매체는_별도로_집계된다(self):
        source_a, source_b = uuid.uuid4(), uuid.uuid4()
        category_id = uuid.uuid4()
        a1, a2 = uuid.uuid4(), uuid.uuid4()

        articles = [
            MagicMock(id=a1, source_id=source_a, sentiment="positive"),
            MagicMock(id=a2, source_id=source_b, sentiment="negative"),
        ]
        categories = [(a1, category_id), (a2, category_id)]

        with patch("app.db.aggregator.get_session") as mock_session, \
             patch("app.db.aggregator.pg_insert") as mock_pg_insert:
            mock_ctx = _mock_session_ctx()
            mock_session.return_value = mock_ctx
            db = mock_ctx.__enter__.return_value

            db.execute.side_effect = [
                MagicMock(all=MagicMock(return_value=articles)),
                MagicMock(all=MagicMock(return_value=categories)),
                MagicMock(),
                MagicMock(),
            ]
            mock_pg_insert.return_value.values.return_value.on_conflict_do_update.return_value = "STMT"

            result = aggregate_source_sentiment_stats(target_date=date(2026, 7, 15))

        assert result == 2
