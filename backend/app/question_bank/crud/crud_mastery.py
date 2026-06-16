#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
from typing import Sequence

import sqlalchemy as sa

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.question_bank.model.mastery import WrongMasteryStatus
from sqlalchemy_crud_plus import CRUDPlus
from backend.utils.timezone import timezone

# 基础间隔（固定 1 天）
BASE_INTERVAL_DAYS = 1


class CRUDMastery(CRUDPlus[WrongMasteryStatus]):
    """错题掌握状态 CRUD"""

    async def create(self, db: AsyncSession, **kwargs) -> WrongMasteryStatus:
        """
        创建掌握状态记录

        :param db: 数据库会话
        :return:
        """
        mastery = WrongMasteryStatus(**kwargs)
        db.add(mastery)
        await db.flush()
        return mastery

    async def get_by_question(
        self,
        db: AsyncSession,
        user_id: int,
        question_id: int | None = None,
        custom_question_id: int | None = None,
    ) -> WrongMasteryStatus | None:
        """
        根据题目获取掌握状态

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param question_id: 题库题目 ID
        :param custom_question_id: 自定义错题 ID
        :return:
        """
        stmt = select(self.model).where(
            self.model.user_id == user_id,
            self.model.deleted == 0,
        )
        if question_id is not None:
            stmt = stmt.where(self.model.question_id == question_id)
        elif custom_question_id is not None:
            stmt = stmt.where(self.model.custom_question_id == custom_question_id)
        else:
            return None

        result = await db.execute(stmt)
        return result.scalars().first()

    async def get_or_create(
        self,
        db: AsyncSession,
        user_id: int,
        question_id: int | None = None,
        custom_question_id: int | None = None,
    ) -> WrongMasteryStatus:
        """
        获取或创建掌握状态记录

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param question_id: 题库题目 ID
        :param custom_question_id: 自定义错题 ID
        :return:
        """
        existing = await self.get_by_question(db, user_id, question_id, custom_question_id)
        if existing:
            return existing

        now = timezone.now()
        new_record = await self.create(
            db,
            user_id=user_id,
            question_id=question_id,
            custom_question_id=custom_question_id,
            status='learning',
            correct_streak=0,
            review_count=0,
            last_practice_time=now,
            next_review_time=now + timedelta(days=BASE_INTERVAL_DAYS),
        )
        return new_record

    @staticmethod
    def calc_next_review_time(correct_streak: int) -> datetime:
        """
        计算下次复习时间

        :param correct_streak: 连续答对次数
        :return: 下次复习时间
        """
        interval = BASE_INTERVAL_DAYS * (2 ** correct_streak)
        return timezone.now() + timedelta(days=interval)

    async def on_correct(
        self,
        db: AsyncSession,
        user_id: int,
        question_id: int | None = None,
        custom_question_id: int | None = None,
        mastery_threshold: int = 3,
    ) -> WrongMasteryStatus:
        """
        做题答对时更新掌握状态

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param question_id: 题库题目 ID
        :param custom_question_id: 自定义错题 ID
        :param mastery_threshold: 掌握阈值
        :return:
        """
        mastery = await self.get_or_create(db, user_id, question_id, custom_question_id)
        now = timezone.now()

        mastery.correct_streak += 1
        mastery.last_practice_time = now
        mastery.next_review_time = self.calc_next_review_time(mastery.correct_streak)

        if mastery.correct_streak >= mastery_threshold:
            mastery.status = 'mastered'
            if mastery.mastered_time is None:
                mastery.mastered_time = now

        await db.flush()
        return mastery

    async def on_wrong(
        self,
        db: AsyncSession,
        user_id: int,
        question_id: int | None = None,
        custom_question_id: int | None = None,
    ) -> WrongMasteryStatus:
        """
        做题答错时更新掌握状态

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param question_id: 题库题目 ID
        :param custom_question_id: 自定义错题 ID
        :return:
        """
        mastery = await self.get_or_create(db, user_id, question_id, custom_question_id)
        now = timezone.now()

        mastery.correct_streak = 0
        mastery.status = 'learning'
        mastery.last_practice_time = now
        mastery.next_review_time = self.calc_next_review_time(0)

        await db.flush()
        return mastery

    async def mark_as_mastered(
        self,
        db: AsyncSession,
        user_id: int,
        question_id: int | None = None,
        custom_question_id: int | None = None,
    ) -> WrongMasteryStatus:
        """
        手动标记为已掌握

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param question_id: 题库题目 ID
        :param custom_question_id: 自定义错题 ID
        :return:
        """
        mastery = await self.get_or_create(db, user_id, question_id, custom_question_id)
        now = timezone.now()

        mastery.status = 'mastered'
        mastery.mastered_time = now
        mastery.next_review_time = None

        await db.flush()
        return mastery

    async def on_review(
        self,
        db: AsyncSession,
        user_id: int,
        question_id: int | None = None,
        custom_question_id: int | None = None,
    ) -> WrongMasteryStatus:
        """
        复盘时更新掌握状态

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param question_id: 题库题目 ID
        :param custom_question_id: 自定义错题 ID
        :return:
        """
        mastery = await self.get_or_create(db, user_id, question_id, custom_question_id)
        now = timezone.now()

        mastery.review_count += 1
        mastery.last_review_time = now

        await db.flush()
        return mastery

    async def check_and_mark_forgotten(
        self,
        db: AsyncSession,
        user_id: int,
    ) -> int:
        """
        检查并标记遗忘的题目

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return: 标记为遗忘的题目数量
        """
        now = timezone.now()
        stmt = (
            sa.update(self.model)
            .where(
                self.model.user_id == user_id,
                self.model.status == 'mastered',
                self.model.next_review_time < now,
                self.model.deleted == 0,
            )
            .values(status='forgotten')
        )
        result = await db.execute(stmt)
        await db.flush()
        return result.rowcount

    async def get_stats(
        self,
        db: AsyncSession,
        user_id: int,
    ) -> dict[str, int]:
        """
        获取用户掌握状态统计

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return: {learning: X, mastered: X, forgotten: X}
        """
        stmt = (
            select(
                self.model.status,
                func.count().label('count'),
            )
            .where(
                self.model.user_id == user_id,
                self.model.deleted == 0,
            )
            .group_by(self.model.status)
        )
        result = await db.execute(stmt)
        rows = result.all()

        stats = {'learning': 0, 'mastered': 0, 'forgotten': 0}
        for row in rows:
            stats[row.status] = row.count

        return stats

    async def get_forgotten_list(
        self,
        db: AsyncSession,
        user_id: int,
    ) -> Sequence[WrongMasteryStatus]:
        """
        获取遗忘题目列表

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return: 遗忘的掌握状态列表
        """
        stmt = (
            select(self.model)
            .where(
                self.model.user_id == user_id,
                self.model.status == 'forgotten',
                self.model.deleted == 0,
            )
            .order_by(self.model.next_review_time.asc())
        )
        result = await db.execute(stmt)
        return result.scalars().all()

    async def list_by_status(
        self,
        db: AsyncSession,
        user_id: int,
        status: str | None = None,
    ) -> Sequence[WrongMasteryStatus]:
        """
        按状态获取掌握状态列表

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param status: 状态筛选
        :return:
        """
        stmt = select(self.model).where(
            self.model.user_id == user_id,
            self.model.deleted == 0,
        )
        if status:
            stmt = stmt.where(self.model.status == status)

        stmt = stmt.order_by(self.model.created_time.desc())
        result = await db.execute(stmt)
        return result.scalars().all()


mastery_dao: CRUDMastery = CRUDMastery(WrongMasteryStatus)
