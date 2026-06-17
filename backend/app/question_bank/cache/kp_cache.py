#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Any

from backend.app.question_bank.schema.knowledge_point import GetKpDetailResponse
from backend.common.cache.redis_cache import RedisCache
from backend.common.cache.serializers import PydanticSerializer

# 知识点详情缓存 TTL: 1 小时
KP_DETAIL_CACHE_TTL = 3600

# 错因标签缓存 TTL: 30 分钟
REASON_TAG_CACHE_TTL = 1800

kp_detail_cache: RedisCache[GetKpDetailResponse] = RedisCache(
    prefix='qbank:kp_detail',
    ttl=KP_DETAIL_CACHE_TTL,
    serializer=PydanticSerializer(GetKpDetailResponse),
    local=True,  # 启用本地缓存，知识点数据全用户共享
    invalidate_pubsub=True,
)


class ReasonTagListSerializer:
    """错因标签列表序列化器"""

    def encode(self, value: list) -> bytes:
        from msgspec import json as msgspec_json

        # 将 Pydantic 模型列表转为字典列表
        data = [item.model_dump() if hasattr(item, 'model_dump') else item for item in value]
        return msgspec_json.encode(data)

    def decode(self, raw: bytes | str) -> list[dict[str, Any]]:
        from msgspec import json as msgspec_json

        return msgspec_json.decode(raw)


reason_tag_cache: RedisCache[list] = RedisCache(
    prefix='qbank:reason_tags',
    ttl=REASON_TAG_CACHE_TTL,
    serializer=ReasonTagListSerializer(),
    local=False,  # 用户相关数据，不启用本地缓存
    single_flight=True,
)
