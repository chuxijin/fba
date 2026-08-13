#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence
from typing import Any

from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.access.constants import CommonStatus, TemplateKind
from backend.app.access.crud.crud_pack import entitlement_pack_dao
from backend.app.access.crud.crud_template import subscription_template_dao, template_pack_dao
from backend.app.access.crud.crud_tier import membership_tier_dao
from backend.app.access.model.pack import EntitlementPack
from backend.app.access.model.template import SubscriptionTemplate, TemplatePack
from backend.app.access.schema.template import (
    CreateTemplateParam,
    GetTemplateDetail,
    GetTemplateDetailWithPacks,
    GetTemplateListItem,
    SetTemplatePacksParam,
    TemplatePackBrief,
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
        tier = await membership_tier_dao.select_model(db, template.tier_id) if template.tier_id is not None else None
        domain_codes = list((template.metadata_ or {}).get('domain_codes', []) or [])
        return GetTemplateDetailWithPacks(
            id=template.id,
            code=template.code,
            name=template.name,
            tier_code=tier.code if tier else None,
            tier_name=tier.name if tier else None,
            tier_weight=tier.weight if tier else 0,
            is_paid_membership=tier.is_paid if tier else False,
            tier_badge_color=tier.badge_color if tier else None,
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
            domain_codes=domain_codes,
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
    async def build_list_items(
        db: AsyncSession,
        *,
        templates: Sequence[GetTemplateDetail | dict[str, Any]],
    ) -> list[GetTemplateListItem]:
        """
        构建模板列表项

        :param db: 数据库会话
        :param templates: 模板基础数据
        :return:
        """
        template_details = [
            item if isinstance(item, GetTemplateDetail) else GetTemplateDetail.model_validate(item)
            for item in templates
        ]
        if not template_details:
            return []

        template_ids = [template.id for template in template_details]
        templates_orm = await subscription_template_dao.select_models(db, id__in=template_ids)
        metadata_map = {t.id: (t.metadata_ or {}) for t in templates_orm}
        tier_ids = list({t.tier_id for t in templates_orm if t.tier_id is not None})
        tiers = await membership_tier_dao.select_models(db, id__in=tier_ids) if tier_ids else []
        tier_map = {tier.id: tier for tier in tiers}
        template_tier_map = {
            template.id: tier_map.get(template.tier_id) if template.tier_id is not None else None
            for template in templates_orm
        }

        relations = await template_pack_dao.get_by_templates(db, template_ids)
        pack_ids = list({relation.pack_id for relation in relations})
        packs = await entitlement_pack_dao.select_models(db, id__in=pack_ids) if pack_ids else []

        pack_map = {pack.id: pack for pack in packs}

        relation_map: dict[int, list[TemplatePack]] = {}
        for relation in relations:
            relation_map.setdefault(relation.template_id, []).append(relation)

        items: list[GetTemplateListItem] = []
        for template in template_details:
            pack_briefs: list[TemplatePackBrief] = []
            metadata = metadata_map.get(template.id) or {}
            tier = template_tier_map.get(template.id)
            domain_codes: list[str] = list(metadata.get('domain_codes', []) or [])

            for relation in relation_map.get(template.id, []):
                pack = pack_map.get(relation.pack_id)
                if pack is None:
                    continue

                pack_briefs.append(
                    TemplatePackBrief(
                        code=pack.code,
                        name=pack.name,
                        domain_id=pack.domain_id,
                        domain_code=None,
                    )
                )

            item_data = template.model_dump()
            item_data.update(
                tier_code=tier.code if tier else None,
                tier_name=tier.name if tier else None,
                tier_weight=tier.weight if tier else 0,
                is_paid_membership=tier.is_paid if tier else False,
                tier_badge_color=tier.badge_color if tier else None,
                pack_codes=[pack.code for pack in pack_briefs],
                domain_codes=domain_codes,
                packs=pack_briefs,
            )
            items.append(GetTemplateListItem.model_validate(item_data))

        return items

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

        data = obj.model_dump(exclude={'pack_codes', 'sale_period', 'tier_code'})
        data['tier_id'] = await SubscriptionTemplateService._resolve_tier_id(db, obj.tier_code)
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
        data = obj.model_dump(exclude_unset=True, exclude={'sale_period', 'tier_code'})
        if 'tier_code' in obj.model_fields_set:
            data['tier_id'] = await SubscriptionTemplateService._resolve_tier_id(db, obj.tier_code)
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

    @staticmethod
    async def _resolve_tier_id(db: AsyncSession, tier_code: str | None) -> int | None:
        """把对外档位编码解析为内部 ID"""
        if tier_code is None or not tier_code.strip():
            return None
        normalized_code = tier_code.strip().upper()
        tier = await membership_tier_dao.get_by_code(db, normalized_code)
        if not tier:
            raise errors.NotFoundError(msg=f'会员档位不存在: {normalized_code}')
        if tier.status != CommonStatus.ACTIVE:
            raise errors.ForbiddenError(msg=f'会员档位未启用: {normalized_code}')
        return tier.id


subscription_template_service: SubscriptionTemplateService = SubscriptionTemplateService()
