#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.social.model.metric import SocialWorkMetric
from backend.app.social.schema.metric import (
    CreateSocialWorkMetricParam,
    UpdateSocialWorkMetricParam,
)


class CRUDSocialWorkMetric(CRUDPlus[SocialWorkMetric]):
    """作品数据数据库操作类"""

    async def get(self, db: AsyncSession, pk: int) -> SocialWorkMetric | None:
        """获取作品数据详情"""
        return await self.select_model(db, pk)

    async def get_latest_by_work(self, db: AsyncSession, work_id: int) -> SocialWorkMetric | None:
        """获取作品最新数据快照"""
        return await self.select_model_by_column(db, work_id=work_id, order_by='-record_time')

    async def get_list(self, *, work_id: int | None) -> Select:
        """获取作品数据列表查询语句"""
        filters: dict[str, object] = {}
        if work_id is not None:
            filters['work_id'] = work_id
        return await self.select_order('record_time', 'desc', load_strategies={'work': 'noload'}, **filters)

    async def create(
        self, db: AsyncSession, obj: CreateSocialWorkMetricParam, current_user_id: int | None = None
    ) -> SocialWorkMetric:
        """创建作品数据快照"""
        data = obj.model_dump()
        if 'created_by' not in data:
            data['created_by'] = current_user_id or 0
        metric = self.model(**data)
        db.add(metric)
        await db.commit()
        await db.refresh(metric)
        return metric

    async def update(
        self, db: AsyncSession, pk: int, obj: UpdateSocialWorkMetricParam, current_user_id: int | None = None
    ) -> int:
        """更新作品数据快照"""
        update_data = obj.model_dump(exclude_unset=True)
        if current_user_id:
            update_data['updated_by'] = current_user_id
        count = await self.update_model_by_column(db, update_data, id=pk)
        await db.commit()
        return count

    async def delete(self, db: AsyncSession, pks: list[int]) -> int:
        """删除作品数据快照"""
        count = await self.delete_model_by_column(db, allow_multiple=True, id__in=pks)
        await db.commit()
        return count


# 实例
social_work_metric_dao = CRUDSocialWorkMetric(SocialWorkMetric)
