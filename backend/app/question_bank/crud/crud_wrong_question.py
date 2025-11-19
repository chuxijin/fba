#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.question_bank.model import WrongQuestionBook


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
        self, db: AsyncSession, user_id: int, question_id: int
    ) -> WrongQuestionBook | None:
        """
        获取用户特定题目的错题记录

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param question_id: 题目 ID
        :return:
        """
        return await self.select_model_by_column(db, user_id=user_id, question_id=question_id)

    async def get_by_user(
        self, db: AsyncSession, user_id: int, is_mastered: bool | None = None, is_pinned: bool | None = None
    ) -> list[WrongQuestionBook]:
        """
        获取用户的错题本列表

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param is_mastered: 是否已掌握
        :param is_pinned: 是否置顶
        :return:
        """
        filters = {'user_id': user_id}
        if is_mastered is not None:
            filters['is_mastered'] = is_mastered
        if is_pinned is not None:
            filters['is_pinned'] = is_pinned

        stmt = await self.select_order('last_wrong_time', 'desc', **filters)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def create(self, db: AsyncSession, user_id: int, question_id: int, wrong_time: datetime) -> WrongQuestionBook:
        """
        创建错题记录

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param question_id: 题目 ID
        :param wrong_time: 错误时间
        :return:
        """
        new_wrong = self.model(
            user_id=user_id,
            question_id=question_id,
            wrong_count=1,
            correct_count=0,
            first_wrong_time=wrong_time,
            last_wrong_time=wrong_time,
        )
        db.add(new_wrong)
        await db.flush()
        await db.refresh(new_wrong)
        return new_wrong

    async def increment_wrong(self, db: AsyncSession, wrong_id: int, wrong_time: datetime) -> int:
        """
        增加错误次数（答错时调用）

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
                'correct_count': 0,
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

        new_correct_count = wrong.correct_count + 1
        update_data = {'correct_count': new_correct_count, 'last_practice_time': practice_time}

        if new_correct_count >= 3:
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
        update_data = {'is_pinned': is_pinned}
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
        mastered_list = await self.get_by_user(db, user_id, is_mastered=True)
        count = 0
        for wrong in mastered_list:
            count += await self.delete_model(db, wrong.id)
        return count

    async def get_select(
        self, user_id: int | None = None, is_mastered: bool | None = None, is_pinned: bool | None = None
    ) -> Select:
        """
        获取错题本列表查询表达式

        :param user_id: 用户 ID
        :param is_mastered: 是否已掌握
        :param is_pinned: 是否置顶
        :return:
        """
        filters = {}

        if user_id:
            filters['user_id'] = user_id
        if is_mastered is not None:
            filters['is_mastered'] = is_mastered
        if is_pinned is not None:
            filters['is_pinned'] = is_pinned

        return await self.select_order('last_wrong_time', 'desc', **filters)


wrong_question_dao: CRUDWrongQuestion = CRUDWrongQuestion(WrongQuestionBook)
