#!/usr/bin/env python3
"""售卖权益不可变版本：冻结套餐与权益包，复用现有权限查询路径。"""

import hashlib
import json

from copy import deepcopy

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.access.constants import CommonStatus
from backend.app.access.model.pack import EntitlementPack, PackItem
from backend.app.access.model.template import SubscriptionTemplate, TemplatePack
from backend.common.exception import errors
from backend.utils.timezone import timezone

SNAPSHOT_PREFIX = 'GBS_'


def ensure_sale_snapshot_writable(code: str) -> None:
    if code.startswith(SNAPSHOT_PREFIX):
        raise errors.ForbiddenError(msg='已售权益版本只读，请修改原套餐后创建新活动版本')


class SaleSnapshotService:
    @staticmethod
    async def capture(db: AsyncSession, template: SubscriptionTemplate, *, duration_days: int | None = None) -> dict:
        packs = list(
            (
                await db.scalars(
                    select(EntitlementPack)
                    .join(
                        TemplatePack,
                        TemplatePack.pack_id == EntitlementPack.id,
                    )
                    .where(TemplatePack.template_id == template.id)
                )
            ).all()
        )
        frozen = []
        for pack in packs:
            if pack.status != CommonStatus.ACTIVE:
                raise errors.RequestError(msg='套餐包含未启用权益包，不能用于拼团')
            items = list(
                (
                    await db.scalars(
                        select(PackItem)
                        .where(
                            PackItem.pack_id == pack.id,
                            PackItem.status == CommonStatus.ACTIVE,
                        )
                        .order_by(PackItem.id)
                    )
                ).all()
            )
            frozen.append({
                'name': pack.name,
                'domain_id': pack.domain_id,
                'description': pack.description,
                'items': [
                    {'entitlement_id': i.entitlement_id, 'value_int': i.value_int, 'value_meta': deepcopy(i.value_meta)}
                    for i in items
                ],
            })
        if not frozen:
            raise errors.RequestError(msg='套餐必须配置权益包后才可用于拼团')
        return {
            'original_code': template.code,
            'name': template.name,
            'tier_id': template.tier_id,
            'duration_days': duration_days if duration_days is not None else template.duration_days,
            'kind': template.kind.value,
            'cover_image': template.cover_image,
            'packs': frozen,
        }

    @staticmethod
    async def materialize(db: AsyncSession, snapshot: dict) -> SubscriptionTemplate:
        digest = hashlib.sha256(json.dumps(snapshot, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:40]
        code = f'{SNAPSHOT_PREFIX}{digest}'
        # 插入锁串行化同一版本的构建，重复任务不会创建多份权益包。
        created = (
            await db.execute(
                insert(SubscriptionTemplate)
                .values(
                    created_time=timezone.now(),
                    updated_time=timezone.now(),
                    code=code,
                    name=snapshot['name'],
                    tier_id=snapshot['tier_id'],
                    kind=snapshot['kind'],
                    duration_days=snapshot['duration_days'],
                    price_cents=0,
                    status=CommonStatus.DRAFT,
                    cover_image=snapshot['cover_image'],
                    metadata_={'sale_snapshot': True, 'original_code': snapshot['original_code']},
                )
                .on_conflict_do_nothing(index_elements=['code'])
                .returning(SubscriptionTemplate.id)
            )
        ).scalar_one_or_none()
        template = (await db.scalars(select(SubscriptionTemplate).where(SubscriptionTemplate.code == code))).one()
        if created is not None:
            for index, frozen in enumerate(snapshot['packs']):
                pack = EntitlementPack(
                    code=f'{code}_{index}',
                    name=frozen['name'],
                    domain_id=frozen['domain_id'],
                    description=frozen['description'],
                )
                db.add(pack)
                await db.flush()
                db.add(TemplatePack(template_id=template.id, pack_id=pack.id))
                for item in frozen['items']:
                    db.add(PackItem(pack_id=pack.id, **deepcopy(item)))
            await db.flush()
        return template


sale_snapshot_service = SaleSnapshotService()
