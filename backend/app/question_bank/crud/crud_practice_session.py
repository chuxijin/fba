#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql import Select
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.question_bank.model import PracticeSession, SessionQuestion
from backend.app.question_bank.model.question import QuestionPlacement


class CRUDPracticeSession(CRUDPlus[PracticeSession]):
    """练习会话数据库操作类"""

    async def get(self, db: AsyncSession, session_id: int) -> PracticeSession | None:
        """
        获取练习会话详情

        :param db: 数据库会话
        :param session_id: 会话 ID
        :return:
        """
        return await self.select_model(db, session_id)

    async def get_detail(self, db: AsyncSession, session_id: int) -> PracticeSession | None:
        """
        获取练习会话详情（含会话题目快照和答题记录）

        :param db: 数据库会话
        :param session_id: 会话 ID
        :return:
        """
        stmt = (
            select(PracticeSession)
            .where(PracticeSession.id == session_id)
            .options(
                selectinload(PracticeSession.session_questions)
                .selectinload(SessionQuestion.placement)
                .selectinload(QuestionPlacement.chapter),
                selectinload(PracticeSession.records),
            )
        )
        result = await db.execute(stmt)
        return result.unique().scalars().first()

    async def get_by_user(
        self, db: AsyncSession, user_id: int, session_type: str | None = None
    ) -> list[PracticeSession]:
        """
        获取用户的练习会话列表

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param session_type: 会话类型
        :return:
        """
        filters: dict = {'user_id': user_id}
        if session_type:
            filters['session_type'] = session_type

        stmt = await self.select_order('start_time', 'desc', **filters)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_latest_session(
        self,
        db: AsyncSession,
        user_id: int,
        session_type: str | None = None,
        bank_id: int | None = None,
        chapter_id: int | None = None,
        source_key: str | None = None,
    ) -> PracticeSession | None:
        """
        获取用户最新的进行中会话

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param session_type: 会话类型
        :param bank_id: 题库 ID
        :param chapter_id: 章节 ID
        :param source_key: 来源签名
        :return:
        """
        filters: dict = {'user_id': user_id, 'status': 'in_progress', 'del_flag': False}
        if session_type:
            filters['session_type'] = session_type
        if bank_id:
            filters['bank_id'] = bank_id
        if chapter_id:
            filters['chapter_id'] = chapter_id
        if source_key:
            filters['source_key'] = source_key

        stmt = await self.select_order('start_time', 'desc', **filters)
        result = await db.execute(stmt)
        return result.scalars().first()

    async def create(self, db: AsyncSession, obj_dict: dict) -> PracticeSession:
        """
        创建练习会话

        :param db: 数据库会话
        :param obj_dict: 会话数据
        :return:
        """
        new_session = self.model(**obj_dict)
        db.add(new_session)
        await db.flush()
        await db.refresh(new_session)
        return new_session

    async def update_statistics(
        self,
        db: AsyncSession,
        session_id: int,
        *,
        completed_count: int,
        correct_count: int,
        wrong_count: int,
        total_time: int,
        score: Decimal | None = None,
        total_score: Decimal | None = None,
    ) -> int:
        """
        更新练习会话统计数据

        :param db: 数据库会话
        :param session_id: 会话 ID
        :param completed_count: 已完成数量
        :param correct_count: 答对数量
        :param wrong_count: 答错数量
        :param total_time: 总用时
        :param score: 得分
        :param total_score: 总满分
        :return:
        """
        accuracy_rate = Decimal('0')
        if completed_count > 0:
            accuracy_rate = Decimal(str(round(correct_count / completed_count * 100, 2)))

        update_data: dict = {
            'completed_count': completed_count,
            'correct_count': correct_count,
            'wrong_count': wrong_count,
            'accuracy_rate': accuracy_rate,
            'total_time': total_time,
        }
        if score is not None:
            update_data['score'] = score
        if total_score is not None:
            update_data['total_score'] = total_score

        return await self.update_model(db, session_id, update_data)

    async def mark_completed(
        self,
        db: AsyncSession,
        session_id: int,
        *,
        submit_time,
        completed_count: int,
        correct_count: int,
        wrong_count: int,
        total_time: int,
        score: Decimal | None = None,
        total_score: Decimal | None = None,
    ) -> int:
        """
        标记会话为已完成（提交时写入完整统计）

        :param db: 数据库会话
        :param session_id: 会话 ID
        :param submit_time: 提交时间
        :param completed_count: 已完成数量
        :param correct_count: 答对数量
        :param wrong_count: 答错数量
        :param total_time: 总用时
        :param score: 得分
        :param total_score: 总满分
        :return:
        """
        accuracy_rate = Decimal('0')
        if completed_count > 0:
            accuracy_rate = Decimal(str(round(correct_count / completed_count * 100, 2)))

        update_data: dict = {
            'status': 'completed',
            'submit_time': submit_time,
            'completed_count': completed_count,
            'correct_count': correct_count,
            'wrong_count': wrong_count,
            'accuracy_rate': accuracy_rate,
            'total_time': total_time,
        }
        if score is not None:
            update_data['score'] = score
        if total_score is not None:
            update_data['total_score'] = total_score

        return await self.update_model(db, session_id, update_data)

    async def abandon_session(self, db: AsyncSession, session_id: int) -> int:
        """
        放弃练习会话

        :param db: 数据库会话
        :param session_id: 会话 ID
        :return:
        """
        return await self.update_model(db, session_id, {'status': 'abandoned'})

    async def update_progress(
        self, db: AsyncSession, session_id: int, *, completed_count: int, total_time: int
    ) -> int:
        """
        更新会话做题进度（已完成题数和累计用时）

        :param db: 数据库会话
        :param session_id: 会话 ID
        :param completed_count: 已完成数量
        :param total_time: 累计用时（秒）
        :return:
        """
        return await self.update_model(db, session_id, {
            'completed_count': completed_count,
            'total_time': total_time,
        })

    async def get_select(
        self,
        user_id: int | None = None,
        session_type: str | None = None,
        bank_id: int | None = None,
        bank_ids: list[int] | None = None,
        chapter_id: int | None = None,
        status: str | None = None,
    ) -> Select:
        """
        获取练习会话列表查询表达式

        :param user_id: 用户 ID
        :param session_type: 会话类型
        :param bank_id: 题库 ID
        :param bank_ids: 题库 ID 列表
        :param chapter_id: 章节 ID
        :param status: 状态
        :return:
        """
        stmt = select(PracticeSession).where(PracticeSession.del_flag.is_(False)).order_by(PracticeSession.start_time.desc())

        if user_id is not None:
            stmt = stmt.where(PracticeSession.user_id == user_id)
        if session_type:
            stmt = stmt.where(PracticeSession.session_type == session_type)
        if bank_id is not None:
            stmt = stmt.where(PracticeSession.bank_id == bank_id)
        if bank_ids:
            stmt = stmt.where(PracticeSession.bank_id.in_(bank_ids))
        if chapter_id is not None:
            stmt = stmt.where(PracticeSession.chapter_id == chapter_id)
        if status:
            stmt = stmt.where(PracticeSession.status == status)

        return stmt

    async def delete(self, db: AsyncSession, session_id: int) -> int:
        """
        删除练习会话（级联删除关联的答题记录）

        :param db: 数据库会话
        :param session_id: 会话 ID
        :return:
        """
        return await self.delete_model_by_column(db, id=session_id, logical_deletion=True, deleted_flag_column='del_flag')


practice_session_dao: CRUDPracticeSession = CRUDPracticeSession(PracticeSession)
