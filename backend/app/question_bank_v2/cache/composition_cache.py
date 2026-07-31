from backend.app.question_bank_v2.schema.composition import GetBankCompositionDetail
from backend.common.cache.redis_cache import RedisCache
from backend.common.cache.serializers import PydanticSerializer

composition_cache: RedisCache[GetBankCompositionDetail] = RedisCache(
    prefix='qbank-v2:composition:v2',
    ttl=3600,
    serializer=PydanticSerializer(GetBankCompositionDetail),
    local=False,
)
