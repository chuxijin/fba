#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from abc import ABC, abstractmethod

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.access.constants import SubscriptionSource
from backend.app.access.service.subscription_service import subscription_service
from backend.app.growth.service import experience_service
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
        撤销权益

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param reward_data: 权益数据
        :return:
        """
        log.warning(f'{self.__class__.__name__} 不支持撤销权益')
        return False


def _parse_positive_int(value: object) -> int | None:
    """
    解析正整数

    :param value: 原始值
    :return:
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value > 0:
        return value
    if isinstance(value, str) and value.strip().isdigit():
        parsed = int(value.strip())
        if parsed > 0:
            return parsed
    return None


class VipFulfiller(BaseRewardFulfiller):
    """会员订阅履约(基于 access.subscription)"""

    async def fulfill(self, *, db: AsyncSession, user_id: int, reward_data: dict) -> bool:
        """
        发放会员订阅(reward_data: {template_code, days?, source_key, ...})

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param reward_data: 权益数据
        :return:
        """
        template_code = str(reward_data.get('template_code') or '').strip()
        days = _parse_positive_int(reward_data.get('days'))
        source = str(reward_data.get('source') or 'reward').strip() or 'reward'
        source_key = str(reward_data.get('source_key') or '').strip()

        if not template_code:
            log.warning(f'会员发放失败: user_id={user_id}, reason=missing_template_code')
            return False
        if not source_key:
            log.warning(f'会员发放失败: user_id={user_id}, reason=missing_source_key')
            return False

        try:
            if days is None:
                await subscription_service.create_from_template(
                    db,
                    user_id=user_id,
                    template_code=template_code,
                    source=SubscriptionSource(source) if source in {s.value for s in SubscriptionSource} else SubscriptionSource.GIFT,
                    source_ref=source_key,
                )
            else:
                await subscription_service.extend_by_days(
                    db,
                    user_id=user_id,
                    template_code=template_code,
                    days=days,
                    source=SubscriptionSource(source) if source in {s.value for s in SubscriptionSource} else SubscriptionSource.GIFT,
                    source_ref=source_key,
                )
        except Exception as exc:
            log.warning(
                f'会员发放失败: user_id={user_id}, template={template_code}, error={exc!s}'
            )
            return False

        log.info(
            f'会员发放成功: user_id={user_id}, template={template_code}, '
            f'days={days}, source={source}, source_key={source_key}'
        )
        return True

    async def revoke(self, *, db: AsyncSession, user_id: int, reward_data: dict) -> bool:
        """
        撤销会员订阅

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param reward_data: 权益数据
        :return:
        """
        source = str(reward_data.get('source') or 'reward').strip() or 'reward'
        source_key = str(reward_data.get('source_key') or '').strip()
        reason = reward_data.get('reason') or '权益撤销'

        if not source_key:
            log.warning(f'会员撤销失败: user_id={user_id}, reason=missing_source_key')
            return False

        try:
            count = await subscription_service.revoke_by_source(
                db,
                user_id=user_id,
                source=source,
                source_ref=source_key,
                reason=reason,
            )
        except Exception as exc:
            log.warning(f'会员撤销失败: user_id={user_id}, source_key={source_key}, error={exc!s}')
            return False

        log.info(f'会员撤销成功: user_id={user_id}, source_key={source_key}, count={count}')
        return True


class PointsFulfiller(BaseRewardFulfiller):
    """经验值履约(基于 growth.experience)"""

    async def fulfill(self, *, db: AsyncSession, user_id: int, reward_data: dict) -> bool:
        """
        发放经验值

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param reward_data: 权益数据
        :return:
        """
        amount = _parse_positive_int(reward_data.get('amount'))
        source = str(reward_data.get('source') or 'reward').strip() or 'reward'
        source_key = str(reward_data.get('source_key') or '').strip()
        reason = reward_data.get('reason') or '经验奖励'

        if amount is None:
            log.warning(f'经验发放失败: user_id={user_id}, reason=invalid_amount')
            return False
        if not source_key:
            log.warning(f'经验发放失败: user_id={user_id}, reason=missing_source_key')
            return False

        family_code = await experience_service.resolve_reward_family(db, user_id=user_id)
        try:
            await experience_service.add_experience(
                db,
                user_id=user_id,
                family_code=str(family_code),
                exp_delta=amount,
                source=source,
                source_key=source_key,
                reason=reason,
            )
        except Exception as exc:
            log.warning(f'经验发放失败: user_id={user_id}, amount={amount}, error={exc!s}')
            return False

        log.info(
            f'经验发放成功: user_id={user_id}, amount={amount}, '
            f'family={family_code}, source={source}, source_key={source_key}'
        )
        return True

    async def revoke(self, *, db: AsyncSession, user_id: int, reward_data: dict) -> bool:
        """
        撤销经验值(从可用经验中扣回)

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param reward_data: 权益数据
        :return:
        """
        amount = _parse_positive_int(reward_data.get('amount'))
        source_key = str(reward_data.get('source_key') or '').strip()
        reason = reward_data.get('reason') or '权益撤销'

        if amount is None:
            log.warning(f'经验撤销失败: user_id={user_id}, reason=invalid_amount')
            return False
        if not source_key:
            log.warning(f'经验撤销失败: user_id={user_id}, reason=missing_source_key')
            return False

        family_code = await experience_service.resolve_reward_family(db, user_id=user_id)
        try:
            await experience_service.consume_experience(
                db,
                user_id=user_id,
                family_code=str(family_code),
                exp_delta=amount,
                source='reward_revoke',
                source_key=f'revoke:{source_key}',
                reason=reason,
            )
        except Exception as exc:
            log.warning(f'经验撤销失败: user_id={user_id}, amount={amount}, error={exc!s}')
            return False

        log.info(
            f'经验撤销成功: user_id={user_id}, amount={amount}, '
            f'family={family_code}, source_key={source_key}'
        )
        return True


class FeatureFulfiller(BaseRewardFulfiller):
    """功能权益履约(占位, 后续接 access.direct_grant)"""

    async def fulfill(self, *, db: AsyncSession, user_id: int, reward_data: dict) -> bool:
        """
        发放功能权益

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param reward_data: 权益数据
        :return:
        """
        feature_key = reward_data.get('feature_key', '')
        days = reward_data.get('days', 0)
        log.info(f'发放功能权益: user_id={user_id}, feature={feature_key}, days={days}')
        return True
