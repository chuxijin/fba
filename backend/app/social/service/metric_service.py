#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from sqlalchemy import Select

from backend.app.social.crud.crud_metric import social_work_metric_dao
from backend.app.social.model.metric import SocialWorkMetric
from backend.app.social.schema.metric import (
    CreateSocialWorkMetricParam,
    UpdateSocialWorkMetricParam,
)
from backend.common.exception import errors
from backend.database.db import async_db_session


class SocialWorkMetricService:
    """作品数据服务类"""

    @staticmethod
    async def get(*, pk: int) -> SocialWorkMetric:
        """获取作品数据详情"""
        async with async_db_session() as db:
            metric = await social_work_metric_dao.get(db, pk)
            if not metric:
                raise errors.NotFoundError(msg='作品数据不存在')
            return metric

    @staticmethod
    async def get_latest_by_work(*, work_id: int) -> SocialWorkMetric | None:
        """获取作品最新数据快照"""
        async with async_db_session() as db:
            return await social_work_metric_dao.get_latest_by_work(db, work_id)

    @staticmethod
    async def get_list(*, work_id: int | None) -> Select:
        """获取作品数据列表查询语句"""
        return await social_work_metric_dao.get_list(work_id=work_id)

    @staticmethod
    async def create(*, obj: CreateSocialWorkMetricParam, current_user_id: int) -> SocialWorkMetric:
        """创建作品数据快照"""
        async with async_db_session() as db:
            metric = await social_work_metric_dao.create(db, obj, current_user_id)
            return metric

    @staticmethod
    async def update(*, pk: int, obj: UpdateSocialWorkMetricParam, current_user_id: int) -> int:
        """更新作品数据快照"""
        async with async_db_session() as db:
            count = await social_work_metric_dao.update(db, pk, obj, current_user_id)
            if count == 0:
                raise errors.NotFoundError(msg='作品数据不存在')
            return count

    @staticmethod
    async def delete(*, pks: list[int]) -> int:
        """删除作品数据快照"""
        async with async_db_session() as db:
            return await social_work_metric_dao.delete(db, pks)
