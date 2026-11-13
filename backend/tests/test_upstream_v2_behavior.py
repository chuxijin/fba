import importlib

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from fastapi import FastAPI
from fastapi.testclient import TestClient
from redis_fastapi import get_async_redis

from backend.app.admin.utils.user_provider import get_current_user
from backend.common.exception import errors
from backend.common.security.permission import RequestPermission
from backend.common.security.rbac import DependsRBAC
from backend.database import db as database


@pytest.mark.parametrize('failure', [None, 'missing', 'disabled', 'missing_dept', 'disabled_dept', 'disabled_roles'])
async def test_custom_user_provider_checks_available_user(monkeypatch: pytest.MonkeyPatch, failure: str | None) -> None:
    user = SimpleNamespace(id=7, status=1, dept_id=None, dept=None, roles=[])
    if failure == 'disabled':
        user.status = 0
    elif failure == 'missing_dept':
        user.dept_id = 1
    elif failure == 'disabled_dept':
        user.dept_id, user.dept = 1, SimpleNamespace(status=0)
    elif failure == 'disabled_roles':
        user.roles = [SimpleNamespace(status=0)]
    module = importlib.import_module('backend.app.admin.service.user_service')
    lookup = AsyncMock(return_value=None if failure == 'missing' else user)
    monkeypatch.setattr(module.user_dao, 'get_join', lookup)
    session = object()
    if failure:
        with pytest.raises(errors.TokenError if failure == 'missing' else errors.AuthorizationError):
            await get_current_user(session, 7)
    else:
        assert await get_current_user(session, 7) is user
    lookup.assert_awaited_once_with(session, user_id=7)


@pytest.mark.parametrize('admin', [False, True])
def test_question_analysis_orm_response_and_membership_branch(monkeypatch: pytest.MonkeyPatch, admin: bool) -> None:
    module = importlib.import_module('backend.app.question_bank.api.v1.question')
    row = SimpleNamespace(
        id=1, question_id=7, type='official', version_no=2, is_default=True, answer_data={'answer': 'A'},
        content='解析', status=10, view_count=2, helpful_count=0, unhelpful_count=0,
        created_time=datetime(2026, 1, 1, tzinfo=UTC), updated_time=None,
    )
    lookup = AsyncMock(return_value=row)
    verify = AsyncMock()
    monkeypatch.setattr(module.question_service, 'get_analysis', lookup)
    monkeypatch.setattr(module.membership_service, 'verify_question_access', verify)
    monkeypatch.setattr(module, '_should_bypass_membership_checks', lambda request: admin)
    app = FastAPI()

    @app.middleware('http')
    async def identity(request, call_next):
        request.scope['user'] = SimpleNamespace(id=9)
        return await call_next(request)

    async def session():
        yield None

    app.dependency_overrides[database.get_db_transaction] = session
    app.add_api_route('/{pk}/analysis', module.get_question_analysis, methods=['GET'])
    with TestClient(app) as client:
        result = client.get('/7/analysis')
    assert result.status_code == 200
    assert result.json()['data']['answer_data'] == {'answer': 'A'}
    assert result.json()['data']['version_no'] == 2
    assert isinstance(result.json()['data']['created_time'], str)
    lookup.assert_awaited_once_with(db=None, question_id=7, increment_view=not admin)
    if admin:
        verify.assert_not_awaited()
    else:
        verify.assert_awaited_once_with(db=None, user_id=9, question_id=7)


def test_question_statistics_orm_response(monkeypatch: pytest.MonkeyPatch) -> None:
    module = importlib.import_module('backend.app.question_bank.api.v1.question')
    row = SimpleNamespace(
        question_id=7, attempt_count=4, correct_count=3, correct_rate=Decimal('75.00'),
        avg_answer_time=Decimal('4.50'), collect_count=0, note_count=0,
        last_updated=datetime(2026, 1, 1, tzinfo=UTC),
    )
    lookup = AsyncMock(return_value=row)
    monkeypatch.setattr(module.question_service, 'get_statistics', lookup)
    monkeypatch.setattr(module, '_should_bypass_membership_checks', lambda request: True)
    app = FastAPI()

    async def session():
        yield None

    app.dependency_overrides[database.get_db] = session
    app.add_api_route('/{pk}/statistics', module.get_question_statistics, methods=['GET'])
    with TestClient(app) as client:
        result = client.get('/7/statistics')
    assert result.status_code == 200
    assert result.json()['data']['correct_rate'] == '75.00'
    assert result.json()['data']['valid_attempt_count'] == 0
    lookup.assert_awaited_once_with(db=None, question_id=7)


@pytest.mark.parametrize(
    ['module_name', 'service_name', 'body', 'group'],
    [
        ('config', 'config_service', {'name': 'test', 'key': 'test', 'value': '1', 'is_frontend': True}, 'config'),
        ('dict_data', 'dict_data_service', {'type_id': 1, 'label': 'test', 'value': '1', 'sort': 0, 'status': 1}, 'dict'),
        ('dict_type', 'dict_type_service', {'name': 'test', 'code': 'test'}, 'dict'),
    ],
)
@pytest.mark.parametrize('failure', [None, 'endpoint', 'commit'])
def test_cached_writes_commit_before_http_eviction(
    monkeypatch: pytest.MonkeyPatch, module_name: str, service_name: str, body: dict, group: str, failure: str | None,
) -> None:
    package = 'config' if module_name == 'config' else 'dict'
    module = importlib.import_module(f'backend.plugin.{package}.api.v1.sys.{module_name}')
    cache_module = importlib.import_module('redis_fastapi.cache')
    events = []

    @asynccontextmanager
    async def transaction():
        events.append('begin')
        try:
            yield None
            if failure == 'commit':
                raise RuntimeError('commit failed')
            events.append('commit')
        except Exception:
            events.append('rollback')
            raise

    async def create(**kwargs):
        events.append('write')
        if failure == 'endpoint':
            raise RuntimeError('endpoint failed')

    async def evict(redis, eviction_group):
        assert eviction_group == group
        events.append('evict')

    async def bypass():
        return None

    monkeypatch.setattr(database, 'async_db_session', SimpleNamespace(begin=transaction))
    monkeypatch.setattr(getattr(module, service_name), 'create', create)
    monkeypatch.setattr(cache_module, '_evict_by_group', evict)
    app = FastAPI()
    app.dependency_overrides[get_async_redis] = bypass
    app.dependency_overrides[DependsRBAC.dependency] = bypass
    for route in module.router.routes:
        for dependency in route.dependencies:
            if isinstance(dependency.dependency, RequestPermission):
                app.dependency_overrides[dependency.dependency] = bypass
    app.include_router(module.router, prefix='/write')
    with TestClient(app, raise_server_exceptions=False) as client:
        result = client.post('/write', json=body)
    assert result.status_code == (500 if failure else 200)
    assert events == (['begin', 'write', 'rollback'] if failure else ['begin', 'write', 'commit', 'evict'])


@pytest.mark.parametrize('failure', [False, True])
async def test_core_cache_subscription_lifecycle_with_fake_services(monkeypatch: pytest.MonkeyPatch, failure: bool) -> None:
    from backend.core import registrar

    events = []
    monkeypatch.setattr(registrar, 'create_tables', AsyncMock())
    monkeypatch.setattr(registrar, 'dispose_database', AsyncMock())
    monkeypatch.setattr(registrar.settings, 'SNOWFLAKE_ENABLED', False)
    monkeypatch.setattr(registrar.settings, 'DATABASE_PK_MODE', 'autoincrement')
    monkeypatch.setattr(registrar, 'redis_client', SimpleNamespace(init=AsyncMock(), aclose=AsyncMock()))
    monkeypatch.setattr(registrar, 'knowledge_invalidation_tasks', set())
    monkeypatch.setattr(registrar.public_knowledge_cache, 'close', AsyncMock())
    monkeypatch.setattr(registrar.OperaLogMiddleware, 'consumer', AsyncMock())
    monkeypatch.setattr(registrar.OperaLogMiddleware, 'stop_consumer', AsyncMock())
    monkeypatch.setattr(registrar.cache_pubsub_manager, 'start_listener', Mock(side_effect=lambda: events.append('start')))
    monkeypatch.setattr(registrar.cache_pubsub_manager, 'stop_listener', AsyncMock(side_effect=lambda: events.append('stop')))
    try:
        async with registrar.register_init(FastAPI()):
            events.append('body')
            if failure:
                raise RuntimeError('body failed')
    except RuntimeError:
        assert failure
    assert events == ['start', 'body', 'stop']
    registrar.cache_pubsub_manager.stop_listener.assert_awaited_once()
    registrar.redis_client.aclose.assert_awaited_once()
