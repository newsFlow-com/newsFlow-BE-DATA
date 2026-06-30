"""
tests/test_es_indexer.py
ES 인덱서 — Elasticsearch 미연결 시 graceful fallback 검증
"""
import uuid
from unittest.mock import MagicMock, patch

from app.db.es_indexer import index_articles, reindex_all


class TestEsIndexerFallback:
    """Elasticsearch 연결 불가 시 0 반환 (파이프라인 중단 없음)."""

    @patch("app.db.es_indexer._get_client", return_value=None)
    def test_index_articles_빈_목록_반환_ES없을때(self, mock_client):
        result = index_articles([uuid.uuid4()])
        assert result == 0

    @patch("app.db.es_indexer._get_client", return_value=None)
    def test_reindex_all_빈_목록_반환_ES없을때(self, mock_client):
        result = reindex_all(limit=10)
        assert result == 0

    @patch("app.db.es_indexer._get_client", return_value=None)
    def test_index_articles_빈_리스트_입력(self, mock_client):
        result = index_articles([])
        assert result == 0
        mock_client.assert_not_called()

    def test_get_client_연결실패시_None반환(self):
        with patch("app.db.es_indexer.Elasticsearch") as mock_es:
            mock_es.return_value.ping.return_value = False
            from app.db.es_indexer import _get_client
            client = _get_client()
            assert client is None

    def test_get_client_예외시_None반환(self):
        with patch("app.db.es_indexer.Elasticsearch") as mock_es:
            mock_es.side_effect = Exception("연결 거부")
            from app.db.es_indexer import _get_client
            client = _get_client()
            assert client is None
