#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.access.constants import CommonStatus
from backend.app.access.crud.crud_entitlement import entitlement_dao
from backend.app.access.crud.crud_pack import entitlement_pack_dao, pack_item_dao
from backend.app.access.crud.crud_template import subscription_template_dao
from backend.app.access.schema.catalog import (
    CatalogEntitlement,
    CatalogPack,
    CatalogTemplate,
    GetSubscriptionCatalog,
)
from backend.app.access.schema.template import GetTemplateDetail
from backend.app.access.service.template_service import subscription_template_service


class SubscriptionCatalogService:
    """游客可浏览的销售资料，数据范围仅限在售套餐的有效关联"""

    @staticmethod
    async def get_catalog(*, db: AsyncSession) -> GetSubscriptionCatalog:
        templates = await subscription_template_dao.get_sale_catalog(db)
        items = await subscription_template_service.build_list_items(
            db=db,
            templates=[GetTemplateDetail.model_validate(template) for template in templates],
        )
        pack_codes = {code for item in items for code in item.pack_codes}
        packs = await entitlement_pack_dao.select_models(
            db, code__in=list(pack_codes), status__eq=CommonStatus.ACTIVE,
        ) if pack_codes else []
        pack_items = await pack_item_dao.get_by_packs(db, [pack.id for pack in packs])
        entitlement_ids = {item.entitlement_id for item in pack_items}
        entitlements = await entitlement_dao.select_models(
            db, id__in=list(entitlement_ids), status__eq=CommonStatus.ACTIVE,
        ) if entitlement_ids else []
        entitlement_codes = {item.id: item.code for item in entitlements}
        active_pack_codes = {pack.code for pack in packs}
        public_templates = []
        for item in items:
            public_item = CatalogTemplate.model_validate(item)
            public_item.pack_codes = [code for code in item.pack_codes if code in active_pack_codes]
            public_item.packs = [pack for pack in item.packs if pack.code in active_pack_codes]
            public_templates.append(public_item)
        return GetSubscriptionCatalog(
            templates=public_templates,
            packs=[
                CatalogPack(
                    code=pack.code,
                    name=pack.name,
                    description=pack.description,
                    entitlement_codes=list(dict.fromkeys(
                        entitlement_codes[item.entitlement_id]
                        for item in pack_items
                        if item.pack_id == pack.id and item.entitlement_id in entitlement_codes
                    )),
                )
                for pack in packs
            ],
            entitlements=[CatalogEntitlement.model_validate(item) for item in entitlements],
        )


subscription_catalog_service = SubscriptionCatalogService()
