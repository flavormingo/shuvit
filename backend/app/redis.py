import json
import logging
from functools import wraps
from typing import Any

import redis.asyncio as aioredis

from app.config import settings

logger = logging.getLogger(__name__)

_pool: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis | None:
    global _pool
    if not settings.REDIS_URL:
        return None
    if _pool is None:
        try:
            _pool = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
            await _pool.ping()
        except Exception:
            _pool = None
    return _pool


def cache(prefix: str, ttl: int = 300):
    """Cache decorator for async functions. Returns cached JSON if available."""

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            r = await get_redis()
            if r is None:
                return await func(*args, **kwargs)

            cache_key = f"{prefix}:{json.dumps(kwargs, sort_keys=True, default=str)}"
            try:
                cached = await r.get(cache_key)
                if cached:
                    return json.loads(cached)
            except Exception:
                logger.warning("Redis cache read failed for %s", cache_key, exc_info=True)

            result = await func(*args, **kwargs)

            try:
                await r.setex(cache_key, ttl, json.dumps(result, default=str))
            except Exception:
                logger.warning("Redis cache write failed for %s", cache_key, exc_info=True)

            return result

        return wrapper

    return decorator


async def close_redis():
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
