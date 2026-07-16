#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from dataclasses import dataclass
from hashlib import sha256
from typing import Any

from backend.app.mydrive.service.drives.quark.client import QuarkRequest, QuarkRequestError
from backend.common.log import log


@dataclass(frozen=True, slots=True)
class QuarkProfile:
    """夸克账户资料。"""

    external_account_id: str
    username: str | None
    avatar_url: str | None
    quota: int | None
    used: int | None
    vip_level: str | None


async def get_quark_profile(cookie: str, client: QuarkRequest | None = None) -> QuarkProfile:
    """
    获取夸克账户资料。

    :param cookie: 夸克网盘 Cookie
    :param client: 夸克请求封装
    :return:
    """
    request_client = client or QuarkRequest(cookie)
    member_response = await request_client.get_member_info()
    account_response = await _get_account_safely(request_client)
    account_data = account_response.get('data', {})
    member_data = member_response.get('data', {})
    external_account_id = _get_external_account_id(account_data, member_data, cookie)
    return QuarkProfile(
        external_account_id=external_account_id,
        username=account_data.get('nickname') or account_data.get('user_name') or external_account_id,
        avatar_url=account_data.get('avatarUri') or account_data.get('avatar'),
        quota=_get_int(member_data.get('total_capacity')),
        used=_get_int(member_data.get('use_capacity')),
        vip_level=_get_vip_level(member_data),
    )


async def _get_account_safely(client: QuarkRequest) -> dict[str, Any]:
    """
    获取夸克账户信息，失败时降级为空账户。

    :param client: 夸克请求封装
    :return:
    """
    try:
        return await client.get_account_info()
    except QuarkRequestError as exc:
        log.warning('夸克账户信息获取失败，账户资料同步降级处理: {}', exc)
        return {}


def _get_external_account_id(account_data: dict[str, Any], member_data: dict[str, Any], cookie: str) -> str:
    """
    获取夸克账户唯一标识。

    :param account_data: 账户资料
    :param member_data: 会员资料
    :param cookie: Cookie 凭证
    :return:
    """
    for key in ('mobilekps', 'user_id', 'ucid', 'uid', 'account_id'):
        value = account_data.get(key) or member_data.get(key)
        if value:
            return str(value)
    return f'cookie:{sha256(cookie.encode()).hexdigest()[:24]}'


def _get_int(value: Any) -> int | None:
    """
    转换容量数值。

    :param value: 原始容量值
    :return:
    """
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _get_vip_level(member_data: dict[str, Any]) -> str | None:
    """
    映射夸克会员等级。

    :param member_data: 夸克会员信息
    :return:
    """
    member_type = str(member_data.get('member_type') or '').upper()
    if member_type == 'SUPER_VIP':
        return 'super_vip'
    if member_data.get('is_vip'):
        return 'vip'
    return 'normal'
