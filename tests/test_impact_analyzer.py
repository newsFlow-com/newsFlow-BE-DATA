"""
tests/test_impact_analyzer.py
뉴스-주가 영향도 분석 — mock 기반 검증
"""
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

from pipelines.impact_analyzer import analyze_link_impact, run_impact_analysis


def _make_link():
    link = MagicMock()
    link.id = uuid.uuid4()
    link.stock_id = uuid.uuid4()
    link.price_change_publish_day = None
    link.price_change_3d = None
    link.impact_analyzed_at = None
    return link


def _make_price(price_date, change_rate=None, close_price=None):
    p = MagicMock()
    p.price_date = price_date
    p.change_rate = Decimal(str(change_rate)) if change_rate is not None else None
    p.close_price = Decimal(str(close_price)) if close_price is not None else None
    return p


def _mock_session_ctx():
    mock_ctx = MagicMock()
    mock_ctx.__enter__ = MagicMock(return_value=MagicMock())
    mock_ctx.__exit__ = MagicMock(return_value=False)
    return mock_ctx


class TestAnalyzeLinkImpact:

    def test_기준_주가_없으면_False(self):
        link = _make_link()
        db = MagicMock()

        with patch("pipelines.impact_analyzer._find_baseline_price", return_value=None):
            result = analyze_link_impact(db, link, date(2026, 7, 1))

        assert result is False
        assert link.price_change_publish_day is None
        assert link.impact_analyzed_at is None

    def test_3일후_데이터_없으면_발행일_등락률만_채우고_False(self):
        link = _make_link()
        db = MagicMock()
        baseline = _make_price(date(2026, 7, 1), change_rate=1.5, close_price=100)

        with patch("pipelines.impact_analyzer._find_baseline_price", return_value=baseline), \
             patch("pipelines.impact_analyzer._find_price_after", return_value=None):
            result = analyze_link_impact(db, link, date(2026, 7, 1))

        assert result is False
        assert link.price_change_publish_day == 1.5
        assert link.price_change_3d is None
        assert link.impact_analyzed_at is None

    def test_3일후_데이터_있으면_누적_변동률_계산_후_True(self):
        link = _make_link()
        db = MagicMock()
        baseline = _make_price(date(2026, 7, 1), change_rate=1.5, close_price=100)
        after = _make_price(date(2026, 7, 6), close_price=110)

        with patch("pipelines.impact_analyzer._find_baseline_price", return_value=baseline), \
             patch("pipelines.impact_analyzer._find_price_after", return_value=after):
            result = analyze_link_impact(db, link, date(2026, 7, 1))

        assert result is True
        assert link.price_change_publish_day == 1.5
        assert link.price_change_3d == 10.0
        assert link.impact_analyzed_at is not None

    def test_종가가_0이면_False(self):
        link = _make_link()
        db = MagicMock()
        baseline = _make_price(date(2026, 7, 1), change_rate=0.0, close_price=0)
        after = _make_price(date(2026, 7, 6), close_price=110)

        with patch("pipelines.impact_analyzer._find_baseline_price", return_value=baseline), \
             patch("pipelines.impact_analyzer._find_price_after", return_value=after):
            result = analyze_link_impact(db, link, date(2026, 7, 1))

        assert result is False


class TestRunImpactAnalysis:

    def test_대상_없으면_0_반환(self):
        with patch("pipelines.impact_analyzer.get_session") as mock_session:
            mock_ctx = _mock_session_ctx()
            mock_session.return_value = mock_ctx
            db = mock_ctx.__enter__.return_value
            db.execute.return_value.all.return_value = []

            result = run_impact_analysis(limit=10)

        assert result == 0

    def test_완료된_건수만_카운트한다(self):
        link1, link2 = _make_link(), _make_link()
        published_at = datetime(2026, 7, 1, tzinfo=timezone.utc)

        with patch("pipelines.impact_analyzer.get_session") as mock_session, \
             patch("pipelines.impact_analyzer.analyze_link_impact",
                   side_effect=[True, False]) as mock_analyze:
            mock_ctx = _mock_session_ctx()
            mock_session.return_value = mock_ctx
            db = mock_ctx.__enter__.return_value
            db.execute.return_value.all.return_value = [
                (link1, published_at), (link2, published_at)
            ]

            result = run_impact_analysis(limit=10)

        assert result == 1
        assert mock_analyze.call_count == 2

    def test_개별_실패해도_나머지_계속_진행(self):
        link1, link2 = _make_link(), _make_link()
        published_at = datetime(2026, 7, 1, tzinfo=timezone.utc)

        with patch("pipelines.impact_analyzer.get_session") as mock_session, \
             patch("pipelines.impact_analyzer.analyze_link_impact",
                   side_effect=[Exception("실패"), True]) as mock_analyze:
            mock_ctx = _mock_session_ctx()
            mock_session.return_value = mock_ctx
            db = mock_ctx.__enter__.return_value
            db.execute.return_value.all.return_value = [
                (link1, published_at), (link2, published_at)
            ]

            result = run_impact_analysis(limit=10)

        assert result == 1
        assert mock_analyze.call_count == 2
