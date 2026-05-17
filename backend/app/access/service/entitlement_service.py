#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.access.constants import CommonStatus, EntitlementCategory, EntitlementVerb
from backend.app.access.crud.crud_entitlement import entitlement_dao
from backend.app.access.model.entitlement import Entitlement
from backend.app.access.schema.entitlement import (
    CreateEntitlementParam,
    UpdateEntitlementParam,
)
from backend.common.exception import errors


class EntitlementService:
    """权益服务"""

    @staticmethod
    async def get(db: AsyncSession, *, pk: int) -> Entitlement:
        """
        获取权益详情

        :param db: 数据库会话
        :param pk: 权益 ID
        :return:
        """
        entitlement = await entitlement_dao.select_model(db, pk)
        if not entitlement:
            raise errors.NotFoundError(msg='权益不存在')
        return entitlement

    @staticmethod
    async def get_by_code(db: AsyncSession, *, code: str) -> Entitlement:
        """
        按编码获取权益

        :param db: 数据库会话
        :param code: 权益编码
        :return:
        """
        entitlement = await entitlement_dao.get_by_code(db, code)
        if not entitlement:
            raise errors.NotFoundError(msg=f'权益不存在: {code}')
        return entitlement

    @staticmethod
    async def get_select(
        *,
        keyword: str | None = None,
        category: EntitlementCategory | None = None,
        verb: EntitlementVerb | None = None,
        domain_id: int | None = None,
        resource_type: str | None = None,
        status: CommonStatus | None = None,
    ) -> Select:
        """
        获取分页查询语句

        :param keyword: 关键字
        :param category: 分类
        :param verb: 动作
        :param domain_id: 领域 ID
        :param resource_type: 资源类型
        :param status: 状态
        :return:
        """
        return await entitlement_dao.get_select(
            keyword=keyword,
            category=category,
            verb=verb,
            domain_id=domain_id,
            resource_type=resource_type,
            status=status,
        )

    @staticmethod
    async def create(db: AsyncSession, *, obj: CreateEntitlementParam) -> None:
        """
        创建权益

        :param db: 数据库会话
        :param obj: 创建参数
        :return:
        """
        existing = await entitlement_dao.get_by_code(db, obj.code)
        if existing:
            raise errors.ConflictError(msg='权益编码已存在')
        await entitlement_dao.create_model(db, obj)

    @staticmethod
    async def update(db: AsyncSession, *, pk: int, obj: UpdateEntitlementParam) -> int:
        """
        更新权益

        :param db: 数据库会话
        :param pk: 权益 ID
        :param obj: 更新参数
        :return:
        """
        await EntitlementService.get(db, pk=pk)
        return await entitlement_dao.update_model(db, pk, obj)

    @staticmethod
    async def delete(db: AsyncSession, *, pk: int) -> int:
        """
        删除权益

        :param db: 数据库会话
        :param pk: 权益 ID
        :return:
        """
        return await entitlement_dao.delete_model(db, pk)


entitlement_service: EntitlementService = EntitlementService()
