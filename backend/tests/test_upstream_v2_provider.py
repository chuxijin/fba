import importlib

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from backend.app.admin.service.user_service import user_service
from backend.common.exception import errors


@pytest.mark.parametrize('state', ['hit', 'miss', 'unavailable'])
async def test_registered_jwt_provider_cache_and_user_validation(monkeypatch: pytest.MonkeyPatch, state: str) -> None:
    module = importlib.import_module('backend.app.admin.service.user_service')
    dto, row, session = object(), object(), object()
    cache = SimpleNamespace(get=AsyncMock(return_value=dto if state == 'hit' else None), set=AsyncMock())
    available = AsyncMock(return_value=row, side_effect=errors.AuthorizationError() if state == 'unavailable' else None)
    validate = Mock(return_value=dto)
    opened = []

    @asynccontextmanager
    async def create_session():
        opened.append(session)
        yield session

    monkeypatch.setattr(module, 'user_cache_manager', cache)
    monkeypatch.setattr(module, 'async_db_session', create_session)
    monkeypatch.setattr(user_service, 'get_available', available)
    monkeypatch.setattr(module, 'GetUserInfoWithRelationDetail', SimpleNamespace(model_validate=validate))
    if state == 'unavailable':
        with pytest.raises(errors.AuthorizationError):
            await user_service.get_jwt_user(user_id=7)
    else:
        assert await user_service.get_jwt_user(user_id=7) is dto
    cache.get.assert_awaited_once_with(7)
    if state == 'hit':
        available.assert_not_awaited()
        assert opened == []
    else:
        available.assert_awaited_once_with(db=session, pk=7)
        assert opened == [session]
    if state == 'miss':
        validate.assert_called_once_with(row)
        cache.set.assert_awaited_once_with(7, dto)
    else:
        validate.assert_not_called()
        cache.set.assert_not_awaited()
