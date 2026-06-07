#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Any

from backend.common.cache.redis_cache import RedisCache
from backend.common.cache.serializers import JsonSerializer


collections_cache: RedisCache[list[dict[str, Any]]] = RedisCache(
    prefix='qbank:collections:v1',
    ttl=60,
    serializer=JsonSerializer(),
)


solution_static_cache: RedisCache[dict[str, Any]] = RedisCache(
    prefix='qbank:solution:static',
    ttl=86400,
    serializer=JsonSerializer(),
)
