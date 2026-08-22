import hashlib

from backend.database.redis import redis_client

_CONSUME_SCRIPT = """
local existing = redis.call('GET', KEYS[2])
if existing then
    return {tonumber(existing), 1}
end
local used = redis.call('INCR', KEYS[1])
if used == 1 then
    redis.call('EXPIRE', KEYS[1], ARGV[1])
end
if used > tonumber(ARGV[2]) then
    redis.call('DECR', KEYS[1])
    return {used, 0}
end
redis.call('SET', KEYS[2], tostring(used), 'EX', ARGV[1])
return {used, 1}
"""

_REFUND_SCRIPT = """
if redis.call('DEL', KEYS[2]) == 0 then
    return 0
end
local current = tonumber(redis.call('GET', KEYS[1]) or '0')
if current > 0 then
    redis.call('DECR', KEYS[1])
end
return 1
"""


class TrialCounterService:
    """Redis 试看计数器，支持业务来源幂等与失败回退。"""

    @staticmethod
    def idempotency_key(*, counter_key: str, source_ref: str) -> str:
        digest = hashlib.sha256(source_ref.encode()).hexdigest()
        return f'{counter_key}:source:{digest}'

    @staticmethod
    async def consume_once(
        *,
        counter_key: str,
        source_ref: str,
        ttl: int,
        limit: int,
    ) -> tuple[int, bool, str]:
        idempotency_key = TrialCounterService.idempotency_key(
            counter_key=counter_key,
            source_ref=source_ref,
        )
        result = await redis_client.eval(
            _CONSUME_SCRIPT,
            2,
            counter_key,
            idempotency_key,
            max(ttl, 1),
            max(limit, 0),
        )
        return int(result[0]), bool(result[1]), idempotency_key

    @staticmethod
    async def refund_once(*, counter_key: str, idempotency_key: str) -> bool:
        refunded = await redis_client.eval(
            _REFUND_SCRIPT,
            2,
            counter_key,
            idempotency_key,
        )
        return bool(refunded)


trial_counter_service = TrialCounterService()
