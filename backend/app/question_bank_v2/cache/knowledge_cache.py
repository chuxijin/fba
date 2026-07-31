from backend.app.question_bank_v2.schema.knowledge import GetKnowledgePointTreeResult
from backend.common.cache.redis_cache import RedisCache
from backend.common.cache.serializers import PydanticSerializer

points_tree_cache: RedisCache[GetKnowledgePointTreeResult] = RedisCache(
    prefix='qbank-v2:knowledge:points-tree:v1',
    ttl=1800,
    serializer=PydanticSerializer(GetKnowledgePointTreeResult),
    local=True,
    invalidate_pubsub=True,
)
