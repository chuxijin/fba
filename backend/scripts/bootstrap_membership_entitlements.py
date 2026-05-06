#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio

from dataclasses import dataclass

from sqlalchemy import select

from backend.app.membership.constants import MembershipEntitlementCode
from backend.app.membership.model.entitlement import MembershipEntitlement
from backend.app.membership.model.tier import MembershipTier
from backend.app.membership.model.tier_entitlement import MembershipTierEntitlement
from backend.database.db import async_db_session


@dataclass(slots=True)
class EntitlementPreset:
    """权益预设"""

    code: str
    name: str
    sort: int
    description: str


ENTITLEMENT_PRESETS: tuple[EntitlementPreset, ...] = (
    EntitlementPreset(
        code=MembershipEntitlementCode.QBANK_VIP_BANK,
        name='VIP 题库',
        sort=100,
        description='访问标记为 VIP 的题库',
    ),
    EntitlementPreset(
        code=MembershipEntitlementCode.QBANK_SVIP_BANK,
        name='SVIP 题库',
        sort=110,
        description='访问标记为 SVIP 的题库',
    ),
    EntitlementPreset(
        code=MembershipEntitlementCode.QBANK_ADVANCED_FILTER,
        name='题库高级筛选',
        sort=120,
        description='使用题库高级筛选条件',
    ),
    EntitlementPreset(
        code=MembershipEntitlementCode.QBANK_KNOWLEDGE_PRACTICE,
        name='知识点刷题',
        sort=130,
        description='使用知识点维度刷题',
    ),
)

FAMILY_ENTITLEMENT_CODES: dict[str, tuple[str, ...]] = {
    'VIP': (
        MembershipEntitlementCode.QBANK_VIP_BANK,
        MembershipEntitlementCode.QBANK_ADVANCED_FILTER,
        MembershipEntitlementCode.QBANK_KNOWLEDGE_PRACTICE,
    ),
    'SVIP': (
        MembershipEntitlementCode.QBANK_VIP_BANK,
        MembershipEntitlementCode.QBANK_SVIP_BANK,
        MembershipEntitlementCode.QBANK_ADVANCED_FILTER,
        MembershipEntitlementCode.QBANK_KNOWLEDGE_PRACTICE,
    ),
}


async def upsert_entitlements() -> dict[str, MembershipEntitlement]:
    """初始化会员权益"""
    async with async_db_session.begin() as db:
        rows = (
            await db.execute(
                select(MembershipEntitlement).where(
                    MembershipEntitlement.code.in_([item.code for item in ENTITLEMENT_PRESETS]),
                )
            )
        ).scalars().all()
        entitlement_map = {item.code: item for item in rows}

        for preset in ENTITLEMENT_PRESETS:
            entitlement = entitlement_map.get(preset.code)
            if entitlement is None:
                entitlement = MembershipEntitlement(
                    code=preset.code,
                    name=preset.name,
                    value_type='bool',
                    default_value=0,
                    sort=preset.sort,
                    status=1,
                    description=preset.description,
                )
                db.add(entitlement)
                entitlement_map[preset.code] = entitlement
                continue

            entitlement.name = preset.name
            entitlement.value_type = 'bool'
            entitlement.default_value = 0
            entitlement.sort = preset.sort
            entitlement.status = 1
            entitlement.description = preset.description

        await db.flush()
        return entitlement_map


async def upsert_tier_entitlements(entitlement_map: dict[str, MembershipEntitlement]) -> int:
    """
    初始化等级权益映射

    :param entitlement_map: 权益映射
    :return:
    """
    changed_count = 0
    async with async_db_session.begin() as db:
        tiers = (
            await db.execute(
                select(MembershipTier).where(
                    MembershipTier.status == 1,
                    MembershipTier.family_code.in_(list(FAMILY_ENTITLEMENT_CODES.keys())),
                )
            )
        ).scalars().all()

        existing_rows = (
            await db.execute(
                select(MembershipTierEntitlement).where(
                    MembershipTierEntitlement.entitlement_code.in_([item.code for item in ENTITLEMENT_PRESETS]),
                )
            )
        ).scalars().all()
        existing_map = {
            (item.tier_id, item.entitlement_code): item
            for item in existing_rows
        }

        for tier in tiers:
            for entitlement_code in FAMILY_ENTITLEMENT_CODES.get(tier.family_code, ()):
                entitlement = entitlement_map[entitlement_code]
                mapping = existing_map.get((tier.id, entitlement_code))
                if mapping is None:
                    mapping = MembershipTierEntitlement(
                        tier_id=tier.id,
                        entitlement_id=entitlement.id,
                        entitlement_code=entitlement.code,
                        value=1,
                        status=1,
                        description=f'{tier.name} 默认题库权益',
                    )
                    db.add(mapping)
                    changed_count += 1
                    continue

                mapping.entitlement_id = entitlement.id
                mapping.value = 1
                mapping.status = 1
                mapping.description = f'{tier.name} 默认题库权益'
                changed_count += 1

        return changed_count


async def main() -> None:
    """执行初始化"""
    entitlement_map = await upsert_entitlements()
    changed_count = await upsert_tier_entitlements(entitlement_map)
    print(f'会员权益初始化完成，权益 {len(entitlement_map)} 个，等级映射处理 {changed_count} 条')


if __name__ == '__main__':
    asyncio.run(main())
