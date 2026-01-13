#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.question_bank.crud.crud_question_note import question_note_dao, user_note_vote_dao
from backend.app.question_bank.model import QuestionNote, UserAccount, UserNoteVote
from backend.app.question_bank.schema.note import (
    CreateQuestionNoteParam,
    GetQuestionNoteListItem,
    NoteVoteStatistics,
)
from backend.common.exception import errors


class NoteService:
    """笔记服务类"""

    @staticmethod
    async def create_note(*, db: AsyncSession, user_id: int, obj: CreateQuestionNoteParam) -> QuestionNote:
        """
        创建题目笔记

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param obj: 笔记参数
        :return: 笔记记录
        """
        note_dict = obj.model_dump()
        note_dict['user_id'] = user_id
        note_dict['created_by'] = user_id

        new_note = await question_note_dao.create(db=db, obj_dict=note_dict)
        return new_note

    @staticmethod
    async def get_note(*, db: AsyncSession, note_id: int, user_id: int) -> QuestionNote:
        """
        获取笔记详情

        :param db: 数据库会话
        :param note_id: 笔记 ID
        :param user_id: 当前用户 ID
        :return: 笔记记录
        """
        note = await question_note_dao.get(db=db, note_id=note_id)
        if not note:
            raise errors.NotFoundError(msg='笔记不存在')

        if not note.is_public and note.user_id != user_id:
            raise errors.AuthorizationError(msg='无权访问此笔记')

        if note.is_public and note.user_id != user_id:
            await question_note_dao.increment_view(db=db, note_id=note_id)

        return note

    @staticmethod
    async def get_question_public_notes(
        *, db: AsyncSession, question_id: int, is_featured: bool | None = None
    ) -> list[GetQuestionNoteListItem]:
        """
        获取题目的公开笔记（按质量分排序）

        :param db: 数据库会话
        :param question_id: 题目 ID
        :param is_featured: 是否只看精选
        :return: 笔记列表（含用户信息）
        """
        notes = await question_note_dao.get_public_notes(db=db, question_id=question_id, is_featured=is_featured)

        if not notes:
            return []

        user_ids = list({note.user_id for note in notes})
        stmt = select(UserAccount).where(UserAccount.id.in_(user_ids))
        result = await db.execute(stmt)
        users = {user.id: user for user in result.scalars().all()}

        note_list = []
        for note in notes:
            note_dict = GetQuestionNoteListItem.model_validate(note).model_dump()
            user = users.get(note.user_id)
            if user:
                note_dict['user_nickname'] = user.nickname
                note_dict['user_avatar'] = user.avatar
            note_list.append(GetQuestionNoteListItem(**note_dict))

        return note_list

    @staticmethod
    async def update_note(
        *, db: AsyncSession, note_id: int, user_id: int, content: str, is_public: bool
    ) -> int:
        """
        更新笔记内容和公开状态

        :param db: 数据库会话
        :param note_id: 笔记 ID
        :param user_id: 用户 ID
        :param content: 笔记内容
        :param is_public: 是否公开
        :return: 更新数量
        """
        note = await question_note_dao.get(db=db, note_id=note_id)
        if not note:
            raise errors.NotFoundError(msg='笔记不存在')
        if note.user_id != user_id:
            raise errors.AuthorizationError(msg='无权操作此笔记')

        count = await question_note_dao.update(db=db, note_id=note_id, content=content, is_public=is_public)
        return count

    @staticmethod
    async def delete_note(*, db: AsyncSession, note_id: int, user_id: int) -> int:
        """
        删除笔记

        :param db: 数据库会话
        :param note_id: 笔记 ID
        :param user_id: 用户 ID
        :return: 删除数量
        """
        note = await question_note_dao.get(db=db, note_id=note_id)
        if not note:
            raise errors.NotFoundError(msg='笔记不存在')
        if note.user_id != user_id:
            raise errors.AuthorizationError(msg='无权操作此笔记')

        count = await question_note_dao.delete(db=db, note_id=note_id)
        return count

    @staticmethod
    async def vote_note(*, db: AsyncSession, note_id: int, user_id: int, vote_value: int) -> None:
        """
        对笔记投票（点赞/点踩）

        :param db: 数据库会话
        :param note_id: 笔记 ID
        :param user_id: 用户 ID
        :param vote_value: 投票值（1=点赞，-1=点踩）
        """
        note = await question_note_dao.get(db=db, note_id=note_id)
        if not note:
            raise errors.NotFoundError(msg='笔记不存在')
        if not note.is_public:
            raise errors.ForbiddenError(msg='不能对私密笔记投票')

        if vote_value not in [1, -1]:
            raise errors.BadRequestError(msg='投票值必须是 1（点赞）或 -1（点踩）')

        await user_note_vote_dao.vote(db=db, user_id=user_id, note_id=note_id, vote_value=vote_value)

        like_count, dislike_count = await user_note_vote_dao.get_note_vote_stats(db=db, note_id=note_id)
        await question_note_dao.update_vote_stats(
            db=db, note_id=note_id, like_count=like_count, dislike_count=dislike_count
        )

    @staticmethod
    async def cancel_vote(*, db: AsyncSession, note_id: int, user_id: int) -> int:
        """
        取消对笔记的投票

        :param db: 数据库会话
        :param note_id: 笔记 ID
        :param user_id: 用户 ID
        :return: 删除数量
        """
        count = await user_note_vote_dao.cancel_vote(db=db, user_id=user_id, note_id=note_id)

        if count > 0:
            like_count, dislike_count = await user_note_vote_dao.get_note_vote_stats(db=db, note_id=note_id)
            await question_note_dao.update_vote_stats(
                db=db, note_id=note_id, like_count=like_count, dislike_count=dislike_count
            )

        return count

    @staticmethod
    async def get_my_vote(*, db: AsyncSession, note_id: int, user_id: int) -> UserNoteVote:
        """
        获取当前用户对笔记的投票状态

        :param db: 数据库会话
        :param note_id: 笔记 ID
        :param user_id: 用户 ID
        :return: 投票记录
        """
        vote = await user_note_vote_dao.get_vote(db=db, user_id=user_id, note_id=note_id)
        if not vote:
            raise errors.NotFoundError(msg='未对此笔记投票')

        return vote

    @staticmethod
    async def get_vote_statistics(*, db: AsyncSession, note_id: int) -> NoteVoteStatistics:
        """
        获取笔记的投票统计数据

        :param db: 数据库会话
        :param note_id: 笔记 ID
        :return: 投票统计
        """
        like_count, dislike_count = await user_note_vote_dao.get_note_vote_stats(db=db, note_id=note_id)
        stats = NoteVoteStatistics(
            like_count=like_count, dislike_count=dislike_count, quality_score=like_count - dislike_count
        )
        return stats

    @staticmethod
    async def batch_get_notes_from_string(
        *, db: AsyncSession, user_id: int, question_ids_str: str
    ) -> dict[int, 'GetQuestionNoteDetail | None']:
        """
        批量查询题目的笔记（从逗号分隔的字符串）

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param question_ids_str: 题目 ID 列表（逗号分隔）
        :return: 字典 {question_id: QuestionNote | None}
        """
        from backend.app.question_bank.schema.note import GetQuestionNoteDetail

        try:
            ids = [int(qid.strip()) for qid in question_ids_str.split(',') if qid.strip()]
        except ValueError:
            raise errors.BadRequestError(msg='题目 ID 格式错误')

        if not ids:
            return {}

        stmt = select(question_note_dao.model).where(
            question_note_dao.model.user_id == user_id,
            question_note_dao.model.question_id.in_(ids),
        )
        result = await db.execute(stmt)
        notes = result.scalars().all()

        note_map: dict[int, GetQuestionNoteDetail | None] = {qid: None for qid in ids}
        for note in notes:
            note_map[note.question_id] = GetQuestionNoteDetail.model_validate(note)

        return note_map


note_service = NoteService()
