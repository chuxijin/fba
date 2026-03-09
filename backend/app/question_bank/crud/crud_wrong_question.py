#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime, timedelta

from sqlalchemy import case, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.question_bank.model import WrongQuestionBook
from backend.app.question_bank.model.question import Question, QuestionPlacement


class CRUDWrongQuestion(CRUDPlus[WrongQuestionBook]):
    """错题本数据库操作类"""

    async def get(self, db: AsyncSession, wrong_id: int) -> WrongQuestionBook | None:
        """
        获取错题记录详情

        :param db: 数据库会话
        :param wrong_id: 错题记录 ID
        :return:
        """
        return await self.select_model(db, wrong_id)

    async def get_by_user_and_question(
        self, db: AsyncSession, user_id: int, question_id: int, placement_id: int | None = None
    ) -> WrongQuestionBook | None:
        """
        获取用户特定题目的错题记录

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param question_id: 题目 ID
        :param placement_id: 挂载 ID
        :return:
        """
        filters: dict = {'user_id': user_id, 'question_id': question_id}
        if placement_id is not None:
            filters['placement_id'] = placement_id

        return await self.select_model_by_column(db, **filters)

    async def get_by_user(
        self, db: AsyncSession, user_id: int, is_mastered: bool | None = None, is_pinned: bool | None = None
    ) -> list[WrongQuestionBook]:
        """
        获取用户的错题本列表（复用 get_select 保持排序一致）

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param is_mastered: 是否已掌握
        :param is_pinned: 是否置顶
        :return:
        """
        stmt = await self.get_select(user_id=user_id, is_mastered=is_mastered, is_pinned=is_pinned)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def create(
        self,
        db: AsyncSession,
        user_id: int,
        question_id: int,
        wrong_time: datetime,
        placement_id: int | None = None,
    ) -> WrongQuestionBook:
        """
        创建错题记录

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param question_id: 题目 ID
        :param wrong_time: 错误时间
        :param placement_id: 挂载 ID
        :return:
        """
        new_wrong = self.model(
            user_id=user_id,
            question_id=question_id,
            placement_id=placement_id,
            wrong_count=1,
            correct_streak=0,
            first_wrong_time=wrong_time,
            last_wrong_time=wrong_time,
            created_by=user_id,
        )
        db.add(new_wrong)
        await db.flush()
        await db.refresh(new_wrong)
        return new_wrong

    async def increment_wrong(self, db: AsyncSession, wrong_id: int, wrong_time: datetime) -> int:
        """
        增加错误次数（答错时调用，连续做对链归零）

        :param db: 数据库会话
        :param wrong_id: 错题记录 ID
        :param wrong_time: 错误时间
        :return:
        """
        wrong = await self.select_model(db, wrong_id)
        if not wrong:
            return 0

        return await self.update_model(
            db,
            wrong_id,
            {
                'wrong_count': wrong.wrong_count + 1,
                'correct_streak': 0,
                'last_wrong_time': wrong_time,
                'is_mastered': False,
                'mastered_time': None,
            },
        )

    async def increment_correct(self, db: AsyncSession, wrong_id: int, practice_time: datetime) -> int:
        """
        增加连续做对次数（答对时调用，连续 3 次标记为已掌握）

        :param db: 数据库会话
        :param wrong_id: 错题记录 ID
        :param practice_time: 练习时间
        :return:
        """
        wrong = await self.select_model(db, wrong_id)
        if not wrong:
            return 0

        new_streak = wrong.correct_streak + 1
        update_data: dict = {'correct_streak': new_streak, 'last_practice_time': practice_time}

        if new_streak >= 3:
            update_data['is_mastered'] = True
            update_data['mastered_time'] = practice_time

        return await self.update_model(db, wrong_id, update_data)

    async def set_pin(self, db: AsyncSession, wrong_id: int, is_pinned: bool) -> int:
        """
        设置置顶状态

        :param db: 数据库会话
        :param wrong_id: 错题记录 ID
        :param is_pinned: 是否置顶
        :return:
        """
        update_data: dict = {'is_pinned': is_pinned}
        if is_pinned:
            update_data['pinned_time'] = datetime.now()
        else:
            update_data['pinned_time'] = None

        return await self.update_model(db, wrong_id, update_data)

    async def delete(self, db: AsyncSession, wrong_id: int) -> int:
        """
        删除错题记录

        :param db: 数据库会话
        :param wrong_id: 错题记录 ID
        :return:
        """
        return await self.delete_model(db, wrong_id)

    async def clear_mastered(self, db: AsyncSession, user_id: int) -> int:
        """
        清空用户已掌握的错题

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        stmt = delete(WrongQuestionBook).where(
            WrongQuestionBook.user_id == user_id,
            WrongQuestionBook.is_mastered == True,  # noqa: E712
        )
        result = await db.execute(stmt)
        return result.rowcount

    # ============ 聚合统计 ============

    async def get_statistics(self, db: AsyncSession, user_id: int) -> dict[str, int | float]:
        """
        获取用户错题统计概览

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        stmt = select(
            func.count().label('total'),
            func.sum(case((WrongQuestionBook.is_mastered == True, 1), else_=0)).label('mastered'),  # noqa: E712
            func.sum(case((WrongQuestionBook.is_mastered == False, 1), else_=0)).label('unmastered'),  # noqa: E712
            func.sum(case((WrongQuestionBook.is_pinned == True, 1), else_=0)).label('pinned'),  # noqa: E712
            func.avg(WrongQuestionBook.wrong_count).label('avg_wrong_count'),
            func.avg(WrongQuestionBook.correct_streak).label('avg_correct_streak'),
        ).where(WrongQuestionBook.user_id == user_id)

        result = await db.execute(stmt)
        row = result.first()

        return {
            'total': row.total or 0,
            'mastered': int(row.mastered or 0),
            'unmastered': int(row.unmastered or 0),
            'pinned': int(row.pinned or 0),
            'avg_wrong_count': round(float(row.avg_wrong_count or 0), 2),
            'avg_correct_streak': round(float(row.avg_correct_streak or 0), 2),
        }

    async def get_progress_statistics(self, db: AsyncSession, user_id: int) -> dict[str, int]:
        """
        获取用户错题进度统计（今日/近 7 天新增与已掌握数）

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        now = datetime.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_ago = today_start - timedelta(days=7)

        stmt = select(
            func.count().label('total'),
            func.sum(case((WrongQuestionBook.last_wrong_time >= today_start, 1), else_=0)).label('today_new'),
            func.sum(case((WrongQuestionBook.last_wrong_time >= week_ago, 1), else_=0)).label('week_new'),
            func.sum(case((WrongQuestionBook.mastered_time >= today_start, 1), else_=0)).label('today_mastered'),
            func.sum(case((WrongQuestionBook.mastered_time >= week_ago, 1), else_=0)).label('week_mastered'),
        ).where(WrongQuestionBook.user_id == user_id)

        result = await db.execute(stmt)
        row = result.first()

        return {
            'total': row.total or 0,
            'today_new': int(row.today_new or 0),
            'week_new': int(row.week_new or 0),
            'today_mastered': int(row.today_mastered or 0),
            'week_mastered': int(row.week_mastered or 0),
        }

    # ============ 列表查询 ============

    async def get_select(
        self,
        user_id: int,
        is_mastered: bool | None = None,
        is_pinned: bool | None = None,
        bank_id: int | None = None,
        chapter_id: int | None = None,
        keyword: str | None = None,
    ) -> Select:
        """
        获取错题本列表查询表达式

        :param user_id: 用户 ID
        :param is_mastered: 是否已掌握
        :param is_pinned: 是否置顶
        :param bank_id: 题库 ID（通过挂载筛选）
        :param chapter_id: 章节 ID（通过挂载筛选）
        :param keyword: 关键字搜索（搜索题干）
        :return:
        """
        stmt = select(WrongQuestionBook).where(WrongQuestionBook.user_id == user_id)

        if bank_id is not None or chapter_id is not None:
            stmt = stmt.join(
                QuestionPlacement,
                QuestionPlacement.id == WrongQuestionBook.placement_id,
            )
            if bank_id is not None:
                stmt = stmt.where(QuestionPlacement.bank_id == bank_id)
            if chapter_id is not None:
                stmt = stmt.where(QuestionPlacement.chapter_id == chapter_id)

        if keyword is not None:
            stmt = stmt.join(
                Question,
                Question.id == WrongQuestionBook.question_id,
            )
            stmt = stmt.where(Question.stem.like(f'%{keyword}%'))

        if is_mastered is not None:
            stmt = stmt.where(WrongQuestionBook.is_mastered == is_mastered)
        if is_pinned is not None:
            stmt = stmt.where(WrongQuestionBook.is_pinned == is_pinned)

        stmt = stmt.order_by(
            WrongQuestionBook.is_pinned.desc(),
            WrongQuestionBook.last_wrong_time.desc(),
        )
        return stmt


wrong_question_dao: CRUDWrongQuestion = CRUDWrongQuestion(WrongQuestionBook)
