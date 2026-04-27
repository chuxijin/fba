#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.membership.crud.crud_experience_rule import membership_experience_rule_dao
from backend.app.membership.model.experience_rule import MembershipExperienceRule
from backend.app.membership.schema.experience_rule import (
    CreateMembershipExperienceRuleParam,
    UpdateMembershipExperienceRuleParam,
)
from backend.common.exception import errors


class MembershipExperienceRuleService:
    """会员经验规则服务"""

    @staticmethod
    async def get_select(
        *,
        event_code: str | None = None,
        family_code: str | None = None,
        status: int | None = None,
    ) -> Select:
        """
        获取经验规则分页查询语句

        :param event_code: 事件编码
        :param family_code: 等级族群
        :param status: 状态
        :return:
        """
        return await membership_experience_rule_dao.get_select(
            event_code=event_code,
            family_code=family_code,
            status=status,
        )

    @staticmethod
    async def get(db: AsyncSession, *, pk: int) -> MembershipExperienceRule:
        """
        获取经验规则详情

        :param db: 数据库会话
        :param pk: 规则 ID
        :return:
        """
        rule = await membership_experience_rule_dao.select_model(db, pk)
        if not rule:
            raise errors.NotFoundError(msg='经验规则不存在')
        return rule

    @staticmethod
    async def create(db: AsyncSession, *, obj: CreateMembershipExperienceRuleParam) -> None:
        """
        创建经验规则

        :param db: 数据库会话
        :param obj: 创建参数
        :return:
        """
        await membership_experience_rule_dao.create_model(db, obj)

    @staticmethod
    async def update(db: AsyncSession, *, pk: int, obj: UpdateMembershipExperienceRuleParam) -> int:
        """
        更新经验规则

        :param db: 数据库会话
        :param pk: 规则 ID
        :param obj: 更新参数
        :return:
        """
        rule = await membership_experience_rule_dao.select_model(db, pk)
        if not rule:
            raise errors.NotFoundError(msg='经验规则不存在')
        return await membership_experience_rule_dao.update_model(db, pk, obj)

    @staticmethod
    async def delete(db: AsyncSession, *, pk: int) -> int:
        """
        删除经验规则

        :param db: 数据库会话
        :param pk: 规则 ID
        :return:
        """
        rule = await membership_experience_rule_dao.select_model(db, pk)
        if not rule:
            raise errors.NotFoundError(msg='经验规则不存在')
        return await membership_experience_rule_dao.delete_model(db, pk)


membership_experience_rule_service: MembershipExperienceRuleService = MembershipExperienceRuleService()
