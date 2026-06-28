"""당일 수집 기사에 종목 연결 독립 실행 스크립트.

Usage:
    python scripts/link_article_stocks.py --target_date 2025-06-27
"""
import argparse
import os
import sys
import logging
from datetime import date, datetime, timezone

_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _project_root)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

parser = argparse.ArgumentParser()
parser.add_argument("--target_date", required=True, help="연결 대상 날짜 (YYYY-MM-DD)")
args = parser.parse_args()

target_date = date.fromisoformat(args.target_date)
start_dt = datetime.combine(target_date, datetime.min.time()).replace(tzinfo=timezone.utc)
end_dt = datetime.combine(target_date, datetime.max.time()).replace(tzinfo=timezone.utc)

from sqlalchemy import select
from app.db.session import get_session
from app.models import Article
from crawlers.stock.stock_collector import collect_stock_masters
from crawlers.base_collector import RawArticle
from pipelines.stock_linker import build_stock_index, link_stocks
from app.db.stock_writer import write_article_stocks

masters = collect_stock_masters()
stock_index = build_stock_index(masters)

total_links = 0
with get_session() as session:
    rows = session.execute(
        select(Article.original_url, Article.title, Article.summary, Article.content)
        .where(Article.collected_at.between(start_dt, end_dt))
    ).fetchall()

for url, title, summary, content in rows:
    article: RawArticle = {
        "source_domain": "", "source_name": "", "feed_url": None,
        "original_url": url, "title": title or "", "summary": summary,
        "content": content, "thumbnail_url": None, "author": None,
        "published_at": None, "language_code": "ko", "feed_type": "rss",
    }
    links = link_stocks(article, stock_index)
    total_links += write_article_stocks(url, links)

logger.info(f"[link_article_stocks] 완료: {total_links}건 ({target_date})")
