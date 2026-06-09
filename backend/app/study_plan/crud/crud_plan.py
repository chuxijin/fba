#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.study_plan.model.plan import StudyPlan


class CRUDStudyPlan(CRUDPlus[StudyPlan]):
    """学习计划数据库操作类"""

    async def get(self, db: AsyncSession, plan_id: int) -> StudyPlan | None:
        """
        获取计划详情

        :param db: 数据库会话
        :param plan_id: 计划 ID
        :return:
        """
        return await self.select_model(db, plan_id, deleted=0)

    async def list_active_by_user(self, db: AsyncSession, user_id: int) -> Sequence[StudyPlan]:
        """
        获取学员所有生效中的计划（支持多 active 并存）

        :param db: 数据库会话
        :param user_id: 学员用户 ID
        :return:
        """
        stmt = (
            select(StudyPlan)
            .where(
                StudyPlan.user_id == user_id,
                StudyPlan.status == 'active',
                StudyPlan.deleted == 0,
            )
            .order_by(StudyPlan.start_date.desc())
        )
        result = await db.execute(stmt)
        return result.scalars().all()

    async def list_by_user(self, db: AsyncSession, user_id: int) -> Sequence[StudyPlan]:
        """
        获取学员所有计划

        :param db: 数据库会话
        :param user_id: 学员用户 ID
        :return:
        """
        stmt = (
            select(StudyPlan)
            .where(StudyPlan.user_id == user_id, StudyPlan.deleted == 0)
            .order_by(StudyPlan.start_date.desc())
        )
        result = await db.execute(stmt)
        return result.scalars().all()

    async def list_active_covering_date(
        self, db: AsyncSession, user_id: int, target_date: date,
    ) -> Sequence[StudyPlan]:
        """
        获取学员在指定日期覆盖范围内的所有生效计划（支持多 active 并存）

        :param db: 数据库会话
        :param user_id: 学员用户 ID
        :param target_date: 目标日期
        :return:
        """
        stmt = (
            select(StudyPlan)
            .where(
                StudyPlan.user_id == user_id,
                StudyPlan.status == 'active',
                StudyPlan.deleted == 0,
                StudyPlan.start_date <= target_date,
                StudyPlan.end_date >= target_date,
            )
            .order_by(StudyPlan.start_date.asc())
        )
        result = await db.execute(stmt)
        return result.scalars().all()


study_plan_dao = CRUDStudyPlan(StudyPlan)
