#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.trail.crud.crud_trail_point import trail_point_dao
from backend.app.trail.model.point import TrailPoint
from backend.app.trail.schema.point import BatchCreateTrailPointParam
from backend.common.pagination import paging_data


class TrailPointService:
    """轨迹点服务类"""

    @staticmethod
    async def batch_upload(db: AsyncSession, user_id: int, obj: BatchCreateTrailPointParam) -> int:
        """
        批量上传轨迹点

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param obj: 批量创建参数
        :return:
        """
        await trail_point_dao.batch_create(db, user_id, obj.points)
        return len(obj.points)

    @staticmethod
    async def get_trail_points(
        db: AsyncSession,
        user_id: int,
        start_time: datetime,
        end_time: datetime,
    ) -> dict:
        """
        分页查询轨迹点

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param start_time: 开始时间
        :param end_time: 结束时间
        :return:
        """
        from backend.app.trail.schema.point import GetTrailPointDetail

        stmt = await trail_point_dao.get_by_time_range(user_id, start_time, end_time)
        return await paging_data(db, stmt, GetTrailPointDetail)

    @staticmethod
    async def get_latest(db: AsyncSession, user_id: int) -> TrailPoint | None:
        """
        获取最新轨迹点

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        return await trail_point_dao.get_latest(db, user_id)


trail_point_service: TrailPointService = TrailPointService()
