from typing import Any

from backend.app.question_bank_v2.schema.catalog import GetCollectionCatalogItem
from backend.common.cache.redis_cache import RedisCache
from backend.common.cache.serializers import JsonSerializer

public_catalog_cache: RedisCache[list[dict[str, Any]]] = RedisCache(
    prefix='qbank-v2:catalog:public:v1',
    ttl=600,
    serializer=JsonSerializer(),
    local=True,
    invalidate_pubsub=True,
)


def catalog_to_cache(data: list[GetCollectionCatalogItem]) -> list[dict[str, Any]]:
    return [item.model_dump(mode='json') for item in data]


def catalog_from_cache(data: list[dict[str, Any]]) -> list[GetCollectionCatalogItem]:
    return [GetCollectionCatalogItem.model_validate(item) for item in data]
