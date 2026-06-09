#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.study_plan.model.record import StudyPlanRecord


class CRUDStudyPlanRecord(CRUDPlus[StudyPlanRecord]):
    """学习计划完成记录数据库操作类"""

    async def get(self, db: AsyncSession, record_id: int) -> StudyPlanRecord | None:
        """
        获取记录详情

        :param db: 数据库会话
        :param record_id: 记录 ID
        :return:
        """
        return await self.select_model(db, record_id, deleted=0)

    async def list_by_item(self, db: AsyncSession, item_id: int) -> Sequence[StudyPlanRecord]:
        """
        获取计划项的所有完成记录（按完成时间降序）

        :param db: 数据库会话
        :param item_id: 计划项 ID
        :return:
        """
        stmt = (
            select(StudyPlanRecord)
            .where(StudyPlanRecord.item_id == item_id, StudyPlanRecord.deleted == 0)
            .order_by(StudyPlanRecord.completed_at.desc())
        )
        result = await db.execute(stmt)
        return result.scalars().all()

    async def get_latest_by_item(
        self, db: AsyncSession, item_id: int,
    ) -> StudyPlanRecord | None:
        """
        获取计划项的最近一次完成记录

        :param db: 数据库会话
        :param item_id: 计划项 ID
        :return:
        """
        stmt = (
            select(StudyPlanRecord)
            .where(StudyPlanRecord.item_id == item_id, StudyPlanRecord.deleted == 0)
            .order_by(StudyPlanRecord.completed_at.desc())
            .limit(1)
        )
        result = await db.execute(stmt)
        return result.scalars().first()


study_plan_record_dao = CRUDStudyPlanRecord(StudyPlanRecord)
