#!/usr/bin/env python3
"""将旧 INVITE 分享素材幂等迁入 CMS；默认仅预览，通过 --apply 写入。"""
import argparse
import asyncio

from sqlalchemy import select

from backend.app.admin.model import User
from backend.app.cms.model import CmsSlot
from backend.app.cms.schema.slot import CreateSlotParam
from backend.app.cms.service.share_service import legacy_material, normalize_share_slot
from backend.database.db import async_db_session
from backend.plugin.config.crud.crud_config import config_dao
from backend.plugin.config.enums import ConfigType


async def migrate(*, apply: bool, created_by: int | None) -> None:
    async with async_db_session.begin() as db:
        if apply:
            user = await db.get(User, created_by) if created_by else None
            if user is None or not (user.is_superuser or user.is_staff):
                raise ValueError('--apply 需要通过 --created-by 指定有效的后台管理用户 ID')
        existing = set((await db.execute(select(CmsSlot.code))).scalars())
        configs = await config_dao.get_all(db, type=ConfigType.invite)
        count = 0
        for item in sorted(configs, key=lambda entry: entry.id):
            material = legacy_material(item)
            if material is None or material.code in existing:
                continue
            payload = CreateSlotParam(
                code=material.code,
                name=f'邀请分享素材（原参数 {item.id}）',
                slot_type='share',
                scene='share.invite',
                title=material.title,
                image_url=material.image_url,
                status=1,
                extra={'share': material.settings.model_dump(mode='json')},
            )
            data = normalize_share_slot(payload.model_dump())
            if apply:
                db.add(CmsSlot(**data, created_by=created_by))
            existing.add(material.code)
            count += 1
            print(f'{"创建" if apply else "计划创建"}: {material.code} / {material.title or "无标题"}')
        print(f'{"已迁移" if apply else "待迁移"} {count} 条；已存在的 CMS 素材和原系统参数均保留。')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='写入数据库；默认只预览')
    parser.add_argument('--created-by', type=int, help='素材创建者的后台用户 ID')
    args = parser.parse_args()
    asyncio.run(migrate(apply=args.apply, created_by=args.created_by))
