"""
Scrapy 공통 설정.
언론사별 스파이더는 이 설정을 공유한다.
"""

BOT_NAME = "newsflow"
SPIDER_MODULES = ["crawlers.scrapy_spiders"]

# 크롤링 예절: 요청 간격 1~3초, 동시 요청 4개로 서버 부하 최소화
DOWNLOAD_DELAY = 1
RANDOMIZE_DOWNLOAD_DELAY = True
CONCURRENT_REQUESTS = 4
CONCURRENT_REQUESTS_PER_DOMAIN = 2

# robots.txt 준수
ROBOTSTXT_OBEY = True

# 기본 User-Agent
USER_AGENT = (
    "Mozilla/5.0 (compatible; NewsFlowBot/1.0; +https://newsflow.com/bot)"
)

# 불필요한 미들웨어 비활성화
COOKIES_ENABLED = False
TELNETCONSOLE_ENABLED = False

# 로그 레벨
LOG_LEVEL = "INFO"

# Item pipeline — Scrapy Item을 RawArticle로 변환해 DB에 바로 적재
ITEM_PIPELINES = {
    "crawlers.scrapy_spiders.pipelines.NewsFlowPipeline": 300,
}

REQUEST_FINGERPRINTER_IMPLEMENTATION = "2.7"
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"
