"""
crawlers/scrapy_spiders/yonhap_spider.py
연합뉴스 크롤러 (RSS 보완 — 속보 및 일부 섹션 전용).

연합뉴스는 RSS가 있지만 일부 섹션(속보, 지역)은 RSS 미제공.
이 스파이더는 RSS에서 누락되는 섹션을 보완한다.

실행:
  scrapy crawl yonhap -s PYTHONPATH=/path/to/project
"""
from datetime import datetime, timezone
from urllib.parse import urljoin

import scrapy

from crawlers.scrapy_spiders.items import NewsArticleItem

_SOURCE_NAME = "연합뉴스"
_SOURCE_DOMAIN = "yna.co.kr"

_SECTION_URLS = [
    "https://www.yna.co.kr/bulletin/all",   # 속보
    "https://www.yna.co.kr/economy/all",
    "https://www.yna.co.kr/politics/all",
]


class YonhapSpider(scrapy.Spider):
    name = "yonhap"
    allowed_domains = ["yna.co.kr"]
    start_urls = _SECTION_URLS

    custom_settings = {
        "DOWNLOAD_DELAY": 1,
    }

    def parse(self, response):
        links = response.css("a.tit-wrap::attr(href), ul.list li a::attr(href)").getall()
        seen = set()
        for href in links:
            url = urljoin("https://www.yna.co.kr", href)
            if "/view/" in url and url not in seen:
                seen.add(url)
                yield scrapy.Request(url, callback=self.parse_article)

    def parse_article(self, response):
        title = (
            response.css("h1.tit::text").get()
            or response.css('meta[property="og:title"]::attr(content)').get()
            or ""
        ).strip()

        if not title:
            return

        paragraphs = response.css("article.story-news p::text").getall()
        content = "\n".join(p.strip() for p in paragraphs if p.strip()) or None

        summary = response.css('meta[property="og:description"]::attr(content)').get()
        thumbnail = response.css('meta[property="og:image"]::attr(content)').get()
        author = response.css("span.writer::text").get()

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
