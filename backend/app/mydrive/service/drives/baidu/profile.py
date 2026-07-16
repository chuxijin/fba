#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from dataclasses import dataclass
from typing import Any

from backend.app.mydrive.service.drives.baidu.client import BaiduRequest, BaiduRequestError
from backend.common.log import log


@dataclass(frozen=True, slots=True)
class BaiduProfile:
    """百度账户资料。"""

    external_account_id: str
    username: str | None
    avatar_url: str | None
    quota: int | None
    used: int | None
    vip_level: str


async def get_baidu_profile(cookie: str, client: BaiduRequest | None = None) -> BaiduProfile:
    """
    获取百度账户资料。

    :param cookie: 百度网盘 Cookie
    :param client: 百度请求封装
    :return:
    """
    request_client = client or BaiduRequest(cookie)
    try:
        user_response = await request_client.get_user_info()
        quota_response = await _get_quota_safely(request_client)
    finally:
        if client is None:
            await request_client.aclose()

    user_info = user_response.get('user_info', {})
    return BaiduProfile(
        external_account_id=str(user_info.get('uk') or ''),
        username=user_info.get('username'),
        avatar_url=user_info.get('photo'),
        quota=_get_int(quota_response.get('total') or quota_response.get('quota')),
        used=_get_int(quota_response.get('used')),
        vip_level=_get_vip_level(user_info),
    )


async def _get_quota_safely(client: BaiduRequest) -> dict[str, Any]:
    """
    获取百度容量，失败时降级为空容量。

    :param client: 百度请求封装
    :return:
    """
    try:
        return await client.get_quota()
    except BaiduRequestError as exc:
        log.warning('百度容量信息获取失败，账户资料同步降级处理: {}', exc)
        return {}


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


def _get_vip_level(user_info: dict[str, Any]) -> str:
    """
    映射百度会员等级。

    :param user_info: 百度账户信息
    :return:
    """
    if user_info.get('is_svip'):
        return 'super_vip'
    if user_info.get('is_vip'):
        return 'vip'
    return 'normal'
