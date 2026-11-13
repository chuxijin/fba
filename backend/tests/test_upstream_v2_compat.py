import asyncio

from unittest.mock import AsyncMock

import pytest

from fastapi.routing import iter_route_contexts

from backend.app.admin.schema.role import UpdateRoleMenuParam, UpdateRoleScopeParam
from backend.app.admin.schema.user import AddUserParam, UpdateUserParam
from backend.core.conf import settings
from backend.plugin import core
from backend.plugin.validator import validate_plugin_config, validate_plugin_files
from backend.utils.async_helper import run_await


@pytest.mark.parametrize('name', core.get_plugins())
async def test_installed_plugin_manifest_and_postgresql_scripts(name: str) -> None:
    config = await core.load_plugin_config(name)
    validate_plugin_config(name, config)
    validate_plugin_files(name)


@pytest.mark.parametrize('name', ['role_ids', 'roles'])
def test_user_relation_field_accepts_v2_and_existing_clients(name: str) -> None:
    fields = {name: [1], 'username': 'user', 'password': 'secret', 'dept_id': 1, 'nickname': 'User'}
    for schema in [AddUserParam, UpdateUserParam]:
        obj = schema.model_validate(fields)
        assert obj.role_ids == [1]
        assert 'roles' not in obj.model_dump()


@pytest.mark.parametrize(
    ['schema', 'current', 'legacy'],
    [[UpdateRoleMenuParam, 'menu_ids', 'menus'], [UpdateRoleScopeParam, 'scope_ids', 'scopes']],
)
def test_role_relation_field_compatibility(schema: type, current: str, legacy: str) -> None:
    for key in [current, legacy]:
        assert schema.model_validate({key: [1]}).model_dump() == {current: [1]}


def test_async_bridge_keeps_one_live_loop_and_rejects_reentrant_wait() -> None:
    async def loop_identity() -> int:
        return id(asyncio.get_running_loop())

    bridge = run_await(loop_identity)
    assert bridge() == bridge()

    async def reentrant() -> None:
        with pytest.raises(RuntimeError, match='自身事件循环线程'):
            bridge()

    run_await(reentrant)()


def test_register_application_routes_without_lifespan_or_external_services(monkeypatch: pytest.MonkeyPatch) -> None:
    class OfflineRedis:
        init = AsyncMock()
        aclose = AsyncMock()
        delete_by_prefix = AsyncMock()
        delete = AsyncMock()
        mset = AsyncMock()

        async def mget_batched(self, keys: list[str]) -> list[None]:
            return [None] * len(keys)

    monkeypatch.setattr(core, 'RedisCli', OfflineRedis)
    monkeypatch.setattr(settings, 'GRAFANA_METRICS_ENABLE', False)
    from backend.core.registrar import register_app

    app = register_app()
    paths = {route.path for route in iter_route_contexts(app.routes)}
    for path in ['/api/v1/auth/refresh', '/api/v1/auth/extension-session', '/api/v1/sys/configs/frontend']:
        assert path in paths
    assert not any('code-gen' in path for path in paths)
