"""
pipelines/embedder.py — 기사 텍스트 임베딩 생성 (RAG 벡터 검색용)

Elasticsearch dense_vector 필드에 저장할 문장 임베딩을 계산한다.
다국어 지원 경량 모델을 사용해 한국어 기사도 별도 전처리 없이 임베딩 가능하다.
모델 로드 비용이 크므로 모듈 레벨 싱글톤으로 유지한다 (classifier.py의 _kiwi 패턴과 동일).
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)

EMBEDDING_MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
EMBEDDING_DIMS = 384

_model = None


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    return _model


def embed_text(text: Optional[str]) -> Optional[list[float]]:
    """
    텍스트를 임베딩 벡터로 변환한다.
    빈 텍스트이거나 모델 로드/추론에 실패하면 None을 반환한다
    (ES 인덱싱 파이프라인은 embedding 없이도 계속 진행되어야 한다).
    """
    if not text or not text.strip():
        return None
    try:
        model = _get_model()
        vector = model.encode(text, normalize_embeddings=True)
        return vector.tolist()
    except Exception as e:
        logger.warning("임베딩 생성 실패: %s", e)
        return None
