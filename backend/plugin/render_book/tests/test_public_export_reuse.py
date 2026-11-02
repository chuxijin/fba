"""公开插件排版复用与恢复逻辑单元测试：覆盖指纹计算、claim_public_export及start_public_export复用。

测试要求：
- mock 整个外部依赖，不使用真实 Redis/数据库/渲染引擎。
- 并发同内容仅一个后台任务；
- 不同账号/游客隔离；
- 相同IP无client不能共用（随机作用域）；
- 改变target复用；
- 忽略捕获metadata但保留scene/keypointName；
- 内容/材料/解析/格式/答案排布改变不复用；
- 原子重试条件：仅 retry_ticket 恰好等于旧 failed 凭证时允许新任务，其余 running/succeeded/unknown 均复用；
  同一旧 retry_ticket 重复请求不能连续创建新 failed 任务；
- 索引有但状态缺失保守 unknown；
- 成功复用不调用 render/consume_quota；
- start_public_export 只在 created=true 添加后台任务，返回 ticket 和 reused。
"""

import asyncio
import copy
import json

from collections.abc import Callable
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from backend.plugin.render_book.api.v1 import public as public_api
from backend.plugin.render_book.schema.public_reformat import PublicReformatRequest
from backend.plugin.render_book.service import public_export_service
from backend.plugin.render_book.service.public_export_service import (
    EXPORT_PREFIX,
    claim_public_export,
    export_content_fingerprint,
)


def _base_payload_data() -> dict:
    return {
        'paper': {
            'title': '测试卷',
            'source_platform': 'fenbi',
            'sections': [
                {
                    'name': '言语理解',
                    'questions': [
                        {
                            'stem': '题目题干1',
                            'options': [{'key': 'A', 'value': '选项A'}],
                            'material': '材料内容1',
                            'analysis': '解析内容1',
                        }
                    ],
                }
            ],
            'metadata': {
                'scene': 'practice',
                'keypointName': '选词填空',
                'extra_runtime_info': 'ignored_meta_1',
                'capture_timestamp': 12345678,
            },
        },
        'options': {
            'include_answer': True,
            'answer_placement': 'merged',
            'output_format': 'docx',
            'target': 'paper_only',
        },
    }


def _make_payload(**kwargs: object) -> PublicReformatRequest:
    data = _base_payload_data()
    data.update(kwargs)
    return PublicReformatRequest.model_validate(data)


# ---------------------------------------------------------------------------
# 1. export_content_fingerprint 测试
# ---------------------------------------------------------------------------


def test_fingerprint_target_does_not_affect_fingerprint() -> None:
    data1 = _base_payload_data()
    data1['target'] = 'computer_download'
    data2 = _base_payload_data()
    data2['target'] = 'mobile_sync'

    fp1 = export_content_fingerprint(PublicReformatRequest.model_validate(data1))
    fp2 = export_content_fingerprint(PublicReformatRequest.model_validate(data2))
    assert fp1 == fp2


def test_fingerprint_ignores_unrelated_metadata_but_keeps_scene_and_keypoint() -> None:
    data_base = _base_payload_data()
    fp_base = export_content_fingerprint(PublicReformatRequest.model_validate(data_base))

    # 修改无关捕获 metadata（如 capturedAt, sourceUrl 等），指纹保持一致
    data_irrelevant = copy.deepcopy(data_base)
    data_irrelevant['paper']['metadata']['capturedAt'] = '2026-11-02T12:00:00'
    data_irrelevant['paper']['metadata']['sourceUrl'] = 'https://fenbi.com/exam/123'
    data_irrelevant['paper']['metadata']['extracted_at'] = '2026-11-02'
    fp_irrelevant = export_content_fingerprint(PublicReformatRequest.model_validate(data_irrelevant))
    assert fp_base == fp_irrelevant

    # 修改 scene，指纹改变
    data_scene = copy.deepcopy(data_base)
    data_scene['paper']['metadata']['scene'] = 'exam'
    assert fp_base != export_content_fingerprint(PublicReformatRequest.model_validate(data_scene))

    # 修改 keypointName，指纹改变
    data_kp = copy.deepcopy(data_base)
    data_kp['paper']['metadata']['keypointName'] = '片段阅读'
    assert fp_base != export_content_fingerprint(PublicReformatRequest.model_validate(data_kp))


@pytest.mark.parametrize(
    'modifier',
    [
        lambda d: d['paper']['sections'][0]['questions'][0].update({'stem': '改变题干'}),
        lambda d: d['paper']['sections'][0]['questions'][0].update({'material': '改变材料'}),
        lambda d: d['paper']['sections'][0]['questions'][0].update({'analysis': '改变解析'}),
        lambda d: d['paper']['sections'][0]['questions'][0].update({'answer': 'B'}),
        lambda d: d['paper']['sections'][0]['questions'][0].update({'options': ['新选项']}),
        lambda d: d['paper']['metadata'].update({'nickname': '另一个署名'}),
        lambda d: d['options'].update({'output_format': 'pdf'}),
        lambda d: d['options'].update({'answer_placement': 'separate'}),
        lambda d: d['options'].update({'include_answer': False}),
    ],
)
def test_fingerprint_changes_on_content_material_analysis_format_and_placement(
    modifier: Callable[[dict], None],
) -> None:
    data_base = _base_payload_data()
    fp_base = export_content_fingerprint(PublicReformatRequest.model_validate(data_base))

    data_mod = copy.deepcopy(data_base)
    modifier(data_mod)
    fp_mod = export_content_fingerprint(PublicReformatRequest.model_validate(data_mod))
    assert fp_base != fp_mod


# ---------------------------------------------------------------------------
# 2. claim_public_export 作用域与隔离测试
# ---------------------------------------------------------------------------


class FakeRedisLuaEnv:
    """模拟 Redis 存储及 CLAIM_EXPORT_SCRIPT 行为"""

    def __init__(self) -> None:
        self.store: dict[str, str] = {}
        self.eval_calls: list[dict] = []

    async def eval(self, script: str, numkeys: int, content_key: str, export_prefix: str, *args: object) -> list:
        self.eval_calls.append({
            'script': script,
            'numkeys': numkeys,
            'content_key': content_key,
            'export_prefix': export_prefix,
            'args': args,
        })
        new_ticket = str(args[0])
        initial_state = str(args[1])
        _ = int(args[2])
        retry_ticket = str(args[3])
        unknown_state = str(args[4])

        previous = self.store.get(content_key)
        if previous:
            task_key = f'{export_prefix}{previous}'
            raw = self.store.get(task_key)
            if raw:
                state = json.loads(raw)
                if not (state.get('status') == 'failed' and previous == retry_ticket):
                    return [previous.encode(), 0]
            else:
                self.store[task_key] = unknown_state
                return [previous.encode(), 0]

        self.store[content_key] = new_ticket
        self.store[f'{export_prefix}{new_ticket}'] = initial_state
        return [new_ticket.encode(), 1]


@pytest.mark.asyncio
async def test_claim_scope_user_vs_guest_isolation(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_redis = FakeRedisLuaEnv()
    monkeypatch.setattr(public_export_service.redis_client, 'eval', fake_redis.eval)

    payload = _make_payload()
    req1 = SimpleNamespace(headers={'X-Render-Client': 'a' * 32})
    req2 = SimpleNamespace(headers={'X-Render-Client': 'b' * 32})

    # 用户1
    ticket_u1, created_u1 = await claim_public_export(request=req1, user_id=1, payload=payload)
    # 用户2（不同用户）
    ticket_u2, created_u2 = await claim_public_export(request=req1, user_id=2, payload=payload)
    # 游客A
    ticket_ga, created_ga = await claim_public_export(request=req1, user_id=None, payload=payload)
    # 游客B
    ticket_gb, created_gb = await claim_public_export(request=req2, user_id=None, payload=payload)

    # 4个不同的 scope 应该各自创建独立的新任务，互不复用
    assert created_u1 and created_u2 and created_ga and created_gb
    tickets = {ticket_u1, ticket_u2, ticket_ga, ticket_gb}
    assert len(tickets) == 4
    # eval 的 content_key 均不相同
    content_keys = {call['content_key'] for call in fake_redis.eval_calls}
    assert len(content_keys) == 4


@pytest.mark.asyncio
async def test_claim_scope_guest_without_valid_client_generates_random_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_redis = FakeRedisLuaEnv()
    monkeypatch.setattr(public_export_service.redis_client, 'eval', fake_redis.eval)

    payload = _make_payload()
    req_no_header = SimpleNamespace(headers={})
    req_invalid_hex = SimpleNamespace(headers={'X-Render-Client': 'not-32-hex-chars!'})

    t1, c1 = await claim_public_export(request=req_no_header, user_id=None, payload=payload)
    t2, c2 = await claim_public_export(request=req_no_header, user_id=None, payload=payload)
    t3, c3 = await claim_public_export(request=req_invalid_hex, user_id=None, payload=payload)

    # 相同 IP / 无有效 32 字符 hex client header 的游客请求，无法共享，每次独立生成随机作用域
    assert c1 and c2 and c3
    assert len({t1, t2, t3}) == 3
    assert len({call['content_key'] for call in fake_redis.eval_calls}) == 3


# ---------------------------------------------------------------------------
# 3. claim_public_export 复用与重试边界测试（模拟真实 Lua 逻辑）
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_claim_reuses_running_succeeded_and_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_redis = FakeRedisLuaEnv()
    monkeypatch.setattr(public_export_service.redis_client, 'eval', fake_redis.eval)

    client_id = 'c' * 32
    req = SimpleNamespace(headers={'X-Render-Client': client_id})
    payload = _make_payload()

    # 1. 首次创建 -> running
    ticket1, created1 = await claim_public_export(request=req, user_id=None, payload=payload)
    assert created1 is True

    # 再次请求同内容 -> 复用 running
    ticket2, created2 = await claim_public_export(request=req, user_id=None, payload=payload)
    assert ticket2 == ticket1
    assert created2 is False

    # 任务变为 succeeded -> 依然复用
    fake_redis.store[f'{EXPORT_PREFIX}{ticket1}'] = json.dumps({'status': 'succeeded', 'result': {}})
    ticket3, created3 = await claim_public_export(request=req, user_id=None, payload=payload)
    assert ticket3 == ticket1
    assert created3 is False

    # 任务变为 unknown -> 依然复用
    fake_redis.store[f'{EXPORT_PREFIX}{ticket1}'] = json.dumps({'status': 'unknown', 'message': 'processing'})
    ticket4, created4 = await claim_public_export(request=req, user_id=None, payload=payload)
    assert ticket4 == ticket1
    assert created4 is False


@pytest.mark.asyncio
async def test_claim_retry_ticket_conditions_and_idempotency(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_redis = FakeRedisLuaEnv()
    monkeypatch.setattr(public_export_service.redis_client, 'eval', fake_redis.eval)

    client_id = 'd' * 32
    req = SimpleNamespace(headers={'X-Render-Client': client_id})
    payload = _make_payload()

    # 首次创建
    ticket1, created1 = await claim_public_export(request=req, user_id=None, payload=payload)
    assert created1 is True

    # 标记失败
    fake_redis.store[f'{EXPORT_PREFIX}{ticket1}'] = json.dumps({'status': 'failed', 'message': 'err'})

    # 请求未带 retry_ticket -> 依然复用旧 failed，不允许创建新任务
    ticket_no_retry, created_no_retry = await claim_public_export(request=req, user_id=None, payload=payload)
    assert ticket_no_retry == ticket1
    assert created_no_retry is False

    # 请求带了错误的 retry_ticket -> 依然复用旧 failed
    payload_wrong = _make_payload(retry_ticket='W' * 32)
    ticket_wrong, created_wrong = await claim_public_export(request=req, user_id=None, payload=payload_wrong)
    assert ticket_wrong == ticket1
    assert created_wrong is False

    # 请求带恰好等于旧 failed 凭证的 retry_ticket -> 允许创建新任务
    payload_retry = _make_payload(retry_ticket=ticket1)
    ticket_new, created_new = await claim_public_export(request=req, user_id=None, payload=payload_retry)
    assert created_new is True
    assert ticket_new != ticket1

    # 此时新任务状态是 running。如果同一旧 retry_ticket 重复发起请求（丢包重发），不能连续创建新任务
    ticket_dup, created_dup = await claim_public_export(request=req, user_id=None, payload=payload_retry)
    assert ticket_dup == ticket_new
    assert created_dup is False
    # 即使替代任务立即失败，旧重试请求的重放也不能继续创建第三个任务。
    fake_redis.store[f'{EXPORT_PREFIX}{ticket_new}'] = json.dumps({'status': 'failed'})
    ticket_again, created_again = await claim_public_export(request=req, user_id=None, payload=payload_retry)
    assert ticket_again == ticket_new
    assert created_again is False


@pytest.mark.asyncio
async def test_claim_missing_state_writes_unknown_and_reuses(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_redis = FakeRedisLuaEnv()
    monkeypatch.setattr(public_export_service.redis_client, 'eval', fake_redis.eval)

    client_id = 'e' * 32
    req = SimpleNamespace(headers={'X-Render-Client': client_id})
    payload = _make_payload()

    # 首次创建
    ticket1, _ = await claim_public_export(request=req, user_id=None, payload=payload)

    # 模拟极端情况：索引存在，但对应 task 状态在 Redis 中丢失或缺失
    fake_redis.store.pop(f'{EXPORT_PREFIX}{ticket1}', None)

    # 再次发起请求
    ticket2, created2 = await claim_public_export(request=req, user_id=None, payload=payload)
    assert ticket2 == ticket1
    assert created2 is False

    # 应写入保守 unknown 状态，不连续盲目新建
    recovered_state = json.loads(fake_redis.store[f'{EXPORT_PREFIX}{ticket1}'])
    assert recovered_state['status'] == 'unknown'
    assert '勿重复排版' in recovered_state['message']


# ---------------------------------------------------------------------------
# 4. start_public_export API 集成与后台任务调度
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_start_public_export_created_true_schedules_background_tasks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(public_api, 'get_public_user', AsyncMock(return_value=None))
    monkeypatch.setattr(public_api, 'claim_public_export', AsyncMock(return_value=('ticket_123', True)))
    tasks = Mock()
    req = SimpleNamespace(headers={'X-Render-Client': 'f' * 32})
    payload = _make_payload()

    resp = await public_api.start_public_export(request=req, payload=payload, tasks=tasks)
    assert resp.data == {'ticket': 'ticket_123', 'reused': False}
    tasks.add_task.assert_called_once_with(public_api._run_public_export, 'ticket_123', req, payload)


@pytest.mark.asyncio
async def test_start_public_export_reused_does_not_schedule_background_task(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(public_api, 'get_public_user', AsyncMock(return_value=None))
    monkeypatch.setattr(public_api, 'claim_public_export', AsyncMock(return_value=('ticket_existing', False)))
    tasks = Mock()
    req = SimpleNamespace(headers={'X-Render-Client': 'f' * 32})
    payload = _make_payload()

    resp = await public_api.start_public_export(request=req, payload=payload, tasks=tasks)
    assert resp.data == {'ticket': 'ticket_existing', 'reused': True}
    tasks.add_task.assert_not_called()


@pytest.mark.asyncio
async def test_concurrency_same_content_only_one_background_task(monkeypatch: pytest.MonkeyPatch) -> None:
    """并发调用实际 claim，仅以原子 Redis 模型隔离外部依赖。"""
    fake_redis = FakeRedisLuaEnv()
    monkeypatch.setattr(public_export_service.redis_client, 'eval', fake_redis.eval)
    monkeypatch.setattr(public_api, 'get_public_user', AsyncMock(return_value=None))

    tasks1 = Mock()
    tasks2 = Mock()
    tasks3 = Mock()
    req = SimpleNamespace(headers={'X-Render-Client': '0' * 32})
    payload = _make_payload()

    results = await asyncio.gather(
        *(
            public_api.start_public_export(request=req, payload=payload, tasks=tasks)
            for tasks in (tasks1, tasks2, tasks3)
        )
    )
    assert len({result.data['ticket'] for result in results}) == 1
    assert sum(not result.data['reused'] for result in results) == 1

    assert tasks1.add_task.call_count == 1
    assert tasks2.add_task.call_count == 0
    assert tasks3.add_task.call_count == 0


@pytest.mark.asyncio
async def test_successful_reuse_does_not_call_render_or_consume_quota(monkeypatch: pytest.MonkeyPatch) -> None:
    """端到端验证：复用请求不会执行 _run_public_export，也不会进入 public_reformat_paper 或扣额度。"""
    monkeypatch.setattr(public_api, 'get_public_user', AsyncMock(return_value=None))
    monkeypatch.setattr(public_api, 'claim_public_export', AsyncMock(return_value=('cached_ticket', False)))

    render_mock = AsyncMock()
    monkeypatch.setattr(public_api, 'public_reformat_paper', render_mock)
    consume_mock = AsyncMock()
    monkeypatch.setattr(public_api.render_book_quota_service, 'consume_quota', consume_mock)
    tasks = Mock()

    payload = _make_payload()
    resp = await public_api.start_public_export(request=SimpleNamespace(), payload=payload, tasks=tasks)

    assert resp.data['reused'] is True
    # tasks.add_task 未被调用
    tasks.add_task.assert_not_called()
    render_mock.assert_not_awaited()
    consume_mock.assert_not_awaited()
