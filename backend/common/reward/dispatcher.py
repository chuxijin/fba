#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.log import log
from backend.common.reward.fulfiller import BaseRewardFulfiller, FeatureFulfiller, PointsFulfiller, VipFulfiller

# 权益类型 → 履约策略的注册表
_FULFILLER_REGISTRY: dict[str, BaseRewardFulfiller] = {
    'vip': VipFulfiller(),
    'points': PointsFulfiller(),
    'feature': FeatureFulfiller(),
}


def register_fulfiller(reward_type: str, fulfiller: BaseRewardFulfiller) -> None:
    """
    注册自定义权益履约策略

    :param reward_type: 权益类型
    :param fulfiller: 履约策略实例
    :return:
    """
    _FULFILLER_REGISTRY[reward_type] = fulfiller


async def dispatch_reward(*, db: AsyncSession, user_id: int, reward_type: str, reward_data: dict) -> bool:
    """
    分发权益（统一入口）

    :param db: 数据库会话
    :param user_id: 用户 ID
    :param reward_type: 权益类型
    :param reward_data: 权益数据
    :return:
    """
    fulfiller = _FULFILLER_REGISTRY.get(reward_type)
    if not fulfiller:
        log.warning(f'未注册的权益类型: {reward_type}')
        return False

    return await fulfiller.fulfill(db=db, user_id=user_id, reward_data=reward_data)


async def revoke_reward(*, db: AsyncSession, user_id: int, reward_type: str, reward_data: dict) -> bool:
    """
    撤销权益（统一入口）

    :param db: 数据库会话
    :param user_id: 用户 ID
    :param reward_type: 权益类型
    :param reward_data: 原始发放时使用的权益数据(必须包含 source_key)
    :return:
    """
    fulfiller = _FULFILLER_REGISTRY.get(reward_type)
    if not fulfiller:
        log.warning(f'未注册的权益类型: {reward_type}')
        return False

    return await fulfiller.revoke(db=db, user_id=user_id, reward_data=reward_data)
