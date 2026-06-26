"""
주식-기사 연결 파이프라인 단위 테스트.
"""
from datetime import datetime, timezone

from pipelines.stock_linker import link_stocks, build_stock_index
from crawlers.base_collector import RawArticle


def _make_article(title: str, summary: str = "") -> RawArticle:
    return {
        "source_domain": "example.com",
        "source_name": "테스트",
        "feed_url": None,
        "original_url": "https://example.com/1",
        "title": title,
        "summary": summary,
        "content": None,
        "thumbnail_url": None,
        "author": None,
        "published_at": datetime(2025, 5, 18, tzinfo=timezone.utc),
        "language_code": "ko",
        "feed_type": "rss",
    }


class MockMaster:
    def __init__(self, name, ticker):
        self.name = name
        self.ticker = ticker


class TestBuildStockIndex:
    def test_인덱스_구조(self):
        masters = [
            MockMaster("삼성전자", "005930"),
            MockMaster("SK하이닉스", "000660"),
        ]
        index = build_stock_index(masters)
        assert index["삼성전자"] == "005930"
        assert index["005930"] == "005930"
        assert index["SK하이닉스"] == "000660"


class TestLinkStocks:
    def setup_method(self):
        self.index = {
            "삼성전자": "005930",
            "005930": "005930",
            "카카오": "035720",
            "네이버": "035420",
        }

    def test_종목명_감지(self):
        article = _make_article("삼성전자 1분기 실적 발표")
        links = link_stocks(article, self.index)
        tickers = [l.ticker for l in links]
        assert "005930" in tickers

    def test_여러_종목_감지(self):
        article = _make_article("삼성전자와 카카오 협업 발표")
        links = link_stocks(article, self.index)
        assert len(links) >= 2

    def test_관련_없는_기사(self):
        article = _make_article("오늘 날씨 맑음")
        links = link_stocks(article, self.index)
        assert len(links) == 0

    def test_최대_5개_제한(self):
        big_index = {f"종목{i}": f"00000{i}" for i in range(20)}
        title = " ".join(big_index.keys())
        article = _make_article(title)
        links = link_stocks(article, big_index)
        assert len(links) <= 5

    def test_mention_score_범위(self):
        article = _make_article("삼성전자 삼성전자 삼성전자 실적")
        links = link_stocks(article, self.index)
        for l in links:
            assert 0.0 <= l.mention_score <= 1.0
