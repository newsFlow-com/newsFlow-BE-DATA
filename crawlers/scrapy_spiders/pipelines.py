"""
Scrapy Item Pipeline — NewsArticleItem을 RawArticle로 변환해 전처리·적재 파이프라인에 투입.
"""
import logging

from crawlers.base_collector import RawArticle
from pipelines.preprocessor import preprocess
from pipelines.deduplicator import deduplicate
from pipelines.classifier import classify
from app.db.writer import write_articles

logger = logging.getLogger(__name__)


class NewsFlowPipeline:
    """수집된 Item을 전처리 → 분류 → DB 적재."""

    def __init__(self):
        self._buffer: list[RawArticle] = []
        self._flush_size = 50  # 50건마다 일괄 적재

    def process_item(self, item, spider):
        raw: RawArticle = {
            "source_domain": item.get("source_domain", ""),
            "source_name": item.get("source_name", ""),
            "feed_url": item.get("feed_url"),
            "original_url": item.get("original_url", ""),
            "title": item.get("title", ""),
            "summary": item.get("summary"),
            "content": item.get("content"),
            "thumbnail_url": item.get("thumbnail_url"),
            "author": item.get("author"),
            "published_at": item.get("published_at"),
            "language_code": item.get("language_code", "ko"),
            "feed_type": "crawl",
        }
        cleaned = preprocess(raw)
        if cleaned:
            self._buffer.append(cleaned)

        if len(self._buffer) >= self._flush_size:
            self._flush()

        return item

    def close_spider(self, spider):
        if self._buffer:
            self._flush()

    def _flush(self):
        deduped = deduplicate(self._buffer)
        classified = [classify(a) for a in deduped]
        result = write_articles(classified)
        logger.info(f"[Pipeline] 플러시 완료: {result}")
        self._buffer.clear()
