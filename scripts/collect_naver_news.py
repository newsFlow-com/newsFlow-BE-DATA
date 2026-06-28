"""네이버 뉴스 API 수집 → 전처리 → 중복제거 → 분류 → DB 적재 독립 실행 스크립트."""
import os
import sys
import logging

_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _project_root)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

from crawlers.news_api.naver_news_collector import collect_naver_news as fetch_naver
from pipelines.preprocessor import preprocess_all
from pipelines.deduplicator import deduplicate
from pipelines.classifier import classify_all
from app.db.writer import write_articles, fetch_existing_urls

raw = fetch_naver()
logger.info(f"[NaverNews] 수집: {len(raw)}건")

cleaned = preprocess_all(raw)
existing_urls = fetch_existing_urls()
deduped = deduplicate(cleaned, existing_urls=existing_urls)
classified = classify_all(deduped)

result = write_articles(classified)
logger.info(f"[NaverNews] 완료: {result}")
