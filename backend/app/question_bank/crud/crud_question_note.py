#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import case, cast, func, literal_column, or_, select, update as sa_update
from sqlalchemy.dialects.postgresql import JSONB as PGJSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.question_bank.model import QuestionNote, UserNoteVote
from backend.app.question_bank.model.question import Question


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
    ) -> QuestionNote | None:
        """
        获取用户在特定题目下的笔记

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param question_id: 题目 ID
        :return:
        """
        stmt = await self.select_order('updated_time', 'desc', user_id=user_id, question_id=question_id)
        result = await db.execute(stmt)
        return result.scalars().first()

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

    async def adjust_vote_stats(
        self,
        db: AsyncSession,
        note_id: int,
        like_delta: int = 0,
        dislike_delta: int = 0,
    ) -> int:
        """
        澧為噺鏇存柊鎶曠エ缁熻

        :param db: 鏁版嵁搴撲細璇?
        :param note_id: 绗旇 ID
        :param like_delta: 鐐硅禐澧為噺
        :param dislike_delta: 鐐硅俯澧為噺
        :return:
        """
        if like_delta == 0 and dislike_delta == 0:
            return 0

        stmt = (
            sa_update(QuestionNote)
            .where(QuestionNote.id == note_id)
            .values(
                like_count=QuestionNote.like_count + like_delta,
                dislike_count=QuestionNote.dislike_count + dislike_delta,
                quality_score=QuestionNote.quality_score + like_delta - dislike_delta,
            )
        )
        result = await db.execute(stmt)
        return result.rowcount

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

    # ============ 分组聚合 ============

    async def get_grouped_by_bank(self, db: AsyncSession, user_id: int) -> list[dict]:
        """
        按题库分组聚合笔记数量（利用冗余字段）

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        stmt = (
            select(
                QuestionNote.bank_id.label('group_id'),
                QuestionNote.bank_name.label('group_name'),
                func.count().label('count'),
            )
            .where(
                QuestionNote.user_id == user_id,
                QuestionNote.bank_id.isnot(None),
            )
            .group_by(QuestionNote.bank_id, QuestionNote.bank_name)
            .order_by(func.count().desc())
        )
        rows = (await db.execute(stmt)).all()
        return [{'group_id': r.group_id, 'group_name': r.group_name or '未分类', 'count': r.count} for r in rows]

    async def get_grouped_by_knowledge_point(self, db: AsyncSession, user_id: int) -> list[dict]:
        """
        按知识点分组聚合笔记数量

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        kp_element = func.jsonb_array_elements(Question.knowledge_point).table_valued('value')
        kp_name = func.coalesce(
            kp_element.c.value.op('->>')(literal_column("'name'")),
            kp_element.c.value.op('->>')(literal_column("'label'")),
            kp_element.c.value.op('->>')(literal_column("'title'")),
            kp_element.c.value.op('#>>')(literal_column("'{}'")),
        ).label('kp_name')

        stmt = (
            select(
                kp_name,
                func.count(func.distinct(QuestionNote.id)).label('count'),
            )
            .select_from(QuestionNote)
            .join(Question, Question.id == QuestionNote.question_id)
            .join(kp_element, literal_column('true'))
            .where(
                QuestionNote.user_id == user_id,
                Question.knowledge_point.isnot(None),
            )
            .group_by(kp_name)
            .having(kp_name.isnot(None))
            .order_by(func.count(func.distinct(QuestionNote.id)).desc())
        )
        rows = (await db.execute(stmt)).all()
        return [{'group_id': None, 'group_name': r.kp_name, 'count': r.count} for r in rows]

    async def get_bank_chapter_counts(self, db: AsyncSession, user_id: int) -> list[dict]:
        """
        按 bank_id + chapter_id 分组统计笔记数

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        stmt = (
            select(
                QuestionNote.bank_id,
                QuestionNote.chapter_id,
                func.count().label('count'),
            )
            .where(QuestionNote.user_id == user_id)
            .group_by(QuestionNote.bank_id, QuestionNote.chapter_id)
        )
        rows = (await db.execute(stmt)).all()
        return [{'bank_id': r.bank_id, 'chapter_id': r.chapter_id, 'count': r.count} for r in rows]

    async def get_question_ids(
        self, db: AsyncSession, user_id: int,
        bank_id: int | None = None, chapter_id: int | None = None, knowledge_point: str | None = None,
    ) -> list[int]:
        """
        按分组条件获取有笔记的题目 ID 列表

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param bank_id: 题库 ID
        :param chapter_id: 章节 ID
        :param knowledge_point: 知识点名称
        :return:
        """
        stmt = (
            select(QuestionNote.question_id)
            .where(QuestionNote.user_id == user_id)
            .distinct()
            .order_by(QuestionNote.question_id)
        )

        if bank_id is not None:
            stmt = stmt.where(QuestionNote.bank_id == bank_id)

        if chapter_id is not None:
            stmt = stmt.where(QuestionNote.chapter_id == chapter_id)

        if knowledge_point is not None:
            stmt = stmt.join(Question, Question.id == QuestionNote.question_id)
            kp_col = cast(Question.knowledge_point, PGJSONB)
            stmt = stmt.where(
                or_(
                    kp_col.contains([knowledge_point]),
                    kp_col.contains([{'name': knowledge_point}]),
                    kp_col.contains([{'label': knowledge_point}]),
                    kp_col.contains([{'title': knowledge_point}]),
                )
            )

        rows = (await db.execute(stmt)).scalars().all()
        return list(rows)

    async def get_statistics(self, db: AsyncSession, user_id: int) -> dict:
        """
        获取用户笔记统计数据

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        stmt = (
            select(
                func.count().label('total'),
                func.sum(case((QuestionNote.is_public == True, 1), else_=0)).label('public_count'),  # noqa: E712
                func.sum(case((QuestionNote.is_featured == True, 1), else_=0)).label('featured_count'),  # noqa: E712
            )
            .where(QuestionNote.user_id == user_id)
        )
        row = (await db.execute(stmt)).one()
        return {
            'total': row.total or 0,
            'public_count': int(row.public_count or 0),
            'featured_count': int(row.featured_count or 0),
        }


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

    async def vote(self, db: AsyncSession, user_id: int, note_id: int, vote_value: int) -> tuple[UserNoteVote, int | None]:
        """
        投票（新增或更新）

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param note_id: 笔记 ID
        :param vote_value: 投票值（1=点赞，-1=点踩）
        :return:
        """
        existing_vote = await self.get_vote(db, user_id, note_id)
        previous_vote_value = existing_vote.vote_value if existing_vote else None

        if existing_vote:
            if existing_vote.vote_value == vote_value:
                return existing_vote, previous_vote_value

            await self.update_model_by_column(db, {'vote_value': vote_value}, user_id=user_id, note_id=note_id)
            existing_vote.vote_value = vote_value
            return existing_vote, previous_vote_value

        new_vote = self.model(user_id=user_id, note_id=note_id, vote_value=vote_value)
        db.add(new_vote)
        await db.flush()
        await db.refresh(new_vote)
        return new_vote, previous_vote_value

    async def cancel_vote(self, db: AsyncSession, user_id: int, note_id: int) -> int | None:
        """
        取消投票

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param note_id: 笔记 ID
        :return:
        """
        existing_vote = await self.get_vote(db, user_id, note_id)
        if not existing_vote:
            return None

        vote_value = existing_vote.vote_value
        await db.delete(existing_vote)
        await db.flush()
        return vote_value

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
