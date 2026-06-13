import json
from typing import Any

import redis.asyncio as redis

from src.config import get_settings

_settings = get_settings()
_pool: redis.Redis | None = None


def get_redis() -> redis.Redis:
    global _pool
    if _pool is None:
        if _settings.dev_mode:
            import fakeredis.aioredis as fakeredis

            _pool = fakeredis.FakeRedis(decode_responses=True)
        else:
            _pool = redis.from_url(_settings.redis_url, decode_responses=True)
    return _pool


async def cache_get(key: str) -> Any | None:
    r = get_redis()
    raw = await r.get(key)
    if raw is None:
        return None
    return json.loads(raw)


async def cache_set(key: str, value: Any, ttl_seconds: int) -> None:
    r = get_redis()
    await r.set(key, json.dumps(value, default=str), ex=ttl_seconds)


async def cache_delete_pattern(pattern: str) -> int:
    r = get_redis()
    keys = [k async for k in r.scan_iter(match=pattern)]
    if keys:
        return await r.delete(*keys)
    return 0
