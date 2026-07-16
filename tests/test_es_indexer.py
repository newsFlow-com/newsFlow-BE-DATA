"""
tests/test_es_indexer.py
ES 인덱서 — Elasticsearch 미연결 시 graceful fallback 검증
"""
import uuid
from unittest.mock import MagicMock, patch

from app.db.es_indexer import (
    ES_INDEX,
    _ensure_embedding_mapping,
    _to_actions,
    index_articles,
    reindex_all,
)


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


class TestToActionsEmbedding:

    def _make_article(self):
        article = MagicMock()
        article.id = uuid.uuid4()
        article.title = "삼성전자 실적 발표"
        article.summary = "영업이익 10조"
        article.ai_summary = None
        article.content = "본문 내용"
        article.article_categories = []
        article.article_keywords = []
        article.published_at = None
        article.thumbnail_url = None
        article.original_url = "https://example.com/1"
        article.status = "active"
        return article

    def test_임베딩_성공시_source에_포함된다(self):
        article = self._make_article()
        with patch("app.db.es_indexer.embed_text", return_value=[0.1, 0.2]):
            actions = list(_to_actions([article]))

        assert actions[0]["_source"]["embedding"] == [0.1, 0.2]

    def test_임베딩_실패시_embedding_키가_빠진다(self):
        article = self._make_article()
        with patch("app.db.es_indexer.embed_text", return_value=None):
            actions = list(_to_actions([article]))

        assert "embedding" not in actions[0]["_source"]


class TestEnsureEmbeddingMapping:

    def test_이미_매핑있으면_put_mapping_호출안함(self):
        client = MagicMock()
        client.indices.get_mapping.return_value = {
            ES_INDEX: {"mappings": {"properties": {"embedding": {}}}}
        }

        _ensure_embedding_mapping(client)

        client.indices.put_mapping.assert_not_called()

    def test_매핑없으면_put_mapping_호출(self):
        client = MagicMock()
        client.indices.get_mapping.return_value = {
            ES_INDEX: {"mappings": {"properties": {"title": {}}}}
        }

        _ensure_embedding_mapping(client)

        client.indices.put_mapping.assert_called_once()
