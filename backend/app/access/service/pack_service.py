#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence

from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.access.constants import CommonStatus, GradeLevel
from backend.app.access.crud.crud_entitlement import entitlement_dao
from backend.app.access.crud.crud_pack import entitlement_pack_dao, pack_item_dao
from backend.app.access.model.pack import EntitlementPack, PackItem
from backend.app.access.schema.pack import (
    CreatePackParam,
    SetPackItemsParam,
    UpdatePackParam,
)
from backend.common.exception import errors


class EntitlementPackService:
    """权益包服务"""

    @staticmethod
    async def get(db: AsyncSession, *, pk: int) -> EntitlementPack:
        """
        获取权益包详情

        :param db: 数据库会话
        :param pk: 包 ID
        :return:
        """
        pack = await entitlement_pack_dao.select_model(db, pk)
        if not pack:
            raise errors.NotFoundError(msg='权益包不存在')
        return pack

    @staticmethod
    async def get_by_code(db: AsyncSession, *, code: str) -> EntitlementPack:
        """
        按编码获取权益包

        :param db: 数据库会话
        :param code: 包编码
        :return:
        """
        pack = await entitlement_pack_dao.get_by_code(db, code)
        if not pack:
            raise errors.NotFoundError(msg=f'权益包不存在: {code}')
        return pack

    @staticmethod
    async def get_items(db: AsyncSession, *, pack_id: int) -> Sequence[PackItem]:
        """
        获取权益包成员

        :param db: 数据库会话
        :param pack_id: 包 ID
        :return:
        """
        return await pack_item_dao.get_by_pack(db, pack_id)

    @staticmethod
    async def get_select(
        *,
        grade: GradeLevel | None = None,
        domain_id: int | None = None,
        status: CommonStatus | None = None,
    ) -> Select:
        """
        获取分页查询语句

        :param grade: 档次
        :param domain_id: 领域 ID
        :param status: 状态
        :return:
        """
        return await entitlement_pack_dao.get_select(
            grade=grade, domain_id=domain_id, status=status
        )

    @staticmethod
    async def create(db: AsyncSession, *, obj: CreatePackParam) -> None:
        """
        创建权益包

        :param db: 数据库会话
        :param obj: 创建参数
        :return:
        """
        existing = await entitlement_pack_dao.get_by_code(db, obj.code)
        if existing:
            raise errors.ConflictError(msg='权益包编码已存在')
        await entitlement_pack_dao.create_model(db, obj)

    @staticmethod
    async def update(db: AsyncSession, *, pk: int, obj: UpdatePackParam) -> int:
        """
        更新权益包

        :param db: 数据库会话
        :param pk: 包 ID
        :param obj: 更新参数
        :return:
        """
        await EntitlementPackService.get(db, pk=pk)
        return await entitlement_pack_dao.update_model(db, pk, obj)

    @staticmethod
    async def delete(db: AsyncSession, *, pk: int) -> int:
        """
        删除权益包(级联删除成员)

        :param db: 数据库会话
        :param pk: 包 ID
        :return:
        """
        return await entitlement_pack_dao.delete_model(db, pk)

    @staticmethod
    async def set_items(db: AsyncSession, *, pack_id: int, obj: SetPackItemsParam) -> None:
        """
        批量重置权益包成员

        :param db: 数据库会话
        :param pack_id: 包 ID
        :param obj: 成员列表
        :return:
        """
        await EntitlementPackService.get(db, pk=pack_id)

        codes = [item.entitlement_code for item in obj.items]
        entitlements = await entitlement_dao.get_by_codes(db, codes)
        code_to_id = {ent.code: ent.id for ent in entitlements}

        missing = [code for code in codes if code not in code_to_id]
        if missing:
            raise errors.NotFoundError(msg=f'权益不存在: {missing}')

        await pack_item_dao.delete_by_pack(db, pack_id)

        for item in obj.items:
            entry = PackItem(
                pack_id=pack_id,
                entitlement_id=code_to_id[item.entitlement_code],
                value_int=item.value_int,
                value_meta=item.value_meta,
            )
            db.add(entry)


entitlement_pack_service: EntitlementPackService = EntitlementPackService()
