"""
tests/test_issue_clusterer.py
이슈 클러스터링 파이프라인 — Jaccard 유사도 계산 및 분기 로직 mock 검증
"""
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from pipelines.issue_clusterer import (
    MIN_SHARED_KEYWORDS,
    SIMILARITY_THRESHOLD,
    _jaccard,
    cluster_article,
    run_issue_clustering,
)


class TestJaccard:

    def test_공집합이면_0(self):
        assert _jaccard(set(), {"a", "b"}) == 0.0
        assert _jaccard({"a", "b"}, set()) == 0.0

    def test_겹치지_않으면_0(self):
        assert _jaccard({"a", "b"}, {"c", "d"}) == 0.0

    def test_완전히_같으면_1(self):
        assert _jaccard({"a", "b"}, {"a", "b"}) == 1.0

    def test_부분_겹침_비율_계산(self):
        # 교집합 1개 / 합집합 3개
        assert _jaccard({"a", "b"}, {"b", "c"}) == pytest.approx(1 / 3)


class TestClusterArticle:

    def _make_article(self, published_at=None):
        article = MagicMock()
        article.id = uuid.uuid4()
        article.published_at = published_at or datetime(2026, 7, 16, tzinfo=timezone.utc)
        return article

    def test_키워드_부족하면_새_이슈_생성(self):
        article = self._make_article()
        db = MagicMock()

        with patch("pipelines.issue_clusterer._load_article_keywords",
                   return_value={uuid.uuid4(): 0.5}), \
             patch("pipelines.issue_clusterer._load_top_category", return_value=uuid.uuid4()), \
             patch("pipelines.issue_clusterer._find_candidate_issue_ids") as mock_find, \
             patch("pipelines.issue_clusterer._create_issue") as mock_create:

            cluster_article(db, article)

        mock_find.assert_not_called()
        mock_create.assert_called_once()

    def test_카테고리_없으면_새_이슈_생성(self):
        article = self._make_article()
        db = MagicMock()
        keyword_ids = {uuid.uuid4(): 0.5, uuid.uuid4(): 0.4}

        with patch("pipelines.issue_clusterer._load_article_keywords", return_value=keyword_ids), \
             patch("pipelines.issue_clusterer._load_top_category", return_value=None), \
             patch("pipelines.issue_clusterer._find_candidate_issue_ids") as mock_find, \
             patch("pipelines.issue_clusterer._create_issue") as mock_create:

            cluster_article(db, article)

        mock_find.assert_not_called()
        mock_create.assert_called_once()

    def test_임계값_이상_후보있으면_병합(self):
        article = self._make_article()
        db = MagicMock()
        keyword_scores = {uuid.uuid4(): 0.5, uuid.uuid4(): 0.4}
        issue_id = uuid.uuid4()
        mock_issue = MagicMock()
        db.get.return_value = mock_issue

        with patch("pipelines.issue_clusterer._load_article_keywords", return_value=keyword_scores), \
             patch("pipelines.issue_clusterer._load_top_category", return_value=uuid.uuid4()), \
             patch("pipelines.issue_clusterer._find_candidate_issue_ids", return_value=[issue_id]), \
             patch("pipelines.issue_clusterer._pick_best_issue_id",
                   return_value=(issue_id, SIMILARITY_THRESHOLD)), \
             patch("pipelines.issue_clusterer._merge_into_issue") as mock_merge, \
             patch("pipelines.issue_clusterer._create_issue") as mock_create:

            cluster_article(db, article)

        mock_merge.assert_called_once_with(db, mock_issue, article, keyword_scores)
        mock_create.assert_not_called()

    def test_임계값_미달이면_새_이슈_생성(self):
        article = self._make_article()
        db = MagicMock()
        keyword_scores = {uuid.uuid4(): 0.5, uuid.uuid4(): 0.4}
        issue_id = uuid.uuid4()

        with patch("pipelines.issue_clusterer._load_article_keywords", return_value=keyword_scores), \
             patch("pipelines.issue_clusterer._load_top_category", return_value=uuid.uuid4()), \
             patch("pipelines.issue_clusterer._find_candidate_issue_ids", return_value=[issue_id]), \
             patch("pipelines.issue_clusterer._pick_best_issue_id",
                   return_value=(issue_id, SIMILARITY_THRESHOLD - 0.01)), \
             patch("pipelines.issue_clusterer._merge_into_issue") as mock_merge, \
             patch("pipelines.issue_clusterer._create_issue") as mock_create:

            cluster_article(db, article)

        mock_merge.assert_not_called()
        mock_create.assert_called_once()

    def test_후보_없으면_새_이슈_생성(self):
        article = self._make_article()
        db = MagicMock()
        keyword_scores = {uuid.uuid4(): 0.5, uuid.uuid4(): 0.4}

        with patch("pipelines.issue_clusterer._load_article_keywords", return_value=keyword_scores), \
             patch("pipelines.issue_clusterer._load_top_category", return_value=uuid.uuid4()), \
             patch("pipelines.issue_clusterer._find_candidate_issue_ids", return_value=[]), \
             patch("pipelines.issue_clusterer._pick_best_issue_id", return_value=(None, 0.0)), \
             patch("pipelines.issue_clusterer._create_issue") as mock_create:

            cluster_article(db, article)

        mock_create.assert_called_once()


class TestRunIssueClustering:

    def test_빈_기사_목록_0_반환(self):
        with patch("pipelines.issue_clusterer.get_session") as mock_session:
            mock_ctx = MagicMock()
            mock_ctx.__enter__ = MagicMock(return_value=MagicMock())
            mock_ctx.__exit__ = MagicMock(return_value=False)
            mock_session.return_value = mock_ctx

            db = mock_ctx.__enter__.return_value
            db.execute.return_value.scalars.return_value.all.return_value = []

            result = run_issue_clustering(limit=10)

        assert result == 0

    def test_기사있으면_클러스터링_수행건수_반환(self):
        articles = [MagicMock(), MagicMock()]

        with patch("pipelines.issue_clusterer.get_session") as mock_session, \
             patch("pipelines.issue_clusterer.cluster_article") as mock_cluster:
            mock_ctx = MagicMock()
            mock_ctx.__enter__ = MagicMock(return_value=MagicMock())
            mock_ctx.__exit__ = MagicMock(return_value=False)
            mock_session.return_value = mock_ctx

            db = mock_ctx.__enter__.return_value
            db.execute.return_value.scalars.return_value.all.return_value = articles

            result = run_issue_clustering(limit=10)

        assert result == 2
        assert mock_cluster.call_count == 2

    def test_개별_기사_클러스터링_실패해도_나머지_계속_진행(self):
        articles = [MagicMock(), MagicMock()]

        with patch("pipelines.issue_clusterer.get_session") as mock_session, \
             patch("pipelines.issue_clusterer.cluster_article",
                   side_effect=[Exception("실패"), None]) as mock_cluster:
            mock_ctx = MagicMock()
            mock_ctx.__enter__ = MagicMock(return_value=MagicMock())
            mock_ctx.__exit__ = MagicMock(return_value=False)
            mock_session.return_value = mock_ctx

            db = mock_ctx.__enter__.return_value
            db.execute.return_value.scalars.return_value.all.return_value = articles

            result = run_issue_clustering(limit=10)

        assert result == 1
        assert mock_cluster.call_count == 2
