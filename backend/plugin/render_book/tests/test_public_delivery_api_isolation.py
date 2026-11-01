"""公开插件排版接口隔离单元测试：全程 mock 数据库/Redis/渲染/微信。"""

import json
import re
import time

from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from backend.common.exception import errors
from backend.plugin.render_book.api.v1 import public as public_api
from backend.plugin.render_book.schema.public_reformat import PublicReformatRequest

TICKET = 'A' * 32


@pytest.mark.parametrize('is_mistake', [False, True])
def test_delivery_filenames_do_not_treat_titles_or_keypoints_as_paths(*, is_mistake: bool) -> None:
    names = public_api.build_clean_paper_and_filenames(
        raw_title='测试\\../试卷\r\n标题',
        platform='fenbi',
        is_mistake=is_mistake,
        total_q=3,
        keypoint_name='资料\\../分析\t知识点',
    )
    for name in names.values():
        assert not any(character in name for character in '\\/\r\n\t')


class FakeSessionContext:
    async def __aenter__(self) -> AsyncMock:
        return AsyncMock()

    async def __aexit__(self, *_exc: object) -> bool:
        return False


def _payload(output_format: str = 'docx') -> PublicReformatRequest:
    return PublicReformatRequest.model_validate({
        'paper': {
            'title': '测试卷',
            'source_platform': 'fenbi',
            'sections': [
                {
                    'name': '言语理解',
                    'questions': [{'stem': '题干', 'options': [{'key': 'A', 'value': '选项'}]}],
                }
            ],
        },
        'options': {'include_answer': False, 'answer_placement': 'merged', 'output_format': output_format},
    })


def _prepare_render_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    template_root = tmp_path / 'templates'
    template = template_root / 'gongkao_xingce' / '1.0.0' / 'template.docx'
    template.parent.mkdir(parents=True)
    template.write_bytes(b'template')
    monkeypatch.setattr(public_api, 'TEMPLATES_ROOT', template_root)
    monkeypatch.setattr(public_api.settings, 'RENDER_BOOK_STORAGE_ROOT', str(tmp_path / 'storage'))


def _fake_doc_payload() -> SimpleNamespace:
    return SimpleNamespace(book=SimpleNamespace(title='原始标题'), paper=SimpleNamespace(question_count=1))


def _fake_render_all() -> Mock:
    def render(**kwargs: object) -> dict[str, str]:
        return {'docx': str(kwargs['output_dir']) + '/out.docx', 'pdf': str(kwargs['output_dir']) + '/out.pdf'}

    return Mock(side_effect=render)


@pytest.fixture(autouse=True)
def _clear_in_memory_caches() -> Iterator[None]:
    public_api._IN_MEMORY_EXPORT_CACHE.clear()
    public_api._IN_MEMORY_DOWNLOAD_CACHE.clear()
    yield
    public_api._IN_MEMORY_EXPORT_CACHE.clear()
    public_api._IN_MEMORY_DOWNLOAD_CACHE.clear()


# ---------------------------------------------------------------------------
# 异步提交 / 状态查询
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_start_public_export_marks_running_and_schedules_background(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(public_api, 'get_public_user', AsyncMock(return_value=None))
    redis_set = AsyncMock()
    monkeypatch.setattr(public_api.redis_client, 'set', redis_set)
    tasks = Mock()

    request = SimpleNamespace()
    payload = _payload()
    result = await public_api.start_public_export(request=request, payload=payload, tasks=tasks)

    ticket = result.data['ticket']
    assert re.fullmatch(r'[A-Za-z0-9_-]{32}', ticket)
    redis_set.assert_awaited_once()
    key = redis_set.await_args.args[0]
    state = json.loads(redis_set.await_args.args[1])
    assert key == f'{public_api.EXPORT_PREFIX}{ticket}'
    assert state['status'] == 'running'
    assert redis_set.await_args.kwargs['ex'] == public_api.DELIVERY_TTL
    tasks.add_task.assert_called_once_with(public_api._run_public_export, ticket, request, payload)


@pytest.mark.parametrize('ticket', ['', 'short', 'a' * 31, 'a' * 33, 'bad ticket with space'])
@pytest.mark.asyncio
async def test_get_public_export_rejects_invalid_ticket(monkeypatch: pytest.MonkeyPatch, ticket: str) -> None:
    redis_get = AsyncMock()
    monkeypatch.setattr(public_api.redis_client, 'get', redis_get)

    with pytest.raises(errors.NotFoundError, match='排版任务不存在'):
        await public_api.get_public_export(ticket)

    redis_get.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_public_export_uses_fresh_memory_cache_without_redis(monkeypatch: pytest.MonkeyPatch) -> None:
    state = {'status': 'succeeded', 'result': {'job_id': 'j1'}}
    public_api._IN_MEMORY_EXPORT_CACHE[TICKET] = (time.time(), state)
    redis_get = AsyncMock()
    monkeypatch.setattr(public_api.redis_client, 'get', redis_get)

    result = await public_api.get_public_export(TICKET)

    assert result.data == state
    redis_get.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_public_export_expired_memory_falls_back_to_redis(monkeypatch: pytest.MonkeyPatch) -> None:
    public_api._IN_MEMORY_EXPORT_CACHE[TICKET] = (time.time() - public_api.DELIVERY_TTL - 10, {'status': 'stale'})
    state = {'status': 'failed', 'message': '排版失败'}
    monkeypatch.setattr(public_api.redis_client, 'get', AsyncMock(return_value=json.dumps(state)))

    result = await public_api.get_public_export(TICKET)

    assert result.data == state
    assert TICKET not in public_api._IN_MEMORY_EXPORT_CACHE


@pytest.mark.asyncio
async def test_get_public_export_missing_redis_state_raises_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(public_api.redis_client, 'get', AsyncMock(return_value=None))

    with pytest.raises(errors.NotFoundError, match='已过期'):
        await public_api.get_public_export(TICKET)


@pytest.mark.asyncio
async def test_get_public_export_marks_stale_running_as_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    state = {'status': 'running', 'started_at': time.time() - 1300}
    monkeypatch.setattr(public_api.redis_client, 'get', AsyncMock(return_value=json.dumps(state)))

    result = await public_api.get_public_export(TICKET)

    assert result.data['status'] == 'failed'
    assert '排版处理时间较长' in result.data['message']


# ---------------------------------------------------------------------------
# 后台执行最终状态
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_public_export_success_publishes_state_and_clears_memory(monkeypatch: pytest.MonkeyPatch) -> None:
    api_result = SimpleNamespace(data=SimpleNamespace(model_dump=lambda mode='json': {'job_id': 'j1'}))
    monkeypatch.setattr(public_api, 'async_db_session', lambda: FakeSessionContext())
    monkeypatch.setattr(public_api, 'public_reformat_paper', AsyncMock(return_value=api_result))
    redis_set = AsyncMock()
    monkeypatch.setattr(public_api.redis_client, 'set', redis_set)

    await public_api._run_public_export(TICKET, SimpleNamespace(), _payload())

    redis_set.assert_awaited_once()
    assert redis_set.await_args.args[0] == f'{public_api.EXPORT_PREFIX}{TICKET}'
    state = json.loads(redis_set.await_args.args[1])
    assert state == {'status': 'succeeded', 'result': {'job_id': 'j1'}}
    assert redis_set.await_args.kwargs['ex'] == public_api.DELIVERY_TTL
    assert TICKET not in public_api._IN_MEMORY_EXPORT_CACHE


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'error,expected',
    [
        (errors.RequestError(code=429, msg='今日额度已用完'), '今日额度已用完'),
        (RuntimeError('boom'), '排版失败，请检查试题内容或稍后重试'),
    ],
)
async def test_run_public_export_reports_business_and_generic_errors(
    monkeypatch: pytest.MonkeyPatch, error: Exception, expected: str
) -> None:
    monkeypatch.setattr(public_api, 'async_db_session', lambda: FakeSessionContext())
    monkeypatch.setattr(public_api, 'public_reformat_paper', AsyncMock(side_effect=error))
    redis_set = AsyncMock()
    monkeypatch.setattr(public_api.redis_client, 'set', redis_set)

    await public_api._run_public_export(TICKET, SimpleNamespace(), _payload())

    state = json.loads(redis_set.await_args.args[1])
    assert state['status'] == 'failed'
    assert state['message'] == expected


@pytest.mark.asyncio
async def test_run_public_export_redis_failure_keeps_memory_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    api_result = SimpleNamespace(data=SimpleNamespace(model_dump=lambda mode='json': {'job_id': 'j1'}))
    monkeypatch.setattr(public_api, 'async_db_session', lambda: FakeSessionContext())
    monkeypatch.setattr(public_api, 'public_reformat_paper', AsyncMock(return_value=api_result))
    redis_set = AsyncMock(side_effect=RuntimeError('redis down'))
    sleep = AsyncMock()
    monkeypatch.setattr(public_api.redis_client, 'set', redis_set)
    monkeypatch.setattr(public_api.anyio, 'sleep', sleep)

    await public_api._run_public_export(TICKET, SimpleNamespace(), _payload())

    assert redis_set.await_count == 3
    assert sleep.await_count == 2
    assert TICKET in public_api._IN_MEMORY_EXPORT_CACHE
    assert public_api._IN_MEMORY_EXPORT_CACHE[TICKET][1]['status'] == 'succeeded'


# ---------------------------------------------------------------------------
# 登记失败回滚与额度退回
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_public_reformat_registration_failure_rolls_back_and_refunds_guest(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _prepare_render_env(monkeypatch, tmp_path)
    monkeypatch.setattr(public_api, 'get_public_user', AsyncMock(return_value=None))
    monkeypatch.setattr(public_api, 'get_request_ip', lambda _request: '1.2.3.4')
    monkeypatch.setattr(public_api, '_get_trial_policy_limit', AsyncMock(return_value=5))
    monkeypatch.setattr(public_api, 'convert_unified_paper_to_document_payload', lambda _payload: _fake_doc_payload())
    monkeypatch.setattr(public_api, 'adapt_gongkao_payload', lambda _payload: {})
    monkeypatch.setattr(public_api.docx_render_engine, 'render_all', _fake_render_all())
    monkeypatch.setattr(public_api, 'register_public_book', AsyncMock(side_effect=errors.ServerError(msg='登记失败')))
    consume = AsyncMock()
    monkeypatch.setattr(public_api.render_book_quota_service, 'consume_quota', consume)
    redis_eval = AsyncMock(side_effect=[1, 0])
    monkeypatch.setattr(public_api.redis_client, 'eval', redis_eval)
    db = AsyncMock()

    with pytest.raises(errors.ServerError, match='排版生成或题本保存失败'):
        await public_api.public_reformat_paper(request=SimpleNamespace(), payload=_payload(), db=db)

    db.rollback.assert_awaited_once()
    db.commit.assert_not_awaited()
    consume.assert_not_awaited()
    assert redis_eval.await_count == 2
    assert 'DECR' in str(redis_eval.await_args_list[1].args[0]).upper()


@pytest.mark.asyncio
async def test_public_reformat_registration_failure_refunds_logged_in_quota(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _prepare_render_env(monkeypatch, tmp_path)
    user = SimpleNamespace(id=7)
    decision = object()
    monkeypatch.setattr(public_api, 'get_public_user', AsyncMock(return_value=user))
    monkeypatch.setattr(public_api, 'get_request_ip', lambda _request: '1.2.3.4')
    monkeypatch.setattr(public_api, '_get_trial_policy_limit', AsyncMock(return_value=5))
    monkeypatch.setattr(public_api, 'convert_unified_paper_to_document_payload', lambda _payload: _fake_doc_payload())
    monkeypatch.setattr(public_api, 'adapt_gongkao_payload', lambda _payload: {})
    monkeypatch.setattr(public_api.docx_render_engine, 'render_all', _fake_render_all())
    register = AsyncMock(side_effect=errors.ServerError(msg='登记失败'))
    monkeypatch.setattr(public_api, 'register_public_book', register)
    consume = AsyncMock(return_value=decision)
    refund = AsyncMock()
    monkeypatch.setattr(public_api.render_book_quota_service, 'consume_quota', consume)
    monkeypatch.setattr(public_api.render_book_quota_service, 'refund_quota', refund)
    redis_eval = AsyncMock()
    monkeypatch.setattr(public_api.redis_client, 'eval', redis_eval)
    db = AsyncMock()

    with pytest.raises(errors.ServerError, match='排版生成或题本保存失败'):
        await public_api.public_reformat_paper(request=SimpleNamespace(), payload=_payload(), db=db)

    consume.assert_awaited_once()
    source_ref = consume.await_args.kwargs['source_ref']
    assert source_ref.startswith('public_reformat:')
    refund.assert_awaited_once()
    assert refund.await_args.args[0] is db
    assert refund.await_args.kwargs == {'user_id': 7, 'decision': decision, 'source_ref': source_ref}
    db.rollback.assert_awaited_once()
    db.commit.assert_awaited_once()
    redis_eval.assert_not_awaited()
    assert register.await_count == 1
