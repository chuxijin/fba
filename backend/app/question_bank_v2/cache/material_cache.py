from typing import Any

from backend.common.cache.redis_cache import RedisCache
from backend.common.cache.serializers import JsonSerializer

material_blocks_cache: RedisCache[dict[str, Any]] = RedisCache(
    prefix='qbank-v2:material:blocks:v1',
    ttl=86400,
    serializer=JsonSerializer(),
    local=False,
)
