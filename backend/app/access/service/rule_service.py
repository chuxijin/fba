#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import Select
from sqlalchemy.dialects.postgresql.ranges import Range
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.access.constants import CommonStatus, GrantMode
from backend.app.access.crud.crud_entitlement import entitlement_dao
from backend.app.access.crud.crud_rule import resource_rule_dao
from backend.app.access.model.rule import ResourceRule
from backend.app.access.schema.rule import (
    BulkUpsertRulesParam,
    CreateRuleParam,
    UpdateRuleParam,
)
from backend.common.exception import errors


class ResourceRuleService:
    """资源规则服务"""

    @staticmethod
    async def get(db: AsyncSession, *, pk: int) -> ResourceRule:
        """
        获取规则详情

        :param db: 数据库会话
        :param pk: 规则 ID
        :return:
        """
        rule = await resource_rule_dao.select_model(db, pk)
        if not rule:
            raise errors.NotFoundError(msg='资源规则不存在')
        return rule

    @staticmethod
    async def get_select(
        *,
        resource_type: str | None = None,
        resource_id: int | None = None,
        entitlement_code: str | None = None,
        grant_mode: GrantMode | None = None,
        status: CommonStatus | None = None,
    ) -> Select:
        """
        获取分页查询语句

        :param resource_type: 资源类型
        :param resource_id: 资源 ID
        :param entitlement_code: 权益编码
        :param grant_mode: 授权模式
        :param status: 状态
        :return:
        """
        return await resource_rule_dao.get_select(
            resource_type=resource_type,
            resource_id=resource_id,
            entitlement_code=entitlement_code,
            grant_mode=grant_mode,
            status=status,
        )

    @staticmethod
    async def create(db: AsyncSession, *, obj: CreateRuleParam) -> None:
        """
        创建资源规则

        :param db: 数据库会话
        :param obj: 创建参数
        :return:
        """
        await ResourceRuleService._validate_entitlement(db, obj.entitlement_code)
        rule = ResourceRule(
            resource_type=obj.resource_type,
            resource_id=obj.resource_id,
            entitlement_code=obj.entitlement_code,
            grant_mode=obj.grant_mode,
            priority=obj.priority,
            trial_policy=obj.trial_policy.model_dump(exclude_none=True) if obj.trial_policy else None,
            valid_period=obj.valid_period.to_range() if obj.valid_period else None,
            audience_filter=obj.audience_filter,
            inherit_to_children=obj.inherit_to_children,
            metadata_=obj.metadata,
        )
        db.add(rule)

    @staticmethod
    async def update(db: AsyncSession, *, pk: int, obj: UpdateRuleParam) -> int:
        """
        更新规则

        :param db: 数据库会话
        :param pk: 规则 ID
        :param obj: 更新参数
        :return:
        """
        await ResourceRuleService.get(db, pk=pk)
        data = obj.model_dump(exclude_unset=True, exclude={'valid_period', 'trial_policy'})
        if obj.valid_period is not None:
            data['valid_period'] = obj.valid_period.to_range()
        if 'trial_policy' in obj.model_fields_set:
            data['trial_policy'] = obj.trial_policy.model_dump(exclude_none=True) if obj.trial_policy else None
        return await resource_rule_dao.update_model(db, pk, data)

    @staticmethod
    async def delete(db: AsyncSession, *, pk: int) -> int:
        """
        删除规则

        :param db: 数据库会话
        :param pk: 规则 ID
        :return:
        """
        return await resource_rule_dao.delete_model(db, pk)

    @staticmethod
    async def bulk_upsert(db: AsyncSession, *, obj: BulkUpsertRulesParam) -> int:
        """
        批量回填规则(对相同资源 + 权益 + 模式幂等)

        :param db: 数据库会话
        :param obj: 批量参数
        :return:
        """
        await ResourceRuleService._validate_entitlement(db, obj.entitlement_code)
        period: Range | None = obj.valid_period.to_range() if obj.valid_period else None
        trial_policy = obj.trial_policy.model_dump(exclude_none=True) if obj.trial_policy else None

        created = 0
        for resource_id in obj.resource_ids:
            rule = ResourceRule(
                resource_type=obj.resource_type,
                resource_id=resource_id,
                entitlement_code=obj.entitlement_code,
                grant_mode=obj.grant_mode,
                priority=obj.priority,
                trial_policy=trial_policy,
                valid_period=period,
            )
            db.add(rule)
            created += 1
        return created

    @staticmethod
    async def _validate_entitlement(db: AsyncSession, code: str) -> None:
        """
        校验权益编码存在

        :param db: 数据库会话
        :param code: 权益编码
        :return:
        """
        entitlement = await entitlement_dao.get_by_code(db, code)
        if not entitlement:
            raise errors.NotFoundError(msg=f'权益不存在: {code}')


resource_rule_service: ResourceRuleService = ResourceRuleService()
