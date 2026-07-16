"""
tests/test_embedder.py
문장 임베딩 생성 — mock 기반 검증

sentence-transformers는 무거운 의존성이라 실제 모델을 로드하지 않고
_get_model()을 모킹하거나 sys.modules에 가짜 모듈을 주입해 검증한다.
"""
import sys
from unittest.mock import MagicMock, patch

import pipelines.embedder as embedder_module
from pipelines.embedder import embed_text


class TestEmbedText:

    def setup_method(self):
        embedder_module._model = None  # 모듈 싱글톤 초기화

    def test_빈_문자열이면_모델_로드없이_None(self):
        with patch("pipelines.embedder._get_model") as mock_get_model:
            result = embed_text("")

        assert result is None
        mock_get_model.assert_not_called()

    def test_None이면_None_반환(self):
        assert embed_text(None) is None

    def test_공백만_있으면_None_반환(self):
        assert embed_text("   ") is None

    def test_정상_텍스트면_벡터_리스트_반환(self):
        mock_model = MagicMock()
        mock_vector = MagicMock()
        mock_vector.tolist.return_value = [0.1, 0.2, 0.3]
        mock_model.encode.return_value = mock_vector

        with patch("pipelines.embedder._get_model", return_value=mock_model):
            result = embed_text("삼성전자 실적 발표")

        assert result == [0.1, 0.2, 0.3]
        mock_model.encode.assert_called_once_with("삼성전자 실적 발표", normalize_embeddings=True)

    def test_예외_발생시_None_반환(self):
        with patch("pipelines.embedder._get_model", side_effect=Exception("모델 로드 실패")):
            result = embed_text("텍스트")

        assert result is None

    def test_모델은_한번만_로드된다(self):
        fake_module = MagicMock()
        mock_model_instance = MagicMock()
        mock_model_instance.encode.return_value.tolist.return_value = [0.1]
        fake_module.SentenceTransformer.return_value = mock_model_instance

        with patch.dict(sys.modules, {"sentence_transformers": fake_module}):
            embed_text("첫번째")
            embed_text("두번째")

        assert fake_module.SentenceTransformer.call_count == 1
