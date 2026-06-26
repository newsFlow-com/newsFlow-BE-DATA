"""
crawlers/scrapy_spiders/zdnet_spider.py
ZDNet Korea IT/테크 전문 크롤러.

RSS 미제공 섹션의 IT·테크 기사를 보완 수집한다.

실행:
  scrapy crawl zdnet -s PYTHONPATH=/path/to/project
"""
from datetime import datetime, timezone
from urllib.parse import urljoin

import scrapy

from crawlers.scrapy_spiders.items import NewsArticleItem

_SOURCE_NAME = "ZDNet Korea"
_SOURCE_DOMAIN = "zdnet.co.kr"

_SECTION_URLS = [
    "https://zdnet.co.kr/news/?lstcode=0000",   # 전체
    "https://zdnet.co.kr/news/?lstcode=0008",   # AI
    "https://zdnet.co.kr/news/?lstcode=0020",   # 반도체
]


class ZdnetSpider(scrapy.Spider):
    name = "zdnet"
    allowed_domains = ["zdnet.co.kr"]
    start_urls = _SECTION_URLS

    custom_settings = {
        "DOWNLOAD_DELAY": 2,
    }

    def parse(self, response):
        links = response.css("a.newsTitle::attr(href), dl.articleList dt a::attr(href)").getall()
        seen = set()
        for href in links:
            url = urljoin("https://zdnet.co.kr", href)
            if url not in seen:
                seen.add(url)
                yield scrapy.Request(url, callback=self.parse_article)

    def parse_article(self, response):
        title = (
            response.css("h1.artTitle::text").get()
            or response.css('meta[property="og:title"]::attr(content)').get()
            or ""
        ).strip()

        if not title:
            return

        paragraphs = response.css("div#articeBody p::text, div.article_body p::text").getall()
        content = "\n".join(p.strip() for p in paragraphs if p.strip()) or None

        summary = response.css('meta[property="og:description"]::attr(content)').get()
        thumbnail = response.css('meta[property="og:image"]::attr(content)').get()
        author = response.css("span.reporter::text, p.reporter a::text").get()

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
