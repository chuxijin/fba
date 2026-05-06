#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.membership.crud.crud_usage_counter import membership_usage_counter_dao
from backend.app.membership.model.usage_counter import MembershipUsageCounter
from backend.app.membership.schema.usage_counter import (
    CreateMembershipUsageCounterParam,
    UpdateMembershipUsageCounterParam,
)
from backend.common.exception import errors
from backend.utils.timezone import timezone


class MembershipUsageCounterService:
    """会员权益用量计数服务"""

    @staticmethod
    def build_cycle_key(cycle_type: str, now: datetime | None = None) -> str:
        """
        生成周期键

        :param cycle_type: 周期类型
        :param now: 当前时间
        :return:
        """
        current_time = now or timezone.now()
        if cycle_type == 'daily':
            return current_time.strftime('%Y-%m-%d')
        if cycle_type == 'monthly':
            return current_time.strftime('%Y-%m')
        if cycle_type == 'yearly':
            return current_time.strftime('%Y')
        if cycle_type == 'lifetime':
            return 'lifetime'

        raise errors.RequestError(msg=f'不支持的额度周期: {cycle_type}')

    @staticmethod
    async def get_select(
        *,
        user_id: int | None = None,
        entitlement_code: str | None = None,
        scope_key: str | None = None,
        cycle_type: str | None = None,
        cycle_key: str | None = None,
    ) -> Select:
        """
        获取用量计数分页查询语句

        :param user_id: 用户 ID
        :param entitlement_code: 权益编码
        :param scope_key: 业务范围键
        :param cycle_type: 周期类型
        :param cycle_key: 周期键
        :return:
        """
        return await membership_usage_counter_dao.get_select(
            user_id=user_id,
            entitlement_code=entitlement_code,
            scope_key=scope_key,
            cycle_type=cycle_type,
            cycle_key=cycle_key,
        )

    @staticmethod
    async def get(db: AsyncSession, *, pk: int) -> MembershipUsageCounter:
        """
        获取用量计数详情

        :param db: 数据库会话
        :param pk: 计数 ID
        :return:
        """
        counter = await membership_usage_counter_dao.select_model(db, pk)
        if not counter:
            raise errors.NotFoundError(msg='权益用量计数不存在')
        return counter

    @staticmethod
    async def create(db: AsyncSession, *, obj: CreateMembershipUsageCounterParam) -> None:
        """
        创建用量计数

        :param db: 数据库会话
        :param obj: 创建参数
        :return:
        """
        existing = await membership_usage_counter_dao.get_by_scope(
            db,
            user_id=obj.user_id,
            entitlement_code=obj.entitlement_code,
            scope_key=obj.scope_key,
            cycle_type=obj.cycle_type,
            cycle_key=obj.cycle_key,
        )
        if existing:
            raise errors.ConflictError(msg='权益用量计数已存在')
        await membership_usage_counter_dao.create_model(db, obj)

    @staticmethod
    async def update(db: AsyncSession, *, pk: int, obj: UpdateMembershipUsageCounterParam) -> int:
        """
        更新用量计数

        :param db: 数据库会话
        :param pk: 计数 ID
        :param obj: 更新参数
        :return:
        """
        counter = await membership_usage_counter_dao.select_model(db, pk)
        if not counter:
            raise errors.NotFoundError(msg='权益用量计数不存在')
        return await membership_usage_counter_dao.update_model(db, pk, obj)

    @staticmethod
    async def consume(
        db: AsyncSession,
        *,
        user_id: int,
        entitlement_code: str,
        amount: int = 1,
        scope_key: str = 'default',
        cycle_type: str = 'monthly',
        cycle_key: str | None = None,
        limit_value: int | None = None,
        source: str | None = None,
        source_key: str | None = None,
        remark: str | None = None,
    ) -> MembershipUsageCounter:
        """
        消耗权益额度

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param entitlement_code: 权益编码
        :param amount: 消耗数量
        :param scope_key: 业务范围键
        :param cycle_type: 周期类型
        :param cycle_key: 周期键
        :param limit_value: 周期额度上限
        :param source: 来源
        :param source_key: 来源业务键
        :param remark: 备注
        :return:
        """
        if amount <= 0:
            raise errors.RequestError(msg='消耗数量必须大于 0')

        normalized_cycle_key = cycle_key or MembershipUsageCounterService.build_cycle_key(cycle_type)
        counter = await membership_usage_counter_dao.get_by_scope(
            db,
            user_id=user_id,
            entitlement_code=entitlement_code,
            scope_key=scope_key,
            cycle_type=cycle_type,
            cycle_key=normalized_cycle_key,
            for_update=True,
        )
        if counter is None:
            counter = MembershipUsageCounter(
                user_id=user_id,
                entitlement_code=entitlement_code,
                scope_key=scope_key,
                cycle_type=cycle_type,
                cycle_key=normalized_cycle_key,
                limit_value=limit_value,
                remark=remark,
            )
            db.add(counter)

        if limit_value is not None:
            counter.limit_value = limit_value

        next_used_value = counter.used_value + amount
        occupied_value = next_used_value + counter.reserved_value
        if counter.limit_value is not None and occupied_value > counter.limit_value:
            raise errors.ForbiddenError(msg='当前权益额度不足')

        counter.used_value = next_used_value
        counter.last_used_time = timezone.now()
        counter.last_source = source
        counter.last_source_key = source_key
        counter.remark = remark
        await db.flush()
        return counter


membership_usage_counter_service: MembershipUsageCounterService = MembershipUsageCounterService()
