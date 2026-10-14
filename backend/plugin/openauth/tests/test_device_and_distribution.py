# ruff: noqa: ANN001, ANN201
import importlib

from unittest.mock import AsyncMock

import pytest

from fastapi import FastAPI
from fastapi.testclient import TestClient
from jose import jwt

from backend.common.exception import errors
from backend.core.conf import settings
from backend.plugin.openauth.api.v1.distribution import router
from backend.plugin.openauth.schema.device import CreateOpenAuthDeviceRevokeParam
from backend.plugin.openauth.service.authorization_service import _decode_openauth_token
from backend.plugin.openauth.service.device_service import openauth_device_service, ticket_key
from backend.plugin.openauth.tests.test_authorization_service import (
    Service,
    login,
    refresh_param,
)
from backend.plugin.openauth.tests.test_authorization_service import (
    env as authorization_env,
)

env = authorization_env
device_module = importlib.import_module('backend.plugin.openauth.service.device_service')


@pytest.mark.asyncio
async def test_device_revoke_only_after_owner_confirms(env, monkeypatch):
    monkeypatch.setattr(device_module, 'redis_client', env.redis)
    monkeypatch.setattr(device_module.openauth_client_service, 'get_by_client_id', AsyncMock(return_value=env.client))
    first, other = await login(env), await login(env)
    ticket = await openauth_device_service.create_ticket(None, token=first.access_token)
    assert CreateOpenAuthDeviceRevokeParam(ticket=ticket.ticket).ticket == ticket.ticket
    preview = await openauth_device_service.preview(None, user_id=100, ticket=ticket.ticket)
    assert preview.active and preview.application_name == env.client.name
    assert (await Service.check(None, token=first.access_token)).authorized
    with pytest.raises(errors.ForbiddenError):
        await openauth_device_service.revoke(user_id=200, ticket=ticket.ticket)
    assert ticket_key(ticket.ticket) in env.redis.store
    await openauth_device_service.revoke(user_id=100, ticket=ticket.ticket)
    with pytest.raises(errors.TokenError):
        await Service.check(None, token=first.access_token)
    with pytest.raises(errors.TokenError):
        await Service.refresh(None, obj=refresh_param(env, first.refresh_token))
    assert (await Service.check(None, token=other.access_token)).authorized
    assert env.grant.status == 'active'
    with pytest.raises(errors.NotFoundError):
        await openauth_device_service.revoke(user_id=100, ticket=ticket.ticket)


@pytest.mark.asyncio
async def test_signed_expired_access_can_only_logout_its_own_session(env):
    first, other = await login(env), await login(env)
    payload = _decode_openauth_token(first.access_token)
    expired = jwt.encode({**payload, 'exp': 1}, settings.TOKEN_SECRET_KEY, algorithm=settings.TOKEN_ALGORITHM)
    with pytest.raises(errors.TokenError):
        await Service.check(None, token=expired)
    await Service.logout(None, token=expired)
    await Service.logout(None, token=expired)  # 幂等退出
    with pytest.raises(errors.TokenError):
        await Service.refresh(None, obj=refresh_param(env, first.refresh_token))
    assert (await Service.check(None, token=other.access_token)).authorized
    with pytest.raises(errors.TokenError):
        await Service.logout(None, token=expired + 'bad-signature')


def test_distribution_serves_matching_package(monkeypatch, tmp_path):
    import hashlib
    import json

    module = importlib.import_module('backend.plugin.openauth.service.distribution_service')
    monkeypatch.setattr(module, 'ARTIFACT_DIR', tmp_path)
    package = b'fixture-zip-bytes'
    manifest = {'version': '0.2.0', 'package_path': 'skill-package', 'sha256': hashlib.sha256(package).hexdigest()}
    (tmp_path / 'skill-release.json').write_text(json.dumps(manifest), encoding='utf-8')
    (tmp_path / 'youanshang-skill.zip').write_bytes(package)
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as client:
        assert client.get('/skill-config').json()['data'] == manifest
        result = client.get('/skill-package')
        assert result.content == package
        assert result.headers['cache-control'] == 'no-store'
        assert client.get('/skill-package/../../state.json').status_code == 404
