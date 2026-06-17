#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence
from datetime import date

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.study_plan.model.item import StudyPlanItem


class CRUDStudyPlanItem(CRUDPlus[StudyPlanItem]):
    """学习计划项数据库操作类"""

    async def get(self, db: AsyncSession, item_id: int) -> StudyPlanItem | None:
        """
        获取计划项详情

        :param db: 数据库会话
        :param item_id: 计划项 ID
        :return:
        """
        return await self.select_model(db, item_id, deleted=0)

    async def list_by_user_and_date(
        self,
        db: AsyncSession,
        user_id: int,
        target_date: date,
    ) -> Sequence[StudyPlanItem]:
        """
        获取学员指定日期的所有计划项（按 order_index 升序）

        :param db: 数据库会话
        :param user_id: 学员用户 ID
        :param target_date: 目标日期
        :return:
        """
        stmt = (
            select(StudyPlanItem)
            .where(
                StudyPlanItem.user_id == user_id,
                StudyPlanItem.plan_date == target_date,
                StudyPlanItem.deleted == 0,
            )
            .order_by(StudyPlanItem.order_index.asc())
        )
        result = await db.execute(stmt)
        return result.scalars().all()

    async def list_by_plan(self, db: AsyncSession, plan_id: int) -> Sequence[StudyPlanItem]:
        """
        获取计划下所有计划项（按日期 + 顺序）

        :param db: 数据库会话
        :param plan_id: 计划 ID
        :return:
        """
        stmt = (
            select(StudyPlanItem)
            .where(StudyPlanItem.plan_id == plan_id, StudyPlanItem.deleted == 0)
            .order_by(StudyPlanItem.plan_date.asc(), StudyPlanItem.order_index.asc())
        )
        result = await db.execute(stmt)
        return result.scalars().all()

    async def list_pending_before(
        self,
        db: AsyncSession,
        before_date: date,
    ) -> Sequence[StudyPlanItem]:
        """
        获取截止指定日期之前所有未完成的计划项（用于跨天定时清理）

        :param db: 数据库会话
        :param before_date: 截止日期（不含）
        :return:
        """
        stmt = select(StudyPlanItem).where(
            StudyPlanItem.plan_date < before_date,
            StudyPlanItem.status.in_(('pending', 'in_progress')),
            StudyPlanItem.deleted == 0,
        )
        result = await db.execute(stmt)
        return result.scalars().all()

    async def update_status(self, db: AsyncSession, item_id: int, status: str) -> int:
        """
        更新计划项状态

        :param db: 数据库会话
        :param item_id: 计划项 ID
        :param status: 新状态
        :return:
        """
        return await self.update_model(db, item_id, {'status': status})

    async def update_extra(self, db: AsyncSession, item_id: int, extra: dict) -> int:
        """
        覆写计划项 extra（JSONB）

        :param db: 数据库会话
        :param item_id: 计划项 ID
        :param extra: 新的 extra 字典
        :return:
        """
        return await self.update_model(db, item_id, {'extra': extra})

    async def get_by_session_key(self, db: AsyncSession, session_key: str) -> StudyPlanItem | None:
        """
        根据 extra->>'session_key' 反查关联的计划项

        :param db: 数据库会话
        :param session_key: 题库练习会话 key
        :return:
        """
        stmt = (
            select(StudyPlanItem)
            .where(
                StudyPlanItem.deleted == 0,
                StudyPlanItem.extra.op('->>')('session_key') == session_key,
            )
            .limit(1)
        )
        result = await db.execute(stmt)
        return result.scalars().first()

    async def bulk_skip_pending_before(
        self,
        db: AsyncSession,
        before_date: date,
    ) -> int:
        """
        批量将截止指定日期之前的未完成项标记为 skipped

        :param db: 数据库会话
        :param before_date: 截止日期（不含）
        :return:
        """
        stmt = (
            update(StudyPlanItem)
            .where(
                StudyPlanItem.plan_date < before_date,
                StudyPlanItem.status.in_(('pending', 'in_progress')),
                StudyPlanItem.deleted == 0,
            )
            .values(status='skipped')
        )
        result = await db.execute(stmt)
        return result.rowcount or 0


study_plan_item_dao = CRUDStudyPlanItem(StudyPlanItem)
