"""
Scrapy Item 정의 — RawArticle 구조와 1:1 대응.
"""
import scrapy


class NewsArticleItem(scrapy.Item):
    source_domain = scrapy.Field()
    source_name = scrapy.Field()
    feed_url = scrapy.Field()
    original_url = scrapy.Field()
    title = scrapy.Field()
    summary = scrapy.Field()
    content = scrapy.Field()
    thumbnail_url = scrapy.Field()
    author = scrapy.Field()
    published_at = scrapy.Field()
    language_code = scrapy.Field()
    feed_type = scrapy.Field()
