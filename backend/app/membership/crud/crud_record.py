#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.membership.model.record import MembershipRecord


class CRUDMembershipRecord(CRUDPlus[MembershipRecord]):
    """会员流水数据库操作类"""

    async def get_select(
        self,
        *,
        user_id: int | None = None,
        family_code: str | None = None,
        plan_id: int | None = None,
        tier_id: int | None = None,
        source: str | None = None,
        source_key: str | None = None,
    ) -> Select:
        """
        获取流水分页查询语句

        :param user_id: 用户 ID
        :param family_code: 族群编码
        :param plan_id: 计划 ID
        :param tier_id: 等级 ID
        :param source: 来源
        :param source_key: 来源幂等键
        :return:
        """
        filters = {}
        if user_id is not None:
            filters['user_id__eq'] = user_id
        if family_code is not None:
            filters['family_code__eq'] = family_code
        if plan_id is not None:
            filters['plan_id__eq'] = plan_id
        if tier_id is not None:
            filters['tier_id__eq'] = tier_id
        if source is not None:
            filters['source__eq'] = source
        if source_key is not None:
            filters['source_key__eq'] = source_key
        return await self.select_order('created_time', 'desc', **filters)

    async def get_by_idempotency(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        family_code: str,
        source: str,
        source_key: str,
        op_type: str,
    ) -> MembershipRecord | None:
        """
        按幂等键查询流水

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param family_code: 族群编码
        :param source: 来源
        :param source_key: 来源幂等键
        :param op_type: 操作类型
        :return:
        """
        return await self.select_model_by_column(
            db,
            user_id__eq=user_id,
            family_code__eq=family_code,
            source__eq=source,
            source_key__eq=source_key,
            op_type__eq=op_type,
        )


membership_record_dao: CRUDMembershipRecord = CRUDMembershipRecord(MembershipRecord)
