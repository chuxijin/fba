from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from starlette.requests import Request

from backend.common.exception import errors
from backend.plugin.render_book.service import public_auth_service


def request(authorization: str | None = None) -> Request:
    headers = [] if authorization is None else [(b'authorization', authorization.encode())]
    return Request({'type': 'http', 'headers': headers})


@pytest.mark.asyncio
async def test_guest_without_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    authenticate = AsyncMock()
    monkeypatch.setattr(public_auth_service, 'jwt_authentication', authenticate)
    assert await public_auth_service.get_public_user(request=request()) is None
    authenticate.assert_not_awaited()


@pytest.mark.asyncio
async def test_uses_full_session_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    user = SimpleNamespace(id=7)
    authenticate = AsyncMock(return_value=user)
    monkeypatch.setattr(public_auth_service, 'jwt_authentication', authenticate)
    assert await public_auth_service.get_public_user(request=request('Bearer credential')) is user
    authenticate.assert_awaited_once_with('credential')


@pytest.mark.asyncio
@pytest.mark.parametrize('header', ['Basic invalid', 'Bearer ', 'garbage'])
async def test_invalid_credentials_do_not_fall_back_to_guest(header: str) -> None:
    with pytest.raises(errors.TokenError):
        await public_auth_service.get_public_user(request=request(header))


@pytest.mark.asyncio
async def test_revoked_session_does_not_fall_back_to_guest(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        public_auth_service, 'jwt_authentication', AsyncMock(side_effect=errors.TokenError(msg='已撤销'))
    )
    with pytest.raises(errors.TokenError, match='已撤销'):
        await public_auth_service.get_public_user(request=request('Bearer revoked'))
