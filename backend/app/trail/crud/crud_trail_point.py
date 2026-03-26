#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.trail.model.point import TrailPoint
from backend.app.trail.schema.point import CreateTrailPointParam


class CRUDTrailPoint(CRUDPlus[TrailPoint]):
    """轨迹点数据库操作类"""

    async def batch_create(
        self,
        db: AsyncSession,
        user_id: int,
        objs: list[CreateTrailPointParam],
    ) -> None:
        """
        批量创建轨迹点

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param objs: 轨迹点参数列表
        :return:
        """
        points = [
            TrailPoint(**obj.model_dump(), user_id=user_id)
            for obj in objs
        ]
        db.add_all(points)
        await db.flush()

    async def get_by_time_range(
        self,
        user_id: int,
        start_time: datetime,
        end_time: datetime,
    ) -> Select:
        """
        按时间范围查询轨迹点

        :param user_id: 用户 ID
        :param start_time: 开始时间
        :param end_time: 结束时间
        :return:
        """
        return (
            select(self.model)
            .where(
                self.model.user_id == user_id,
                self.model.recorded_at >= start_time,
                self.model.recorded_at <= end_time,
            )
            .order_by(self.model.recorded_at.asc())
        )

    async def get_latest(self, db: AsyncSession, user_id: int) -> TrailPoint | None:
        """
        获取用户最新轨迹点

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        stmt = (
            select(self.model)
            .where(self.model.user_id == user_id)
            .order_by(self.model.recorded_at.desc())
            .limit(1)
        )
        result = await db.execute(stmt)
        return result.scalars().first()


trail_point_dao: CRUDTrailPoint = CRUDTrailPoint(TrailPoint)
