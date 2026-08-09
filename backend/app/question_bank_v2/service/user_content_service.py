from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.question_bank_v2.crud.crud_composition import bank_item_dao
from backend.app.question_bank_v2.crud.crud_practice import practice_session_dao
from backend.app.question_bank_v2.crud.crud_question import question_dao
from backend.app.question_bank_v2.crud.crud_user_content import (
    favorite_folder_dao,
    question_favorite_dao,
    question_note_dao,
    question_note_vote_dao,
)
from backend.app.question_bank_v2.schema.user_content import (
    ContentGroupNode,
    CreateFavoriteFolderParam,
    CreateQuestionFavoriteParam,
    CreateQuestionNoteParam,
    FavoriteStatistics,
    GetFavoriteFolderDetail,
    GetQuestionFavoriteDetail,
    GetQuestionNoteDetail,
    NoteStatistics,
    QuestionNoteVoteParam,
    UpdateFavoriteFolderParam,
    UpdateQuestionFavoriteParam,
    UpdateQuestionNoteParam,
)
from backend.app.question_bank_v2.service.content_group_service import content_group_service
from backend.app.question_bank_v2.service.knowledge_service import knowledge_service
from backend.common.exception import errors
from backend.utils.timezone import timezone


class UserContentService:
    """收藏、笔记等用户题目内容服务类"""

    @staticmethod
    async def _resolve_question_context(
        *,
        db: AsyncSession,
        user_id: int,
        question_id: int,
        bank_item_id: int | None,
    ) -> None:
        """校验题目存在且用户可访问"""
        question = await question_dao.get(db, question_id)
        if question is None or question.status != 'active':
            raise errors.NotFoundError(msg='题目不存在或不可用')
        if question.visibility == 'private' and question.owner_id != user_id:
            raise errors.ForbiddenError(msg='无权访问该私有题目')
        if bank_item_id is not None:
            bank_item = await bank_item_dao.get(db, bank_item_id)
            if (
                bank_item is None
                or bank_item.question_id != question_id
            ):
                raise errors.RequestError(msg='题库编排上下文与题目不一致')

    @staticmethod
    async def _ensure_folder(*, db: AsyncSession, user_id: int, folder_id: int | None) -> None:
        """校验收藏夹属于当前用户且仍启用"""
        if folder_id is None:
            return
        folder = await favorite_folder_dao.get(db, folder_id, user_id=user_id)
        if folder is None:
            raise errors.NotFoundError(msg='收藏夹不存在')
        if folder.status != 'active':
            raise errors.ConflictError(msg='已归档收藏夹不能接收新收藏')

    @staticmethod
    def _build_groups(*, rows: list[dict[str, Any]], group_by: str) -> list[ContentGroupNode]:
        """将知识点统计行组装成客户端分组"""
        return [ContentGroupNode(id=row['id'], name=row['name'], count=int(row['count'] or 0)) for row in rows]

    @staticmethod
    def _favorite_detail(row: dict[str, Any] | None) -> GetQuestionFavoriteDetail:
        """校验并构建收藏聚合详情"""
        if row is None:
            raise errors.NotFoundError(msg='收藏不存在')
        return GetQuestionFavoriteDetail(**row)

    @staticmethod
    def _note_detail(row: dict[str, Any] | None) -> GetQuestionNoteDetail:
        """校验并构建笔记聚合详情"""
        if row is None:
            raise errors.NotFoundError(msg='笔记不存在')
        return GetQuestionNoteDetail(**row, is_public=row['visibility'] == 'public')

    @staticmethod
    async def get_folders(*, db: AsyncSession, user_id: int) -> list[GetFavoriteFolderDetail]:
        """获取当前用户全部收藏夹"""
        rows = await favorite_folder_dao.get_all(db, user_id=user_id)
        return [GetFavoriteFolderDetail(**row) for row in rows]

    @staticmethod
    async def create_folder(
        *,
        db: AsyncSession,
        user_id: int,
        obj: CreateFavoriteFolderParam,
    ) -> GetFavoriteFolderDetail:
        """创建用户收藏夹"""
        name = obj.name.strip()
        if await favorite_folder_dao.get_by_name(db, user_id=user_id, name=name):
            raise errors.ConflictError(msg='收藏夹名称已存在')
        folder = await favorite_folder_dao.create(
            db,
            user_id=user_id,
            data={**obj.model_dump(), 'name': name},
        )
        return GetFavoriteFolderDetail(
            id=folder.id,
            name=folder.name,
            description=folder.description,
            sort_order=folder.sort_order,
            status=folder.status,
            favorite_count=0,
            created_time=folder.created_time,
            updated_time=folder.updated_time,
        )

    @staticmethod
    async def update_folder(
        *,
        db: AsyncSession,
        user_id: int,
        folder_id: int,
        obj: UpdateFavoriteFolderParam,
    ) -> GetFavoriteFolderDetail:
        """更新用户收藏夹"""
        folder = await favorite_folder_dao.get(db, folder_id, user_id=user_id)
        if folder is None:
            raise errors.NotFoundError(msg='收藏夹不存在')
        data = obj.model_dump(exclude_unset=True)
        if 'name' in data:
            data['name'] = data['name'].strip()
            existing = await favorite_folder_dao.get_by_name(db, user_id=user_id, name=data['name'])
            if existing is not None and existing.id != folder_id:
                raise errors.ConflictError(msg='收藏夹名称已存在')
        if data:
            data['updated_by'] = user_id
            await favorite_folder_dao.update(db, folder_id, user_id=user_id, data=data)
        rows = await favorite_folder_dao.get_all(db, user_id=user_id)
        row = next((item for item in rows if item['id'] == folder_id), None)
        if row is None:
            raise errors.NotFoundError(msg='收藏夹不存在')
        return GetFavoriteFolderDetail(**row)

    @staticmethod
    async def delete_folder(*, db: AsyncSession, user_id: int, folder_id: int) -> None:
        """删除收藏夹并将其中收藏移到未分组"""
        folder = await favorite_folder_dao.get(db, folder_id, user_id=user_id)
        if folder is None:
            return
        await favorite_folder_dao.clear_favorites(db, folder_id=folder_id, user_id=user_id)
        await favorite_folder_dao.delete_model(db, folder_id)

    @staticmethod
    async def get_favorites_select(
        *,
        db: AsyncSession,
        user_id: int,
        folder_id: int | None,
    ) -> Any:
        """校验收藏夹并构建当前用户收藏查询"""
        if folder_id is not None:
            await UserContentService._ensure_folder(db=db, user_id=user_id, folder_id=folder_id)
        return question_favorite_dao.get_list_select(
            user_id=user_id,
            folder_id=folder_id,
        )

    @staticmethod
    async def create_favorite(
        *,
        db: AsyncSession,
        user_id: int,
        obj: CreateQuestionFavoriteParam,
    ) -> GetQuestionFavoriteDetail:
        """幂等收藏题目"""
        existing = await question_favorite_dao.get_by_question(
            db,
            user_id=user_id,
            question_id=obj.question_id,
        )
        if existing is not None:
            if existing.bank_item_id is None and obj.bank_item_id is not None:
                await UserContentService._resolve_question_context(
                    db=db,
                    user_id=user_id,
                    question_id=obj.question_id,
                    bank_item_id=obj.bank_item_id,
                )
                await question_favorite_dao.update(
                    db,
                    existing.id,
                    user_id=user_id,
                    data={'bank_item_id': obj.bank_item_id, 'updated_by': user_id},
                )
            return UserContentService._favorite_detail(
                await question_favorite_dao.get_detail(db, existing.id, user_id=user_id)
            )
        await UserContentService._ensure_folder(db=db, user_id=user_id, folder_id=obj.folder_id)
        await UserContentService._resolve_question_context(
            db=db,
            user_id=user_id,
            question_id=obj.question_id,
            bank_item_id=obj.bank_item_id,
        )
        now = timezone.now()
        favorite = await question_favorite_dao.create(
            db,
            user_id=user_id,
            data={
                'question_id': obj.question_id,
                'folder_id': obj.folder_id,
                'bank_item_id': obj.bank_item_id,
                'tags': obj.tags,
                'remark': obj.remark,
                'is_pinned': obj.is_pinned,
                'pinned_time': now if obj.is_pinned else None,
            },
        )
        return UserContentService._favorite_detail(
            await question_favorite_dao.get_detail(db, favorite.id, user_id=user_id)
        )

    @staticmethod
    async def update_favorite(
        *,
        db: AsyncSession,
        user_id: int,
        favorite_id: int,
        obj: UpdateQuestionFavoriteParam,
    ) -> GetQuestionFavoriteDetail:
        """更新收藏夹归属、标签、备注和置顶状态"""
        favorite = await question_favorite_dao.get(db, favorite_id, user_id=user_id)
        if favorite is None:
            raise errors.NotFoundError(msg='收藏不存在')
        data = obj.model_dump(exclude_unset=True)
        if 'folder_id' in obj.model_fields_set:
            await UserContentService._ensure_folder(db=db, user_id=user_id, folder_id=obj.folder_id)
        if obj.is_pinned is not None:
            data['pinned_time'] = timezone.now() if obj.is_pinned else None
        if data:
            data['updated_by'] = user_id
            await question_favorite_dao.update(db, favorite_id, user_id=user_id, data=data)
        return UserContentService._favorite_detail(
            await question_favorite_dao.get_detail(db, favorite_id, user_id=user_id)
        )

    @staticmethod
    async def delete_favorite_by_question(*, db: AsyncSession, user_id: int, question_id: int) -> None:
        """按题目幂等取消收藏"""
        favorite = await question_favorite_dao.get_by_question(
            db,
            user_id=user_id,
            question_id=question_id,
        )
        if favorite is not None:
            await question_favorite_dao.delete_model(db, favorite.id)

    @staticmethod
    async def get_session_favorites(
        *,
        db: AsyncSession,
        user_id: int,
        session_key: str,
    ) -> dict[int, bool]:
        """一次查询获取会话内已收藏题目"""
        session = await practice_session_dao.get_by_key(db, session_key, user_id=user_id)
        if session is None:
            raise errors.NotFoundError(msg='练习会话不存在')
        return await question_favorite_dao.get_session_states(db, session_id=session.id, user_id=user_id)

    @staticmethod
    async def _resolve_knowledge_system_ids(
        *,
        db: AsyncSession,
        user_id: int,
        group_by: str,
        knowledge_system_id: int | None,
        domain_category_id: int | None,
    ) -> list[int]:
        """按知识点分组时解析当前领域各科目生效的体系；其他分组方式无需解析"""
        if group_by != 'knowledge_point':
            return []
        resolved_domain_id = await knowledge_service.resolve_domain_category_id(
            db=db,
            user_id=user_id,
            domain_category_id=domain_category_id,
        )
        return await knowledge_service.resolve_system_ids(
            db=db,
            domain_category_id=resolved_domain_id,
            system_id=knowledge_system_id,
            user_id=user_id,
        )

    @staticmethod
    async def get_favorite_statistics(
        *,
        db: AsyncSession,
        user_id: int,
        group_by: str,
        knowledge_system_id: int | None = None,
        domain_category_id: int | None = None,
    ) -> FavoriteStatistics:
        """获取收藏汇总及题库或知识点分组"""
        stats = await question_favorite_dao.get_statistics(db, user_id=user_id)
        knowledge_system_ids = await UserContentService._resolve_knowledge_system_ids(
            db=db,
            user_id=user_id,
            group_by=group_by,
            knowledge_system_id=knowledge_system_id,
            domain_category_id=domain_category_id,
        )
        rows = await question_favorite_dao.get_group_counts(
            db,
            user_id=user_id,
            group_by=group_by,
            knowledge_system_ids=knowledge_system_ids,
        )
        groups = (
            UserContentService._build_groups(rows=rows, group_by=group_by)
            if group_by == 'knowledge_point'
            else await content_group_service.build_bank_tree(db=db, rows=rows, ungrouped_name='未归属题库')
        )
        return FavoriteStatistics(
            total_count=int(stats['total_count'] or 0),
            folder_count=int(stats['folder_count'] or 0),
            groups=groups,
        )

    @staticmethod
    def get_notes_select(
        *,
        user_id: int,
    ) -> Any:
        """构建当前用户笔记查询"""
        return question_note_dao.get_list_select(user_id=user_id)

    @staticmethod
    async def build_note_page(rows: list[Any]) -> list[GetQuestionNoteDetail]:
        """规范化一页笔记数据"""
        return [UserContentService._note_detail(row._mapping if hasattr(row, '_mapping') else row) for row in rows]

    @staticmethod
    async def create_note(
        *,
        db: AsyncSession,
        user_id: int,
        obj: CreateQuestionNoteParam,
    ) -> GetQuestionNoteDetail:
        """创建用户在题目上的唯一笔记"""
        if await question_note_dao.get_by_question(db, user_id=user_id, question_id=obj.question_id):
            raise errors.ConflictError(msg='该题目已存在笔记，请直接更新')
        await UserContentService._resolve_question_context(
            db=db,
            user_id=user_id,
            question_id=obj.question_id,
            bank_item_id=obj.bank_item_id,
        )
        note = await question_note_dao.create(
            db,
            user_id=user_id,
            data={
                **obj.model_dump(),
                'status': 'published' if obj.visibility == 'public' else 'draft',
            },
        )
        return UserContentService._note_detail(await question_note_dao.get_detail(db, note.id, viewer_id=user_id))

    @staticmethod
    async def update_note(
        *,
        db: AsyncSession,
        user_id: int,
        note_id: int,
        obj: UpdateQuestionNoteParam,
    ) -> GetQuestionNoteDetail:
        """更新用户自己的题目笔记"""
        note = await question_note_dao.get(db, note_id, user_id=user_id)
        if note is None:
            raise errors.NotFoundError(msg='笔记不存在')
        data = obj.model_dump(exclude_unset=True)
        if obj.visibility is not None:
            data['status'] = 'published' if obj.visibility == 'public' else 'draft'
        if data:
            data['updated_by'] = user_id
            await question_note_dao.update(db, note_id, user_id=user_id, data=data)
        return UserContentService._note_detail(await question_note_dao.get_detail(db, note_id, viewer_id=user_id))

    @staticmethod
    async def delete_note(*, db: AsyncSession, user_id: int, note_id: int) -> None:
        """删除用户自己的笔记"""
        note = await question_note_dao.get(db, note_id, user_id=user_id)
        if note is not None:
            await question_note_dao.delete_model(db, note.id)

    @staticmethod
    def get_public_notes_select(
        *,
        user_id: int,
        question_id: int,
    ) -> Any:
        """构建题目公开笔记查询"""
        return question_note_dao.get_public_by_question_select(
            question_id=question_id,
            viewer_id=user_id,
        )

    @staticmethod
    async def get_session_notes(
        *,
        db: AsyncSession,
        user_id: int,
        session_key: str,
    ) -> dict[int, GetQuestionNoteDetail]:
        """一次查询获取会话内当前用户笔记"""
        session = await practice_session_dao.get_by_key(db, session_key, user_id=user_id)
        if session is None:
            raise errors.NotFoundError(msg='练习会话不存在')
        rows = await question_note_dao.get_session_notes(db, session_id=session.id, user_id=user_id)
        return {int(row['question_id']): UserContentService._note_detail(row) for row in rows}

    @staticmethod
    async def vote_note(
        *,
        db: AsyncSession,
        user_id: int,
        note_id: int,
        obj: QuestionNoteVoteParam,
    ) -> GetQuestionNoteDetail:
        """原子切换公开笔记点赞或点踩并维护计数缓存"""
        note = await question_note_dao.get(db, note_id, for_update=True)
        if note is None or note.visibility != 'public' or note.status != 'published':
            raise errors.NotFoundError(msg='公开笔记不存在')
        if note.user_id == user_id:
            raise errors.ConflictError(msg='不能给自己的笔记投票')
        existing = await question_note_vote_dao.get(db, note_id=note_id, user_id=user_id)
        previous_value = existing.vote_value if existing is not None else 0
        next_value = obj.vote_value
        if previous_value == next_value:
            return UserContentService._note_detail(await question_note_dao.get_detail(db, note_id, viewer_id=user_id))
        if existing is None and next_value != 0:
            await question_note_vote_dao.create(
                db,
                note_id=note_id,
                user_id=user_id,
                vote_value=next_value,
            )
        elif existing is not None and next_value == 0:
            await question_note_vote_dao.delete_model(db, existing.id)
        elif existing is not None:
            await question_note_vote_dao.update(db, existing.id, vote_value=next_value)
        note.like_count = max(0, note.like_count - int(previous_value == 1) + int(next_value == 1))
        note.dislike_count = max(0, note.dislike_count - int(previous_value == -1) + int(next_value == -1))
        note.updated_by = user_id
        await db.flush()
        return UserContentService._note_detail(await question_note_dao.get_detail(db, note_id, viewer_id=user_id))

    @staticmethod
    async def get_note_statistics(
        *,
        db: AsyncSession,
        user_id: int,
        group_by: str,
        knowledge_system_id: int | None = None,
        domain_category_id: int | None = None,
    ) -> NoteStatistics:
        """获取笔记汇总及题库或知识点分组"""
        stats = await question_note_dao.get_statistics(db, user_id=user_id)
        knowledge_system_ids = await UserContentService._resolve_knowledge_system_ids(
            db=db,
            user_id=user_id,
            group_by=group_by,
            knowledge_system_id=knowledge_system_id,
            domain_category_id=domain_category_id,
        )
        rows = await question_note_dao.get_group_counts(
            db,
            user_id=user_id,
            group_by=group_by,
            knowledge_system_ids=knowledge_system_ids,
        )
        groups = (
            UserContentService._build_groups(rows=rows, group_by=group_by)
            if group_by == 'knowledge_point'
            else await content_group_service.build_bank_tree(db=db, rows=rows, ungrouped_name='未归属题库')
        )
        return NoteStatistics(
            **stats,
            groups=groups,
        )


user_content_service: UserContentService = UserContentService()
