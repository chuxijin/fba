#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from dataclasses import dataclass
from typing import Any

from backend.app.mydrive.service.drives.thunder.client import ThunderRequest


@dataclass(frozen=True, slots=True)
class ThunderProfile:
    """迅雷账户资料。"""

    external_account_id: str
    username: str | None
    avatar_url: str | None
    quota: int | None
    used: int | None
    vip_level: str
    credential: dict[str, str]


async def get_thunder_profile(credential: dict[str, Any], client: ThunderRequest | None = None) -> ThunderProfile:
    """
    获取迅雷账户资料。

    :param credential: 迅雷授权凭证
    :param client: 迅雷请求封装
    :return:
    """
    request_client = client or ThunderRequest(credential)
    try:
        about = await request_client.get_about()
        user = await request_client.get_user()
        quota = about.get('quota', {})
        return ThunderProfile(
            external_account_id=str(user.get('user_id') or user.get('sub') or ''),
            username=user.get('username') or user.get('nickname'),
            avatar_url=user.get('avatar') or user.get('avatar_url'),
            quota=_to_int(quota.get('limit')),
            used=_to_int(quota.get('usage')),
            vip_level=_vip_level(user),
            credential=request_client.refreshed_credential,
        )
    finally:
        if client is None:
            await request_client.aclose()


def _to_int(value: Any) -> int | None:
    """
    转换容量数值。

    :param value: 原始容量值
    :return:
    """
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _vip_level(user: dict[str, Any]) -> str:
    """
    映射迅雷会员等级。

    :param user: 迅雷账户信息
    :return:
    """
    if user.get('is_svip') or user.get('vip_type') in {'svip', 'super_vip'}:
        return 'super_vip'
    if user.get('is_vip') or user.get('vip_type'):
        return 'vip'
    return 'normal'
