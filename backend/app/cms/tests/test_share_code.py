from unittest.mock import AsyncMock

import httpx
import pytest

from backend.common.exception import errors
from backend.utils.wechat_code import create_miniapp_code


def mock_wechat(
    monkeypatch: pytest.MonkeyPatch, *, content_type: str = 'image/png', cached: str | bytes | None = None
) -> tuple[AsyncMock, AsyncMock, AsyncMock, AsyncMock]:
    get = AsyncMock(return_value=cached)
    save = AsyncMock()
    token = AsyncMock(return_value='server-token')
    client = AsyncMock()
    client.post.return_value = httpx.Response(200, headers={'content-type': content_type}, content=b'png-test')
    manager = AsyncMock()
    manager.__aenter__.return_value = client
    monkeypatch.setattr('backend.utils.wechat_code.redis_client.get', get)
    monkeypatch.setattr('backend.utils.wechat_code.redis_client.set', save)
    monkeypatch.setattr('backend.utils.wechat_code.WechatScanService.get_access_token', token)
    monkeypatch.setattr('backend.utils.wechat_code.httpx.AsyncClient', lambda **_: manager)
    return get, save, token, client


async def test_code_payload_uses_trusted_route_scene_and_bounded_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    _get, save, token, client = mock_wechat(monkeypatch)
    result = await create_miniapp_code(page='pages/practice/index', scene='iv_ABCD1234', ttl=10)
    assert result.startswith('data:image/png;base64,')
    payload = client.post.call_args.kwargs['json']
    assert payload['scene'] == 'iv_ABCD1234'
    assert payload['page'] == 'pages/practice/index'
    assert payload['env_version'] in {'trial', 'release'}
    assert 'server-token' not in result
    assert save.call_args.kwargs['ex'] == 10
    token.assert_awaited_once()


async def test_cached_code_never_calls_wechat(monkeypatch: pytest.MonkeyPatch) -> None:
    _get, save, token, client = mock_wechat(monkeypatch, cached=b'data:image/png;base64,cG5n')
    assert await create_miniapp_code(page='pages/practice/index', scene='iv_ABCD1234') == 'data:image/png;base64,cG5n'
    token.assert_not_awaited()
    client.post.assert_not_awaited()
    save.assert_not_awaited()


async def test_wechat_json_error_is_not_saved_as_an_image(monkeypatch: pytest.MonkeyPatch) -> None:
    _get, save, _token, _client = mock_wechat(monkeypatch, content_type='application/json')
    with pytest.raises(errors.GatewayError):
        await create_miniapp_code(page='pages/practice/index', scene='iv_ABCD1234')
    save.assert_not_awaited()
