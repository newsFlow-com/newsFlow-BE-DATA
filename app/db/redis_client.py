"""
app/db/redis_client.py
Redis 연결 팩토리. REDIS_URL 환경변수 기반 단일 클라이언트를 반환한다.
"""
import os
import redis

_REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")


def get_redis() -> redis.Redis:
    return redis.from_url(_REDIS_URL, decode_responses=True)
