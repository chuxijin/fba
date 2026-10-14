# -*- coding: utf-8 -*-
"""微信登录默认昵称生成与占位昵称修复的单元测试（不依赖数据库与微信网络）。"""

import re

from types import SimpleNamespace
from typing import Any, Self

import pytest

from backend.plugin.oauth2.service import oauth2_service as oauth2_service_module
from backend.plugin.oauth2.service.oauth2_service import OAuth2Service
from backend.utils.nickname import DEFAULT_NICKNAME_SUFFIX_LENGTH, generate_default_nickname

AUTO_NICKNAME_RE = re.compile(rf'^微信用户_[a-z0-9]{{{DEFAULT_NICKNAME_SUFFIX_LENGTH}}}$')
OPENID = 'oTESTopenid0001ABCD'


class FakeWxResponse:
    """伪造 jscode2session 响应"""

    def json(self) -> dict[str, str]:
        return {'openid': OPENID, 'unionid': 'unionid-test'}


class FakeAsyncClient:
    """伪造 httpx.AsyncClient，只提供 jscode2session 所需的 get"""

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def get(self, url: str, params: dict[str, str] | None = None) -> FakeWxResponse:
        return FakeWxResponse()


def prepare_login(monkeypatch: pytest.MonkeyPatch, *, is_new_user: bool, stored_nickname: str | None) -> dict[str, Any]:
    """
    打桩微信登录流程，返回收集调用信息的容器

    新用户场景按真实实现模拟：入库昵称就是本次传入的昵称；
    老用户场景始终返回库里的昵称（登录流程不会覆盖已有昵称）。

    :param monkeypatch: pytest 打桩工具
    :param is_new_user: 是否为新注册用户
    :param stored_nickname: 老用户的库内昵称
    :return: 含 login_kwargs / updates 的容器
    """
    calls: dict[str, Any] = {'login_kwargs': None, 'updates': []}

    monkeypatch.setattr(oauth2_service_module.settings, 'WX_MINIAPP_APPID', 'appid-test', raising=False)
    monkeypatch.setattr(oauth2_service_module.settings, 'WX_MINIAPP_SECRET', 'secret-test', raising=False)
    monkeypatch.setattr(oauth2_service_module.httpx, 'AsyncClient', FakeAsyncClient)

    async def fake_login(**kwargs: Any) -> Any:  # noqa: RUF029
        calls['login_kwargs'] = kwargs
        nickname = kwargs['nickname'] if is_new_user else stored_nickname
        return SimpleNamespace(user=SimpleNamespace(id=7, nickname=nickname, avatar=None))

    async def fake_update_nickname(db: object, user_id: int, nickname: str) -> int:  # noqa: RUF029
        calls['updates'].append((user_id, nickname))
        return 1

    monkeypatch.setattr(OAuth2Service, 'login', fake_login)
    monkeypatch.setattr(oauth2_service_module.user_dao, 'update_nickname', fake_update_nickname)
    return calls


def test_generate_default_nickname_is_readable_and_unique() -> None:
    nickname = generate_default_nickname()
    assert AUTO_NICKNAME_RE.match(nickname), nickname
    assert generate_default_nickname(prefix='用户', suffix_length=10).startswith('用户_')
    # 随机后缀必须真的随机，否则又回到「分不清谁是谁」的老问题
    samples = {generate_default_nickname() for _ in range(200)}
    assert len(samples) > 190


def test_resolve_nickname_prefers_client_value_and_falls_back_to_default() -> None:
    assert OAuth2Service._resolve_nickname('桥水彼岸') == '桥水彼岸'
    assert OAuth2Service._resolve_nickname('  桥水彼岸  ') == '桥水彼岸'
    for empty in (None, '', '   '):
        assert AUTO_NICKNAME_RE.match(OAuth2Service._resolve_nickname(empty))


async def test_wechat_miniapp_login_stores_generated_nickname_for_new_user(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = prepare_login(monkeypatch, is_new_user=True, stored_nickname=None)

    token = await OAuth2Service.wechat_miniapp_login(
        db=None, response=None, background_tasks=None, code='js-code',
    )

    nickname = calls['login_kwargs']['nickname']
    assert AUTO_NICKNAME_RE.match(nickname), nickname
    # 用户名仍是 wx_ + openid 后缀：昵称与用户名各司其职，不能互相顶替
    assert calls['login_kwargs']['username'] == f'wx_{OPENID[-8:]}'
    assert token.user.nickname == nickname
    # 新用户入库就是默认昵称，不需要额外的修复写库
    assert calls['updates'] == []


async def test_wechat_miniapp_login_uses_client_provided_nickname(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = prepare_login(monkeypatch, is_new_user=True, stored_nickname=None)

    await OAuth2Service.wechat_miniapp_login(
        db=None, response=None, background_tasks=None, code='js-code', nickname='桥水彼岸',
    )

    assert calls['login_kwargs']['nickname'] == '桥水彼岸'


async def test_wechat_miniapp_login_repairs_legacy_placeholder_nickname(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = prepare_login(monkeypatch, is_new_user=False, stored_nickname='微信用户')

    token = await OAuth2Service.wechat_miniapp_login(
        db=None, response=None, background_tasks=None, code='js-code',
    )

    assert len(calls['updates']) == 1
    user_id, repaired = calls['updates'][0]
    assert user_id == 7
    assert AUTO_NICKNAME_RE.match(repaired), repaired
    # 返回给前端的资料同步成修复后的昵称
    assert token.user.nickname == repaired


async def test_wechat_miniapp_login_keeps_real_nickname(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = prepare_login(monkeypatch, is_new_user=False, stored_nickname='桥水彼岸')

    token = await OAuth2Service.wechat_miniapp_login(
        db=None, response=None, background_tasks=None, code='js-code',
    )

    assert calls['updates'] == []
    assert token.user.nickname == '桥水彼岸'
