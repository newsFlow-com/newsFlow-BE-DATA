import feedparser
from datetime import datetime


RSS_FEEDS = [
    # 추후 실제 RSS 주소 추가
    # "https://feeds.yna.co.kr/yna/all.rss",   # 연합뉴스
    # "https://rss.etnews.com/",               # 전자신문
]


def collect_rss(feed_url: str) -> list[dict]:
    """RSS 피드에서 기사 수집"""
    feed = feedparser.parse(feed_url)
    articles = []

    for entry in feed.entries:
        articles.append({
            "title": entry.get("title", ""),
            "content": entry.get("summary", ""),
            "source_url": entry.get("link", ""),
            "publisher": feed.feed.get("title", ""),
            "published_at": datetime(*entry.published_parsed[:6]) if hasattr(entry, "published_parsed") else datetime.now(),
        })

    return articles


def collect_all_rss() -> list[dict]:
    """등록된 모든 RSS 피드 수집"""
    all_articles = []
    for url in RSS_FEEDS:
        try:
            articles = collect_rss(url)
            all_articles.extend(articles)
        except Exception as e:
            print(f"RSS 수집 실패: {url} - {e}")
    return all_articles