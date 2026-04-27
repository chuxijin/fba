#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from abc import ABC, abstractmethod

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.membership.service.experience_service import membership_experience_service
from backend.app.membership.service.membership_service import membership_service
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


class VipFulfiller(BaseRewardFulfiller):
    """会员履约"""

    @staticmethod
    def _parse_positive_int(value: object, default: int | None = None) -> int | None:
        """
        解析正整数参数

        :param value: 原始值
        :param default: 默认值
        :return:
        """
        if value is None:
            return default

        if isinstance(value, bool):
            return default

        if isinstance(value, int):
            if value > 0:
                return value
            return default

        if isinstance(value, str):
            text = value.strip()
            if text.isdigit():
                parsed = int(text)
                if parsed > 0:
                    return parsed

        return default

    async def fulfill(self, *, db: AsyncSession, user_id: int, reward_data: dict) -> bool:
        """
        发放会员权益

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param reward_data: 权益数据
        :return:
        """
        plan_id = self._parse_positive_int(reward_data.get('plan_id'))
        days = self._parse_positive_int(reward_data.get('days'))
        source = str(reward_data.get('source') or 'reward').strip() or 'reward'
        source_key = str(reward_data.get('source_key') or '').strip()
        source_detail = reward_data.get('source_detail')
        remark = reward_data.get('remark')

        if plan_id is None:
            log.warning(f'会员权益发放失败: user_id={user_id}, reason=missing_plan_id')
            return False

        if not source_key:
            log.warning(f'会员权益发放失败: user_id={user_id}, reason=missing_source_key')
            return False

        try:
            if days is None:
                await membership_service.grant_by_plan(
                    db,
                    user_id=user_id,
                    plan_id=plan_id,
                    source=source,
                    source_key=source_key,
                    op_type='reward',
                    days=None,
                    source_detail=source_detail,
                    remark=remark,
                )
            else:
                await membership_service.add_days(
                    db,
                    user_id=user_id,
                    plan_id=plan_id,
                    days=days,
                    source=source,
                    source_key=source_key,
                    source_detail=source_detail,
                    remark=remark,
                )
        except Exception as exc:
            log.warning(f'会员权益发放失败: user_id={user_id}, plan_id={plan_id}, error={exc!s}')
            return False

        log.info(
            f'会员权益发放成功: user_id={user_id}, plan_id={plan_id}, '
            f'days={days}, source={source}, source_key={source_key}'
        )
        return True


class PointsFulfiller(BaseRewardFulfiller):
    """积分履约"""

    @staticmethod
    def _parse_positive_int(value: object) -> int | None:
        """
        解析正整数参数

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

    async def fulfill(self, *, db: AsyncSession, user_id: int, reward_data: dict) -> bool:
        """
        发放积分权益

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param reward_data: 权益数据
        :return:
        """
        amount = self._parse_positive_int(reward_data.get('amount'))
        family_code = reward_data.get('family_code')
        source = str(reward_data.get('source') or 'reward').strip() or 'reward'
        source_key = str(reward_data.get('source_key') or '').strip()
        remark = reward_data.get('remark')

        if amount is None:
            log.warning(f'积分权益发放失败: user_id={user_id}, reason=invalid_amount')
            return False
        if not source_key:
            log.warning(f'积分权益发放失败: user_id={user_id}, reason=missing_source_key')
            return False

        if not family_code:
            family_code = await membership_experience_service.resolve_reward_family(db, user_id=user_id)

        try:
            await membership_experience_service.add_experience(
                db,
                user_id=user_id,
                family_code=str(family_code),
                exp_delta=amount,
                source=source,
                source_key=source_key,
                remark=remark or '积分奖励',
            )
        except Exception as exc:
            log.warning(f'积分权益发放失败: user_id={user_id}, amount={amount}, error={exc!s}')
            return False

        log.info(
            f'积分权益发放成功: user_id={user_id}, amount={amount}, '
            f'family={family_code}, source={source}, source_key={source_key}'
        )
        return True


class FeatureFulfiller(BaseRewardFulfiller):
    """功能权益履约"""

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
