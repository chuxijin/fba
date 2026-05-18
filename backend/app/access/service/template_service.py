#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence

from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.access.constants import CommonStatus, TemplateKind
from backend.app.access.crud.crud_pack import entitlement_pack_dao
from backend.app.access.crud.crud_template import subscription_template_dao, template_pack_dao
from backend.app.access.model.pack import EntitlementPack
from backend.app.access.model.template import SubscriptionTemplate, TemplatePack
from backend.app.access.schema.template import (
    CreateTemplateParam,
    GetTemplateDetailWithPacks,
    SetTemplatePacksParam,
    UpdateTemplateParam,
)
from backend.common.exception import errors


class SubscriptionTemplateService:
    """订阅模板服务"""

    @staticmethod
    async def get(db: AsyncSession, *, pk: int) -> SubscriptionTemplate:
        """
        获取模板详情

        :param db: 数据库会话
        :param pk: 模板 ID
        :return:
        """
        template = await subscription_template_dao.select_model(db, pk)
        if not template:
            raise errors.NotFoundError(msg='订阅模板不存在')
        return template

    @staticmethod
    async def get_detail(db: AsyncSession, *, pk: int) -> GetTemplateDetailWithPacks:
        """
        获取模板详情

        :param db: 数据库会话
        :param pk: 模板 ID
        :return:
        """
        template = await SubscriptionTemplateService.get(db, pk=pk)
        packs = await SubscriptionTemplateService.get_packs(db, template_id=pk)
        return GetTemplateDetailWithPacks(
            id=template.id,
            code=template.code,
            name=template.name,
            kind=template.kind,
            duration_days=template.duration_days,
            auto_renewable=template.auto_renewable,
            price_cents=template.price_cents,
            display_order=template.display_order,
            cover_image=template.cover_image,
            description=template.description,
            sale_period=template.sale_period,
            status=template.status,
            created_time=template.created_time,
            updated_time=template.updated_time,
            packs=packs,
        )

    @staticmethod
    async def get_by_code(db: AsyncSession, *, code: str) -> SubscriptionTemplate:
        """
        按编码获取模板

        :param db: 数据库会话
        :param code: 模板编码
        :return:
        """
        template = await subscription_template_dao.get_by_code(db, code)
        if not template:
            raise errors.NotFoundError(msg=f'订阅模板不存在: {code}')
        return template

    @staticmethod
    async def get_packs(db: AsyncSession, *, template_id: int) -> Sequence[EntitlementPack]:
        """
        获取模板关联的权益包

        :param db: 数据库会话
        :param template_id: 模板 ID
        :return:
        """
        relations = await template_pack_dao.get_by_template(db, template_id)
        pack_ids = [rel.pack_id for rel in relations]
        if not pack_ids:
            return []
        return await entitlement_pack_dao.select_models(db, id__in=pack_ids)

    @staticmethod
    async def get_select(
        *,
        kind: TemplateKind | None = None,
        status: CommonStatus | None = None,
    ) -> Select:
        """
        获取分页查询语句

        :param kind: 模板类型
        :param status: 状态
        :return:
        """
        return await subscription_template_dao.get_select(kind=kind, status=status)

    @staticmethod
    async def create(db: AsyncSession, *, obj: CreateTemplateParam) -> None:
        """
        创建模板(可选附带权益包关联)

        :param db: 数据库会话
        :param obj: 创建参数
        :return:
        """
        existing = await subscription_template_dao.get_by_code(db, obj.code)
        if existing:
            raise errors.ConflictError(msg='模板编码已存在')

        data = obj.model_dump(exclude={'pack_codes', 'sale_period'})
        if obj.sale_period is not None:
            data['sale_period'] = obj.sale_period.to_range()
        
        if 'metadata' in data:
            data['metadata_'] = data.pop('metadata')
            
        template = SubscriptionTemplate(**data)
        db.add(template)
        await db.flush()

        if obj.pack_codes:
            await SubscriptionTemplateService._sync_packs(db, template.id, obj.pack_codes)

    @staticmethod
    async def update(db: AsyncSession, *, pk: int, obj: UpdateTemplateParam) -> int:
        """
        更新模板

        :param db: 数据库会话
        :param pk: 模板 ID
        :param obj: 更新参数
        :return:
        """
        await SubscriptionTemplateService.get(db, pk=pk)
        data = obj.model_dump(exclude_unset=True, exclude={'sale_period'})
        if obj.sale_period is not None:
            data['sale_period'] = obj.sale_period.to_range()
            
        if 'metadata' in data:
            data['metadata_'] = data.pop('metadata')
            
        return await subscription_template_dao.update_model(db, pk, data)

    @staticmethod
    async def delete(db: AsyncSession, *, pk: int) -> int:
        """
        删除模板(级联删除关联)

        :param db: 数据库会话
        :param pk: 模板 ID
        :return:
        """
        return await subscription_template_dao.delete_model(db, pk)

    @staticmethod
    async def set_packs(db: AsyncSession, *, template_id: int, obj: SetTemplatePacksParam) -> None:
        """
        批量重置模板关联的权益包

        :param db: 数据库会话
        :param template_id: 模板 ID
        :param obj: 包编码列表
        :return:
        """
        await SubscriptionTemplateService.get(db, pk=template_id)
        await SubscriptionTemplateService._sync_packs(db, template_id, obj.pack_codes)

    @staticmethod
    async def _sync_packs(db: AsyncSession, template_id: int, pack_codes: list[str]) -> None:
        """
        同步模板↔包关联(全量替换)

        :param db: 数据库会话
        :param template_id: 模板 ID
        :param pack_codes: 包编码列表
        :return:
        """
        packs = await entitlement_pack_dao.get_by_codes(db, pack_codes)
        code_to_id = {pack.code: pack.id for pack in packs}
        missing = [code for code in pack_codes if code not in code_to_id]
        if missing:
            raise errors.NotFoundError(msg=f'权益包不存在: {missing}')

        await template_pack_dao.delete_by_template(db, template_id)
        for code in pack_codes:
            db.add(TemplatePack(template_id=template_id, pack_id=code_to_id[code]))


subscription_template_service: SubscriptionTemplateService = SubscriptionTemplateService()
