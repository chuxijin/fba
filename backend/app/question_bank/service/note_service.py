#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.admin.model import User
from backend.app.question_bank.crud.crud_practice_session import practice_session_dao
from backend.app.question_bank.crud.crud_question import question_statistics_dao
from backend.app.question_bank.crud.crud_question_note import question_note_dao, user_note_vote_dao
from backend.app.question_bank.crud.crud_session_question import session_question_dao
from backend.app.question_bank.model import QuestionNote, SessionQuestion, UserNoteVote
from backend.app.question_bank.schema.note import (
    CreateQuestionNoteParam,
    GetQuestionNoteDetail,
    GetQuestionNoteListItem,
    NoteVoteStatistics,
    UpdateQuestionNoteParam,
)
from backend.app.question_bank.schema.question import UpdateQuestionStatisticsParam
from backend.app.question_bank.service.study_domain_service import StudyDomainQuestionFilter, study_domain_service
from backend.common.exception import errors
from backend.utils.sensitive_words import validate_no_sensitive_words


class NoteService:
    """笔记服务类"""

    @staticmethod
    async def _get_study_domain_filter(
        *,
        db: AsyncSession,
        study_domain: str | None,
    ) -> StudyDomainQuestionFilter | None:
        """
        获取领域过滤上下文

        :param db: 数据库会话
        :param study_domain: 领域编码
        :return:
        """
        if study_domain is None:
            return None
        return await study_domain_service.get_question_filter(db=db, code=study_domain)

    @staticmethod
    async def create_note(*, db: AsyncSession, user_id: int, obj: CreateQuestionNoteParam) -> QuestionNote:
        """
        创建题目笔记

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param obj: 笔记参数
        :return:
        """
        from backend.app.question_bank.model.question import QuestionPlacement

        validate_no_sensitive_words(obj.content, '笔记内容')

        placement_stmt = (
            select(QuestionPlacement)
            .options(
                selectinload(QuestionPlacement.bank),
                selectinload(QuestionPlacement.chapter),
            )
            .where(
                QuestionPlacement.question_id == obj.question_id,
                QuestionPlacement.is_active.is_(True),
            )
        )
        if obj.placement_id is not None:
            placement_stmt = placement_stmt.where(QuestionPlacement.id == obj.placement_id)
        else:
            placement_stmt = placement_stmt.order_by(QuestionPlacement.sort_order, QuestionPlacement.id)

        placement_stmt = placement_stmt.limit(1)
        placement_result = await db.execute(placement_stmt)
        placement = placement_result.scalars().first()

        if obj.placement_id is not None and placement is None:
            raise errors.NotFoundError(msg='挂载不存在或不属于当前题目')

        note_dict = obj.model_dump(exclude={'placement_id'})
        if placement:
            note_dict['bank_id'] = placement.bank_id
            note_dict['bank_name'] = placement.bank.name if placement.bank else None
            note_dict['chapter_id'] = placement.chapter_id
            note_dict['chapter_name'] = placement.chapter.name if placement.chapter else None

        existing_note = await question_note_dao.get_by_user_and_question(
            db=db,
            user_id=user_id,
            question_id=obj.question_id,
        )
        if existing_note:
            await question_note_dao.update(db=db, note_id=existing_note.id, **note_dict)
            updated_note = await question_note_dao.get(db=db, note_id=existing_note.id)
            if not updated_note:
                raise errors.NotFoundError(msg='笔记不存在')
            return updated_note

        note_dict['user_id'] = user_id
        note_dict['created_by'] = user_id
        new_note = await question_note_dao.create(db=db, obj_dict=note_dict)

        await question_statistics_dao.update_stats(
            db,
            obj.question_id,
            UpdateQuestionStatisticsParam(note_delta=1),
        )
        return new_note

    @staticmethod
    async def get_note(*, db: AsyncSession, note_id: int, user_id: int) -> QuestionNote:
        """
        获取笔记详情

        :param db: 数据库会话
        :param note_id: 笔记 ID
        :param user_id: 用户 ID
        :return:
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
        *,
        db: AsyncSession,
        question_id: int,
        is_featured: bool | None = None,
    ) -> list[GetQuestionNoteListItem]:
        """
        获取题目公开笔记

        :param db: 数据库会话
        :param question_id: 题目 ID
        :param is_featured: 是否只看精选
        :return:
        """
        notes = await question_note_dao.get_public_notes(
            db=db,
            question_id=question_id,
            is_featured=is_featured,
        )
        if not notes:
            return []

        user_ids = list({note.user_id for note in notes})
        stmt = select(User).where(User.id.in_(user_ids))
        result = await db.execute(stmt)
        users = {user.id: user for user in result.scalars().all()}

        note_list: list[GetQuestionNoteListItem] = []
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
        *,
        db: AsyncSession,
        note_id: int,
        user_id: int,
        obj: UpdateQuestionNoteParam,
    ) -> int:
        """
        更新笔记

        :param db: 数据库会话
        :param note_id: 笔记 ID
        :param user_id: 用户 ID
        :param obj: 更新参数
        :return:
        """
        note = await question_note_dao.get(db=db, note_id=note_id)
        if not note:
            raise errors.NotFoundError(msg='笔记不存在')
        if note.user_id != user_id:
            raise errors.AuthorizationError(msg='无权操作此笔记')

        update_data = obj.model_dump(exclude_none=True)
        if not update_data:
            return 0

        validate_no_sensitive_words(update_data.get('content'), '笔记内容')

        return await question_note_dao.update(db=db, note_id=note_id, **update_data)

    @staticmethod
    async def delete_note(*, db: AsyncSession, note_id: int, user_id: int) -> int:
        """
        删除笔记

        :param db: 数据库会话
        :param note_id: 笔记 ID
        :param user_id: 用户 ID
        :return:
        """
        note = await question_note_dao.get(db=db, note_id=note_id)
        if not note:
            raise errors.NotFoundError(msg='笔记不存在')
        if note.user_id != user_id:
            raise errors.AuthorizationError(msg='无权操作此笔记')

        count = await question_note_dao.delete(db=db, note_id=note_id)
        if count > 0:
            await question_statistics_dao.update_stats(
                db,
                note.question_id,
                UpdateQuestionStatisticsParam(note_delta=-1),
            )

        return count

    @staticmethod
    async def vote_note(*, db: AsyncSession, note_id: int, user_id: int, vote_value: int) -> None:
        """
        笔记投票

        :param db: 数据库会话
        :param note_id: 笔记 ID
        :param user_id: 用户 ID
        :param vote_value: 投票值
        :return:
        """
        note = await question_note_dao.get(db=db, note_id=note_id)
        if not note:
            raise errors.NotFoundError(msg='笔记不存在')
        if not note.is_public:
            raise errors.ForbiddenError(msg='不能对私密笔记投票')

        _, previous_vote_value = await user_note_vote_dao.vote(
            db=db,
            user_id=user_id,
            note_id=note_id,
            vote_value=vote_value,
        )
        if previous_vote_value == vote_value:
            return

        like_delta = 0
        dislike_delta = 0
        if previous_vote_value == 1:
            like_delta -= 1
        elif previous_vote_value == -1:
            dislike_delta -= 1

        if vote_value == 1:
            like_delta += 1
        else:
            dislike_delta += 1

        await question_note_dao.adjust_vote_stats(
            db=db,
            note_id=note_id,
            like_delta=like_delta,
            dislike_delta=dislike_delta,
        )

    @staticmethod
    async def cancel_vote(*, db: AsyncSession, note_id: int, user_id: int) -> int:
        """
        取消投票

        :param db: 数据库会话
        :param note_id: 笔记 ID
        :param user_id: 用户 ID
        :return:
        """
        previous_vote_value = await user_note_vote_dao.cancel_vote(
            db=db,
            user_id=user_id,
            note_id=note_id,
        )
        if previous_vote_value is None:
            return 0

        await question_note_dao.adjust_vote_stats(
            db=db,
            note_id=note_id,
            like_delta=-1 if previous_vote_value == 1 else 0,
            dislike_delta=-1 if previous_vote_value == -1 else 0,
        )
        return 1

    @staticmethod
    async def get_my_vote(*, db: AsyncSession, note_id: int, user_id: int) -> UserNoteVote:
        """
        获取我的投票

        :param db: 数据库会话
        :param note_id: 笔记 ID
        :param user_id: 用户 ID
        :return:
        """
        vote = await user_note_vote_dao.get_vote(db=db, user_id=user_id, note_id=note_id)
        if not vote:
            raise errors.NotFoundError(msg='未对该笔记投票')

        return vote

    @staticmethod
    async def get_vote_statistics(*, db: AsyncSession, note_id: int) -> NoteVoteStatistics:
        """
        获取投票统计

        :param db: 数据库会话
        :param note_id: 笔记 ID
        :return:
        """
        note = await question_note_dao.get(db=db, note_id=note_id)
        if not note:
            raise errors.NotFoundError(msg='笔记不存在')

        like_count = int(note.like_count or 0)
        dislike_count = int(note.dislike_count or 0)
        return NoteVoteStatistics(
            like_count=like_count,
            dislike_count=dislike_count,
            quality_score=like_count - dislike_count,
        )

    @staticmethod
    async def _get_owned_session_question_ids(*, db: AsyncSession, user_id: int, session_id: int) -> list[int]:
        """
        获取当前用户会话内题目 ID 列表

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param session_id: 会话 ID
        :return:
        """
        session = await practice_session_dao.get(db=db, session_id=session_id)
        if not session:
            raise errors.NotFoundError(msg='会话不存在')
        if session.user_id != user_id:
            raise errors.AuthorizationError(msg='无权访问此会话')

        session_questions = await session_question_dao.list_by_session(db=db, session_id=session_id)
        return [item.question_id for item in session_questions]

    @staticmethod
    async def batch_get_notes_by_session(
        *,
        db: AsyncSession,
        user_id: int,
        session_id: int,
    ) -> dict[int, 'GetQuestionNoteDetail']:
        """
        通过会话批量查询题目笔记（单条 JOIN SQL，跳过会话题目 ORM 加载）

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param session_id: 会话 ID
        :return:
        """
        note_model = question_note_dao.model
        stmt = (
            select(note_model)
            .join(
                SessionQuestion,
                and_(
                    SessionQuestion.question_id == note_model.question_id,
                    SessionQuestion.session_id == session_id,
                ),
            )
            .where(note_model.user_id == user_id)
            .order_by(
                note_model.updated_time.desc(),
                note_model.id.desc(),
            )
        )
        result = await db.execute(stmt)
        notes = result.scalars().all()

        note_map: dict[int, GetQuestionNoteDetail] = {}
        for note in notes:
            if note.question_id in note_map:
                continue
            note_map[note.question_id] = GetQuestionNoteDetail.model_validate(note)

        return note_map

    @staticmethod
    async def batch_get_notes_from_string(
        *,
        db: AsyncSession,
        user_id: int,
        question_ids_str: str,
    ) -> dict[int, 'GetQuestionNoteDetail | None']:
        """
        批量查询题目笔记

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param question_ids_str: 题目 ID 字符串
        :return:
        """
        try:
            ids = [int(qid.strip()) for qid in question_ids_str.split(',') if qid.strip()]
        except ValueError:
            raise errors.BadRequestError(msg='题目 ID 格式错误')

        if not ids:
            return {}

        stmt = (
            select(question_note_dao.model)
            .where(
                question_note_dao.model.user_id == user_id,
                question_note_dao.model.question_id.in_(ids),
            )
            .order_by(
                question_note_dao.model.updated_time.desc(),
                question_note_dao.model.id.desc(),
            )
        )
        result = await db.execute(stmt)
        notes = result.scalars().all()

        note_map: dict[int, GetQuestionNoteDetail | None] = {qid: None for qid in ids}
        for note in notes:
            if note_map[note.question_id] is not None:
                continue
            note_map[note.question_id] = GetQuestionNoteDetail.model_validate(note)

        return note_map

    @staticmethod
    async def get_statistics(
        *,
        db: AsyncSession,
        user_id: int,
        study_domain: str | None = None,
    ) -> dict:
        """
        获取笔记统计数据

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param study_domain: 领域编码
        :return:
        """
        domain_filter = await NoteService._get_study_domain_filter(db=db, study_domain=study_domain)
        if domain_filter:
            return await question_note_dao.get_statistics_by_bank_ids(
                db=db,
                user_id=user_id,
                bank_ids=domain_filter.bank_ids,
            )
        return await question_note_dao.get_statistics(db=db, user_id=user_id)

    @staticmethod
    async def get_grouped(
        *,
        db: AsyncSession,
        user_id: int,
        group_by: str,
        study_domain: str | None = None,
    ) -> list[dict]:
        """
        获取分组统计

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param group_by: 分组方式
        :return:
        """
        domain_filter = await NoteService._get_study_domain_filter(db=db, study_domain=study_domain)
        if group_by == 'knowledge_point':
            rows = await question_note_dao.get_grouped_by_knowledge_point(db=db, user_id=user_id)
            if not domain_filter:
                return rows
            return [
                item for item in rows
                if str(item['group_name'] or '').strip() in domain_filter.knowledge_names
            ]

        rows = await question_note_dao.get_grouped_by_bank(db=db, user_id=user_id)
        if not domain_filter:
            return rows
        return [
            item for item in rows
            if item['group_id'] is not None and int(item['group_id']) in domain_filter.bank_ids
        ]

    @staticmethod
    async def get_statistics_with_groups(
        *,
        db: AsyncSession,
        user_id: int,
        group_by: str = 'knowledge_point',
        study_domain: str | None = None,
    ) -> dict:
        """
        获取统计和树形分组

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param group_by: 分组方式
        :return:
        """
        from backend.app.question_bank.service.group_tree import (
            build_bank_tree,
            build_kp_tree,
            load_banks_and_chapters,
            load_kp_categories,
        )

        domain_filter = await NoteService._get_study_domain_filter(db=db, study_domain=study_domain)
        stats = await NoteService.get_statistics(db=db, user_id=user_id, study_domain=study_domain)

        if group_by == 'knowledge_point':
            flat_counts = await question_note_dao.get_grouped_by_knowledge_point(db=db, user_id=user_id)
            if domain_filter:
                flat_counts = [
                    item for item in flat_counts
                    if str(item['group_name'] or '').strip() in domain_filter.knowledge_names
                ]
            count_map = {item['group_name']: item['count'] for item in flat_counts}
            categories = await load_kp_categories(db)
            groups = build_kp_tree(categories, count_map)
        else:
            flat_counts = await question_note_dao.get_bank_chapter_counts(db=db, user_id=user_id)
            if domain_filter:
                flat_counts = [
                    row for row in flat_counts
                    if row['bank_id'] is not None and int(row['bank_id']) in domain_filter.bank_ids
                ]
            count_map = {(row['bank_id'], row['chapter_id']): row['count'] for row in flat_counts}
            bank_ids = {row['bank_id'] for row in flat_counts if row['bank_id'] is not None}
            chapter_ids = {row['chapter_id'] for row in flat_counts if row['chapter_id'] is not None}
            banks, chapters = await load_banks_and_chapters(db, bank_ids, chapter_ids)
            groups = build_bank_tree(banks, chapters, count_map)

        return {
            'total_count': stats['total'],
            'public_count': stats['public_count'],
            'featured_count': stats['featured_count'],
            'groups': groups,
        }


note_service = NoteService()
