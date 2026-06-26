"""
crawlers/scrapy_spiders/joongang_spider.py
중앙일보 뉴스 크롤러.

실행:
  scrapy crawl joongang -s PYTHONPATH=/path/to/project
"""
from datetime import datetime, timezone
from urllib.parse import urljoin

import scrapy

from crawlers.scrapy_spiders.items import NewsArticleItem

_SOURCE_NAME = "중앙일보"
_SOURCE_DOMAIN = "joongang.co.kr"

_SECTION_URLS = [
    "https://www.joongang.co.kr/politics",
    "https://www.joongang.co.kr/economy",
    "https://www.joongang.co.kr/society",
    "https://www.joongang.co.kr/world",
    "https://www.joongang.co.kr/it",
]


class JoongangSpider(scrapy.Spider):
    name = "joongang"
    allowed_domains = ["joongang.co.kr"]
    start_urls = _SECTION_URLS

    custom_settings = {
        "DOWNLOAD_DELAY": 2,
    }

    def parse(self, response):
        links = response.css("a.card-body__title::attr(href), a[href*='/article/']::attr(href)").getall()
        seen = set()
        for href in links:
            url = urljoin(response.url, href)
            if url not in seen:
                seen.add(url)
                yield scrapy.Request(url, callback=self.parse_article)

    def parse_article(self, response):
        title = (
            response.css("h1.article-title::text").get()
            or response.css('meta[property="og:title"]::attr(content)').get()
            or ""
        ).strip()

        if not title:
            return

        paragraphs = response.css("div#article_body p::text").getall()
        content = "\n".join(p.strip() for p in paragraphs if p.strip()) or None

        summary = response.css('meta[property="og:description"]::attr(content)').get()
        thumbnail = response.css('meta[property="og:image"]::attr(content)').get()
        author = response.css("span.byline__name::text").get()

        pub_raw = response.css('meta[property="article:published_time"]::attr(content)').get()
        published_at = None
        if pub_raw:
            try:
                published_at = datetime.fromisoformat(pub_raw).astimezone(timezone.utc)
            except Exception:
                pass

        yield NewsArticleItem(
            source_domain=_SOURCE_DOMAIN,
            source_name=_SOURCE_NAME,
            feed_url=response.url,
            original_url=response.url,
            title=title,
            summary=summary,
            content=content,
            thumbnail_url=thumbnail,
            author=author,
            published_at=published_at,
            language_code="ko",
            feed_type="crawl",
        )
