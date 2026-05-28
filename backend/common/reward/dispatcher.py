#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.log import log
from backend.common.reward.fulfiller import (
    BaseRewardFulfiller,
    ChaojiCourseFulfiller,
    FeatureFulfiller,
    PointsFulfiller,
    VipFulfiller,
)

# 权益类型 → 履约策略的注册表
# reward_type 命名约定:
# 1. 使用 snake_case, 描述“发放什么/由谁发放”, 不描述审核条件
# 2. 新增第三方履约时, 先在 fulfiller.py 新增 XxxFulfiller, 再在这里注册
# 3. quest_task.reward_type 必须与这里的 key 一致, quest_task.reward_data 放该履约器需要的配置
# 示例:
# - chaoji_course: 调超级考研代理后台开通课程
# - baidu_netdisk_code: 发放网盘兑换码
# - external_coupon: 调第三方接口发券
_FULFILLER_REGISTRY: dict[str, BaseRewardFulfiller] = {
    'vip': VipFulfiller(),
    'points': PointsFulfiller(),
    'feature': FeatureFulfiller(),
    'chaoji_course': ChaojiCourseFulfiller(),
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
