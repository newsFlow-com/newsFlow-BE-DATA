"""
crawlers/scrapy_spiders/chosun_spider.py
조선일보 뉴스 목록 크롤러.

RSS가 없거나 제한적인 언론사를 대상으로 Scrapy로 직접 크롤링한다.
이 스파이더를 참고해 다른 언론사 스파이더를 추가할 수 있다.

실행:
  scrapy crawl chosun -s PYTHONPATH=/path/to/project
"""
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import scrapy

from crawlers.scrapy_spiders.items import NewsArticleItem

_SOURCE_NAME = "조선일보"
_SOURCE_DOMAIN = "chosun.com"
_START_URL = "https://www.chosun.com/"

# 섹션별 목록 페이지 URL
_SECTION_URLS = [
    "https://www.chosun.com/politics/",
    "https://www.chosun.com/economy/",
    "https://www.chosun.com/national/",
    "https://www.chosun.com/international/",
    "https://www.chosun.com/it-science/",
]


class ChosunSpider(scrapy.Spider):
    name = "chosun"
    allowed_domains = ["chosun.com"]
    start_urls = _SECTION_URLS

    custom_settings = {
        "DOWNLOAD_DELAY": 2,
    }

    def parse(self, response):
        """섹션 목록 페이지에서 기사 링크 추출."""
        # 조선일보 기사 URL 패턴: /section/yyyy/mm/dd/...
        article_links = response.css("a[href*='/']::attr(href)").getall()
        article_pattern = re.compile(r"/\w+/\d{4}/\d{2}/\d{2}/")

        seen = set()
        for href in article_links:
            url = urljoin(response.url, href)
            if article_pattern.search(href) and url not in seen:
                seen.add(url)
                yield scrapy.Request(url, callback=self.parse_article)

    def parse_article(self, response):
        """기사 상세 페이지에서 본문 및 메타데이터 추출."""
        title = (
            response.css("h1.article-header__headline::text").get()
            or response.css("h1::text").get()
            or ""
        ).strip()

        if not title:
            return

        # 본문 추출: 조선일보 기사 본문 선택자
        paragraphs = response.css("div.article-body p::text").getall()
        content = "\n".join(p.strip() for p in paragraphs if p.strip()) or None

        # 요약 (og:description)
        summary = response.css('meta[property="og:description"]::attr(content)').get()

        # 썸네일
        thumbnail = response.css('meta[property="og:image"]::attr(content)').get()

        # 저자
        author = response.css("span.article-header__author::text").get()

        # 발행 시각
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
