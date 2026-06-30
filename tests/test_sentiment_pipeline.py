"""
tests/test_sentiment_pipeline.py
감성 분석 파이프라인 — BE-AI HTTP 호출 mock 검증
"""
import uuid
from unittest.mock import MagicMock, patch

from pipelines.sentiment import run_sentiment_analysis, _call_ai_sentiment


class TestCallAiSentiment:

    def test_정상_응답_반환(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"sentiment": "positive", "score": 0.9}
        mock_resp.raise_for_status.return_value = None

        with patch("pipelines.sentiment.requests.post", return_value=mock_resp) as mock_post:
            result = _call_ai_sentiment("some-uuid")

        assert result["sentiment"] == "positive"
        assert result["score"] == 0.9

    def test_HTTP_오류시_None_반환(self):
        with patch("pipelines.sentiment.requests.post", side_effect=Exception("연결 오류")):
            result = _call_ai_sentiment("some-uuid")

        assert result is None

    def test_타임아웃시_None_반환(self):
        import requests as req
        with patch("pipelines.sentiment.requests.post",
                   side_effect=req.exceptions.Timeout("타임아웃")):
            result = _call_ai_sentiment("some-uuid")

        assert result is None


class TestRunSentimentAnalysis:

    def test_빈_기사_목록_0_반환(self):
        with patch("pipelines.sentiment.get_session") as mock_session:
            mock_ctx = MagicMock()
            mock_ctx.__enter__ = MagicMock(return_value=MagicMock())
            mock_ctx.__exit__ = MagicMock(return_value=False)
            mock_session.return_value = mock_ctx

            db = mock_ctx.__enter__.return_value
            db.execute.return_value.all.return_value = []

            result = run_sentiment_analysis(limit=10)

        assert result == 0

    def test_API_실패시_업데이트_건너뜀(self):
        article_id = uuid.uuid4()

        with patch("pipelines.sentiment.get_session") as mock_session, \
             patch("pipelines.sentiment._call_ai_sentiment", return_value=None):

            mock_ctx = MagicMock()
            mock_ctx.__enter__ = MagicMock(return_value=MagicMock())
            mock_ctx.__exit__ = MagicMock(return_value=False)
            mock_session.return_value = mock_ctx

            db = mock_ctx.__enter__.return_value
            row = MagicMock()
            row.id = article_id
            db.execute.return_value.all.return_value = [row]

            result = run_sentiment_analysis(limit=10)

        assert result == 0
