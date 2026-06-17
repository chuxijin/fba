#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.social.model.work import SocialWork
from backend.app.social.schema.work import (
    CreateSocialWorkParam,
    UpdateSocialWorkParam,
)


class CRUDSocialWork(CRUDPlus[SocialWork]):
    """作品数据库操作类"""

    async def get(self, db: AsyncSession, pk: int) -> SocialWork | None:
        """
        获取作品详情

        :param db: 数据库会话
        :param pk: 作品 ID
        :return:
        """
        return await self.select_model(db, pk)

    async def get_by_external(self, db: AsyncSession, *, account_id: int, external_id: str) -> SocialWork | None:
        """通过账号与平台作品ID获取作品"""
        return await self.select_model_by_column(db, account_id=account_id, external_id=external_id)

    async def get_list(self, *, account_id: int | None, external_id: str | None) -> Select:
        """获取作品列表，附带最新快照的四项指标"""
        stmt = select(self.model)

        if account_id is not None:
            stmt = stmt.where(self.model.account_id == account_id)
        if external_id is not None:
            stmt = stmt.where(self.model.external_id.like(f'%{external_id}%'))

        return stmt.order_by(self.model.id.desc())

    async def create(
        self, db: AsyncSession, obj: CreateSocialWorkParam, current_user_id: int | None = None
    ) -> SocialWork:
        """创建作品"""
        data = obj.model_dump()
        # 自动从链接提取 external_id（支持多平台，如 B站、小红书）
        if (not data.get('external_id')) and isinstance(data.get('work_url'), str):
            import re

            patterns = [
                r'/video/([A-Za-z0-9]+)',  # bilibili: /video/BV1....
                r'/explore/([A-Za-z0-9]+)',  # xiaohongshu: /explore/<id>
            ]
            for pat in patterns:
                m = re.search(pat, data['work_url'])
                if m:
                    data['external_id'] = m.group(1)
                    break
        # 兜底：依然没有 external_id 则用 URL 末段（去掉 query/hash）
        if not data.get('external_id'):
            try:
                from urllib.parse import urlparse

                path = urlparse(data.get('work_url') or '').path or ''
                seg = path.rstrip('/').split('/')[-1]
                data['external_id'] = seg or data.get('external_id')
            except Exception:
                pass
        if 'created_by' not in data:
            data['created_by'] = current_user_id or 0
        work = self.model(**data)
        db.add(work)
        await db.commit()
        await db.refresh(work)
        return work

    async def update(
        self, db: AsyncSession, pk: int, obj: UpdateSocialWorkParam, current_user_id: int | None = None
    ) -> int:
        """更新作品"""
        update_data = obj.model_dump(exclude_unset=True)
        if current_user_id:
            update_data['updated_by'] = current_user_id
        count = await self.update_model_by_column(db, update_data, id=pk)
        await db.commit()
        return count

    async def delete(self, db: AsyncSession, pks: list[int]) -> int:
        """删除作品"""
        count = await self.delete_model_by_column(db, allow_multiple=True, id__in=pks)
        await db.commit()
        return count


# 实例
social_work_dao = CRUDSocialWork(SocialWork)
