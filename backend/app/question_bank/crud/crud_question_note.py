#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import case, func, select, update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.question_bank.model import QuestionNote, UserNoteVote


class CRUDQuestionNote(CRUDPlus[QuestionNote]):
    """题目笔记数据库操作类"""

    async def get(self, db: AsyncSession, note_id: int) -> QuestionNote | None:
        """
        获取笔记详情

        :param db: 数据库会话
        :param note_id: 笔记 ID
        :return:
        """
        return await self.select_model(db, note_id)

    async def get_by_user_and_question(
        self, db: AsyncSession, user_id: int, question_id: int
    ) -> list[QuestionNote]:
        """
        获取用户在特定题目下的所有笔记

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param question_id: 题目 ID
        :return:
        """
        stmt = await self.select_order('updated_time', 'desc', user_id=user_id, question_id=question_id)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_public_notes(
        self, db: AsyncSession, question_id: int, is_featured: bool | None = None
    ) -> list[QuestionNote]:
        """
        获取题目的公开笔记（按质量分排序）

        :param db: 数据库会话
        :param question_id: 题目 ID
        :param is_featured: 是否只看精选
        :return:
        """
        filters: dict = {'question_id': question_id, 'is_public': True}
        if is_featured is not None:
            filters['is_featured'] = is_featured

        stmt = await self.select_order('quality_score', 'desc', **filters)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def create(self, db: AsyncSession, obj_dict: dict) -> QuestionNote:
        """
        创建笔记

        :param db: 数据库会话
        :param obj_dict: 笔记数据
        :return:
        """
        new_note = self.model(**obj_dict)
        db.add(new_note)
        await db.flush()
        await db.refresh(new_note)
        return new_note

    async def update(self, db: AsyncSession, note_id: int, **update_fields: object) -> int:
        """
        更新笔记（支持局部更新）

        :param db: 数据库会话
        :param note_id: 笔记 ID
        :param update_fields: 要更新的字段键值对
        :return:
        """
        if not update_fields:
            return 0

        return await self.update_model(db, note_id, update_fields)

    async def delete(self, db: AsyncSession, note_id: int) -> int:
        """
        删除笔记

        :param db: 数据库会话
        :param note_id: 笔记 ID
        :return:
        """
        return await self.delete_model(db, note_id)

    async def increment_view(self, db: AsyncSession, note_id: int) -> int:
        """
        原子增加浏览次数

        :param db: 数据库会话
        :param note_id: 笔记 ID
        :return:
        """
        stmt = (
            sa_update(QuestionNote)
            .where(QuestionNote.id == note_id)
            .values(view_count=QuestionNote.view_count + 1)
        )
        result = await db.execute(stmt)
        return result.rowcount

    async def update_vote_stats(self, db: AsyncSession, note_id: int, like_count: int, dislike_count: int) -> int:
        """
        更新投票统计（投票后调用）

        :param db: 数据库会话
        :param note_id: 笔记 ID
        :param like_count: 点赞数
        :param dislike_count: 点踩数
        :return:
        """
        quality_score = like_count - dislike_count
        return await self.update_model(
            db, note_id, {'like_count': like_count, 'dislike_count': dislike_count, 'quality_score': quality_score}
        )

    async def set_featured(self, db: AsyncSession, note_id: int, is_featured: bool) -> int:
        """
        设置精选状态（管理员功能）

        :param db: 数据库会话
        :param note_id: 笔记 ID
        :param is_featured: 是否精选
        :return:
        """
        from datetime import datetime

        update_data: dict = {'is_featured': is_featured}
        if is_featured:
            update_data['featured_time'] = datetime.now()
        else:
            update_data['featured_time'] = None

        return await self.update_model(db, note_id, update_data)

    async def get_select(
        self,
        user_id: int | None = None,
        question_id: int | None = None,
        is_public: bool | None = None,
        is_featured: bool | None = None,
    ) -> Select:
        """
        获取笔记列表查询表达式

        :param user_id: 用户 ID
        :param question_id: 题目 ID
        :param is_public: 是否公开
        :param is_featured: 是否精选
        :return:
        """
        stmt = select(QuestionNote)

        if user_id is not None:
            stmt = stmt.where(QuestionNote.user_id == user_id)
        if question_id is not None:
            stmt = stmt.where(QuestionNote.question_id == question_id)
        if is_public is not None:
            stmt = stmt.where(QuestionNote.is_public == is_public)
        if is_featured is not None:
            stmt = stmt.where(QuestionNote.is_featured == is_featured)

        stmt = stmt.order_by(QuestionNote.quality_score.desc())
        return stmt


class CRUDUserNoteVote(CRUDPlus[UserNoteVote]):
    """笔记投票数据库操作类"""

    async def get_vote(self, db: AsyncSession, user_id: int, note_id: int) -> UserNoteVote | None:
        """
        获取用户对笔记的投票

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param note_id: 笔记 ID
        :return:
        """
        return await self.select_model_by_column(db, user_id=user_id, note_id=note_id)

    async def vote(self, db: AsyncSession, user_id: int, note_id: int, vote_value: int) -> UserNoteVote:
        """
        投票（新增或更新）

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param note_id: 笔记 ID
        :param vote_value: 投票值（1=点赞，-1=点踩）
        :return:
        """
        existing_vote = await self.get_vote(db, user_id, note_id)

        if existing_vote:
            await self.update_model_by_column(db, {'vote_value': vote_value}, user_id=user_id, note_id=note_id)
            await db.refresh(existing_vote)
            return existing_vote

        new_vote = self.model(user_id=user_id, note_id=note_id, vote_value=vote_value)
        db.add(new_vote)
        await db.flush()
        await db.refresh(new_vote)
        return new_vote

    async def cancel_vote(self, db: AsyncSession, user_id: int, note_id: int) -> int:
        """
        取消投票

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param note_id: 笔记 ID
        :return:
        """
        return await self.delete_model_by_column(db, user_id=user_id, note_id=note_id)

    async def get_note_vote_stats(self, db: AsyncSession, note_id: int) -> tuple[int, int]:
        """
        获取笔记的投票统计

        :param db: 数据库会话
        :param note_id: 笔记 ID
        :return: (点赞数, 点踩数)
        """
        stmt = select(
            func.sum(case((UserNoteVote.vote_value == 1, 1), else_=0)).label('like_count'),
            func.sum(case((UserNoteVote.vote_value == -1, 1), else_=0)).label('dislike_count'),
        ).where(UserNoteVote.note_id == note_id)

        result = await db.execute(stmt)
        row = result.first()

        return (row.like_count or 0, row.dislike_count or 0)


question_note_dao: CRUDQuestionNote = CRUDQuestionNote(QuestionNote)
user_note_vote_dao: CRUDUserNoteVote = CRUDUserNoteVote(UserNoteVote)
