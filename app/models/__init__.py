"""
app/models/__init__.py
모든 모델을 단일 진입점에서 임포트.
Alembic autogenerate 와 SQLAlchemy 가 테이블을 인식하려면
Base 와 함께 모든 모델이 이 파일을 통해 로드되어야 한다.
"""

from .base import Base, TimestampMixin, UUIDMixin  # noqa: F401

# ── 사용자 & 인증
from .user import RefreshToken, SocialAccount, User  # noqa: F401

# ── 뉴스
from .news import Article, Source  # noqa: F401

# ── 분류
from .category import ArticleCategory, Category  # noqa: F401

# ── 키워드 & 트렌드
from .keyword import ArticleKeyword, Keyword, TrendingKeyword  # noqa: F401

# ── 이슈 클러스터링
from .issue import Issue, IssueKeyword  # noqa: F401

# ── 주식
from .stock import ArticleStock, Stock, StockPrice  # noqa: F401

# ── 통계
from .stats import (  # noqa: F401
    ApiRequestLog,
    DailyArticleStat,
    DailyUserStat,
    PipelineStat,
    SourceSentimentStat,
)

# ── 사용자 활동
from .activity import ArticleView, Bookmark, ShareLog, UserCategory  # noqa: F401

# ── 관리자
from .admin import (  # noqa: F401
    AdminLog,
    ArticleReport,
    Banner,
    CollectLog,
    ContentQualityLog,
    Notice,
)

# ── 알림
from .notification import Subscription, UserNotification  # noqa: F401

# ── B2B
from .b2b import ApiKey  # noqa: F401

__all__ = [
    # base
    "Base", "TimestampMixin", "UUIDMixin",
    # user
    "User", "SocialAccount", "RefreshToken",
    # news
    "Source", "Article",
    # category
    "Category", "ArticleCategory",
    # keyword
    "Keyword", "ArticleKeyword", "TrendingKeyword",
    # issue
    "Issue", "IssueKeyword",
    # stock
    "Stock", "ArticleStock", "StockPrice",
    # stats
    "DailyArticleStat", "DailyUserStat", "PipelineStat", "ApiRequestLog",
    "SourceSentimentStat",
    # activity
    "Bookmark", "UserCategory", "ShareLog", "ArticleView",
    # admin
    "AdminLog", "CollectLog", "ContentQualityLog",
    "ArticleReport", "Notice", "Banner",
    # notification
    "Subscription", "UserNotification",
    # b2b
    "ApiKey",
]