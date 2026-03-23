#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from abc import ABC, abstractmethod

from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.log import log


class BaseRewardFulfiller(ABC):
    """权益履约基类"""

    @abstractmethod
    async def fulfill(self, *, db: AsyncSession, user_id: int, reward_data: dict) -> bool:
        """
        发放权益

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param reward_data: 权益数据
        :return:
        """

    async def revoke(self, *, db: AsyncSession, user_id: int, reward_data: dict) -> bool:
        """
        撤销权益（默认不支持，子类按需覆写）

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param reward_data: 权益数据
        :return:
        """
        log.warning(f'{self.__class__.__name__} 不支持撤销权益')
        return False


class VipFulfiller(BaseRewardFulfiller):
    """VIP 会员权益履约"""

    async def fulfill(self, *, db: AsyncSession, user_id: int, reward_data: dict) -> bool:
        """
        发放 VIP 会员权益

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param reward_data: 权益数据，如 {"level": 1, "days": 30}
        :return:
        """
        # TODO: 写入 user_entitlement 表（会员系统建表后补充）
        level = reward_data.get('level', 1)
        days = reward_data.get('days', 30)
        log.info(f'发放 VIP 权益: user_id={user_id}, level={level}, days={days}')
        return True


class PointsFulfiller(BaseRewardFulfiller):
    """积分权益履约"""

    async def fulfill(self, *, db: AsyncSession, user_id: int, reward_data: dict) -> bool:
        """
        发放积分权益

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param reward_data: 权益数据，如 {"amount": 100}
        :return:
        """
        # TODO: 更新用户积分（积分系统实现后补充）
        amount = reward_data.get('amount', 0)
        log.info(f'发放积分权益: user_id={user_id}, amount={amount}')
        return True


class FeatureFulfiller(BaseRewardFulfiller):
    """功能解锁权益履约"""

    async def fulfill(self, *, db: AsyncSession, user_id: int, reward_data: dict) -> bool:
        """
        发放功能解锁权益

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param reward_data: 权益数据，如 {"feature_key": "scene_pack_01", "days": 90}
        :return:
        """
        # TODO: 写入 user_entitlement 表（会员系统建表后补充）
        feature_key = reward_data.get('feature_key', '')
        days = reward_data.get('days', 0)
        log.info(f'发放功能解锁权益: user_id={user_id}, feature={feature_key}, days={days}')
        return True
