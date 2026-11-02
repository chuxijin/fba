"""插件短任务幂等：同一归属、相同内容在交付有效期内只创建一个任务。"""

import hashlib
import json
import re
import secrets
import time

from backend.database.redis import redis_client
from backend.plugin.render_book.schema.public_reformat import PublicReformatRequest
from backend.plugin.render_book.service.public_delivery_service import DELIVERY_TTL

EXPORT_PREFIX = 'fba:render_book:export:'
EXPORT_CONTENT_PREFIX = 'fba:render_book:export_content:v1:'

# 内容索引和初始任务状态同一次原子写入，不能先占索引再创建状态。
# 只有调用者明确重试的那一份 failed 任务可被替换；丢包重发不能连续创建失败任务。
CLAIM_EXPORT_SCRIPT = """
local previous = redis.call('GET', KEYS[1])
if previous then
    local raw = redis.call('GET', ARGV[1] .. previous)
    if raw then
        local state = cjson.decode(raw)
        if not (state.status == 'failed' and previous == ARGV[5]) then
            return {previous, 0}
        end
    else
        redis.call('SET', ARGV[1] .. previous, ARGV[6], 'EX', ARGV[4])
        return {previous, 0}
    end
end
redis.call('SET', KEYS[1], ARGV[2], 'EX', ARGV[4])
redis.call('SET', ARGV[1] .. ARGV[2], ARGV[3], 'EX', ARGV[4])
return {ARGV[2], 1}
"""


def export_content_fingerprint(payload: PublicReformatRequest) -> str:
    """保守比较全部内容，仅忽略不影响排版的捕获信息和交付终端。"""
    paper = payload.paper.model_dump(mode='json')
    metadata = paper.get('metadata') or {}
    paper['metadata'] = {
        key: value
        for key, value in metadata.items()
        if key not in {'capturedAt', 'captured_at', 'extractedAt', 'extracted_at', 'sourceUrl', 'source_url'}
    }
    paper['total_questions'] = sum(len(section.questions) for section in payload.paper.sections)
    content = {'renderer': 'public-v1', 'paper': paper, 'options': payload.options.model_dump(mode='json')}
    raw = json.dumps(content, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(raw.encode()).hexdigest()


async def claim_public_export(
    *, request: object, user_id: int | None, payload: PublicReformatRequest
) -> tuple[str, bool]:
    headers = getattr(request, 'headers', {})
    client = headers.get('X-Render-Client', '')
    # 账号由服务端认证结果决定；游客使用插件生成的随机秘密，不按 IP 或卷名共享。
    scope = f'user:{user_id}' if user_id is not None else f'guest:{client}'
    if user_id is None and not re.fullmatch(r'[a-f0-9]{32}', client):
        scope = f'guest:{secrets.token_hex(16)}'
    digest = hashlib.sha256(f'{scope}:{export_content_fingerprint(payload)}'.encode()).hexdigest()
    ticket = secrets.token_urlsafe(24)
    now = time.time()
    state = json.dumps({'status': 'running', 'started_at': now, 'expires_at': now + DELIVERY_TTL})
    unknown = json.dumps({'status': 'unknown', 'message': '暂时无法确认原任务结果，请先查看我的题本，勿重复排版。'})
    result = await redis_client.eval(
        CLAIM_EXPORT_SCRIPT,
        1,
        f'{EXPORT_CONTENT_PREFIX}{digest}',
        EXPORT_PREFIX,
        ticket,
        state,
        DELIVERY_TTL,
        payload.retry_ticket or '',
        unknown,
    )
    previous = result[0].decode() if isinstance(result[0], bytes) else str(result[0])
    return previous, bool(int(result[1]))
