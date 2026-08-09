from collections.abc import Sequence
from typing import Any

from sqlalchemy import Select, and_, case, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.admin.model.user import User
from backend.app.question_bank_v2.model.bank import QbBank, QbBankItem, QbBankRevision, QbBankSection
from backend.app.question_bank_v2.model.knowledge import QbKnowledgePoint, QbQuestionKnowledgePoint
from backend.app.question_bank_v2.model.practice import QbPracticeSessionItem
from backend.app.question_bank_v2.model.question import QbQuestion
from backend.app.question_bank_v2.model.user_content import (
    QbFavoriteFolder,
    QbQuestionFavorite,
    QbQuestionNote,
    QbQuestionNoteVote,
)


async def _get_bank_group_counts(
    db: AsyncSession,
    *,
    model: type[QbQuestionFavorite] | type[QbQuestionNote],
    user_id: int,
) -> list[dict[str, Any]]:
    """按题库和篇章统计用户内容"""
    saved_item = QbBankItem.__table__.alias('saved_content_bank_item')
    has_valid_saved_item = exists(
        select(saved_item.c.id).where(
            saved_item.c.id == model.bank_item_id,
        )
    )
    ranked_items = (
        select(
            QbBankItem.id,
            QbBankItem.question_id,
            func.row_number()
            .over(
                partition_by=(QbBankItem.question_id, QbBankRevision.bank_id),
                order_by=(
                    (QbBankItem.bank_revision_id == QbBank.current_revision_id).desc(),
                    QbBankRevision.revision_no.desc(),
                    QbBankItem.id.desc(),
                ),
            )
            .label('rank'),
        )
        .join(QbBankRevision, QbBankRevision.id == QbBankItem.bank_revision_id)
        .join(QbBank, QbBank.id == QbBankRevision.bank_id)
        .subquery()
    )
    fallback_item_ids = select(ranked_items.c.id).where(
        ranked_items.c.question_id == model.question_id,
        ranked_items.c.rank == 1,
    )
    stmt = (
        select(
            QbBank.id.label('bank_id'),
            QbBankItem.bank_revision_id,
            QbBankRevision.name.label('bank_name'),
            QbBankSection.id.label('section_id'),
            QbBankSection.name.label('section_name'),
            func.count(func.distinct(model.question_id)).label('count'),
        )
        .select_from(model)
        .join(
            QbBankItem,
            and_(
                or_(
                    QbBankItem.id == model.bank_item_id,
                    and_(
                        QbBankItem.id.in_(fallback_item_ids),
                        ~has_valid_saved_item,
                    ),
                ),
            ),
        )
        .join(
            QbBankRevision,
            QbBankRevision.id == QbBankItem.bank_revision_id,
        )
        .join(QbBank, QbBank.id == QbBankRevision.bank_id)
        .outerjoin(
            QbBankSection,
            QbBankSection.id == QbBankItem.section_id,
        )
        .where(
            model.user_id == user_id,
            model.deleted == 0,
        )
        .group_by(
            QbBank.id,
            QbBankItem.bank_revision_id,
            QbBankRevision.name,
            QbBankSection.id,
            QbBankSection.name,
        )
        .order_by(QbBankRevision.name, QbBankSection.name)
    )
    return [dict(row) for row in (await db.execute(stmt)).mappings().all()]


async def _get_knowledge_group_counts(
    db: AsyncSession,
    *,
    model: type[QbQuestionFavorite] | type[QbQuestionNote],
    user_id: int,
    knowledge_system_ids: Sequence[int],
) -> list[dict[str, Any]]:
    """按知识点统计用户内容"""
    stmt = (
        select(
            QbKnowledgePoint.id,
            QbKnowledgePoint.name,
            func.count(func.distinct(model.question_id)).label('count'),
        )
        .select_from(model)
        .join(
            QbQuestionKnowledgePoint,
            and_(
                QbQuestionKnowledgePoint.question_id == model.question_id,
                QbQuestionKnowledgePoint.deleted == 0,
            ),
        )
        .join(
            QbKnowledgePoint,
            and_(QbKnowledgePoint.id == QbQuestionKnowledgePoint.knowledge_point_id, QbKnowledgePoint.deleted == 0),
        )
        .where(model.user_id == user_id, model.deleted == 0)
    )
    stmt = stmt.where(QbKnowledgePoint.system_id.in_(knowledge_system_ids))
    stmt = stmt.group_by(QbKnowledgePoint.id, QbKnowledgePoint.name, QbKnowledgePoint.sort_order).order_by(
        QbKnowledgePoint.sort_order,
        QbKnowledgePoint.id,
    )
    return [dict(row) for row in (await db.execute(stmt)).mappings().all()]


class CRUDFavoriteFolder(CRUDPlus[QbFavoriteFolder]):
    """用户收藏夹数据库操作类"""

    async def get(self, db: AsyncSession, pk: int, *, user_id: int) -> QbFavoriteFolder | None:
        """获取用户收藏夹"""
        stmt = select(QbFavoriteFolder).where(
            QbFavoriteFolder.id == pk,
            QbFavoriteFolder.user_id == user_id,
            QbFavoriteFolder.deleted == 0,
        )
        return (await db.execute(stmt)).scalars().first()

    async def get_by_name(self, db: AsyncSession, *, user_id: int, name: str) -> QbFavoriteFolder | None:
        """按名称获取用户收藏夹"""
        stmt = select(QbFavoriteFolder).where(
            QbFavoriteFolder.user_id == user_id,
            QbFavoriteFolder.name == name,
            QbFavoriteFolder.deleted == 0,
        )
        return (await db.execute(stmt)).scalars().first()

    async def get_all(self, db: AsyncSession, *, user_id: int) -> list[dict[str, Any]]:
        """获取用户收藏夹及收藏数量"""
        stmt = (
            select(
                QbFavoriteFolder.id,
                QbFavoriteFolder.name,
                QbFavoriteFolder.description,
                QbFavoriteFolder.sort_order,
                QbFavoriteFolder.status,
                QbFavoriteFolder.created_time,
                QbFavoriteFolder.updated_time,
                func.count(QbQuestionFavorite.id).label('favorite_count'),
            )
            .outerjoin(
                QbQuestionFavorite,
                and_(
                    QbQuestionFavorite.folder_id == QbFavoriteFolder.id,
                    QbQuestionFavorite.user_id == user_id,
                    QbQuestionFavorite.deleted == 0,
                ),
            )
            .where(QbFavoriteFolder.user_id == user_id, QbFavoriteFolder.deleted == 0)
            .group_by(
                QbFavoriteFolder.id,
                QbFavoriteFolder.name,
                QbFavoriteFolder.description,
                QbFavoriteFolder.sort_order,
                QbFavoriteFolder.status,
                QbFavoriteFolder.created_time,
                QbFavoriteFolder.updated_time,
            )
            .order_by(QbFavoriteFolder.status, QbFavoriteFolder.sort_order, QbFavoriteFolder.id)
        )
        return [dict(row) for row in (await db.execute(stmt)).mappings().all()]

    async def create(self, db: AsyncSession, *, user_id: int, data: dict[str, Any]) -> QbFavoriteFolder:
        """创建收藏夹"""
        folder = QbFavoriteFolder(user_id=user_id, created_by=user_id, **data)
        db.add(folder)
        await db.flush()
        return folder

    async def update(self, db: AsyncSession, pk: int, *, user_id: int, data: dict[str, Any]) -> int:
        """更新收藏夹"""
        return await self.update_model_by_column(db, data, id=pk, user_id=user_id, deleted=0)

    async def clear_favorites(self, db: AsyncSession, *, folder_id: int, user_id: int) -> int:
        """删除收藏夹前将其中收藏移到未分组"""
        return await question_favorite_dao.update_model_by_column(
            db,
            {'folder_id': None, 'updated_by': user_id},
            folder_id=folder_id,
            user_id=user_id,
            deleted=0,
        )


class CRUDQuestionFavorite(CRUDPlus[QbQuestionFavorite]):
    """用户题目收藏数据库操作类"""

    async def get(self, db: AsyncSession, pk: int, *, user_id: int) -> QbQuestionFavorite | None:
        """获取用户题目收藏"""
        stmt = select(QbQuestionFavorite).where(
            QbQuestionFavorite.id == pk,
            QbQuestionFavorite.user_id == user_id,
            QbQuestionFavorite.deleted == 0,
        )
        return (await db.execute(stmt)).scalars().first()

    async def get_by_question(self, db: AsyncSession, *, user_id: int, question_id: int) -> QbQuestionFavorite | None:
        """按稳定题目获取用户收藏"""
        stmt = select(QbQuestionFavorite).where(
            QbQuestionFavorite.user_id == user_id,
            QbQuestionFavorite.question_id == question_id,
            QbQuestionFavorite.deleted == 0,
        )
        return (await db.execute(stmt)).scalars().first()

    @staticmethod
    def _detail_select() -> Select:
        return (
            select(
                QbQuestionFavorite.id,
                QbQuestionFavorite.question_id,
                QbQuestionFavorite.folder_id,
                QbFavoriteFolder.name.label('folder_name'),
                QbQuestionFavorite.bank_item_id,
                QbQuestionFavorite.tags,
                QbQuestionFavorite.remark,
                QbQuestionFavorite.is_pinned,
                QbQuestionFavorite.pinned_time,
                QbQuestionFavorite.created_time,
                QbQuestionFavorite.updated_time,
                QbQuestion.stem,
                QbQuestion.question_type,
                QbQuestion.difficulty,
            )
            .join(
                QbQuestion,
                and_(
                    QbQuestion.id == QbQuestionFavorite.question_id,
                    QbQuestion.deleted == 0,
                ),
            )
            .outerjoin(
                QbFavoriteFolder,
                and_(QbFavoriteFolder.id == QbQuestionFavorite.folder_id, QbFavoriteFolder.deleted == 0),
            )
            .where(QbQuestionFavorite.deleted == 0)
        )

    async def get_detail(self, db: AsyncSession, pk: int, *, user_id: int) -> dict[str, Any] | None:
        """获取用户收藏聚合详情"""
        row = (
            (
                await db.execute(
                    self._detail_select().where(
                        QbQuestionFavorite.id == pk,
                        QbQuestionFavorite.user_id == user_id,
                    )
                )
            )
            .mappings()
            .first()
        )
        return dict(row) if row is not None else None

    def get_list_select(
        self,
        *,
        user_id: int,
        folder_id: int | None,
    ) -> Select:
        """构建用户收藏游标分页查询"""
        stmt = self._detail_select().where(QbQuestionFavorite.user_id == user_id, QbQuestionFavorite.deleted == 0)
        if folder_id is not None:
            stmt = stmt.where(QbQuestionFavorite.folder_id == folder_id)
        return stmt.order_by(
            QbQuestionFavorite.is_pinned.desc(),
            QbQuestionFavorite.pinned_time.desc().nullslast(),
            QbQuestionFavorite.created_time.desc(),
            QbQuestionFavorite.id.desc(),
        )

    async def create(self, db: AsyncSession, *, user_id: int, data: dict[str, Any]) -> QbQuestionFavorite:
        """创建题目收藏"""
        favorite = QbQuestionFavorite(user_id=user_id, created_by=user_id, **data)
        db.add(favorite)
        await db.flush()
        return favorite

    async def update(self, db: AsyncSession, pk: int, *, user_id: int, data: dict[str, Any]) -> int:
        """更新题目收藏"""
        return await self.update_model_by_column(db, data, id=pk, user_id=user_id, deleted=0)

    async def get_session_states(self, db: AsyncSession, *, session_id: int, user_id: int) -> dict[int, bool]:
        """批量获取会话题目收藏状态"""
        stmt = (
            select(QbPracticeSessionItem.question_id)
            .join(
                QbQuestionFavorite,
                and_(
                    QbQuestionFavorite.question_id == QbPracticeSessionItem.question_id,
                    QbQuestionFavorite.user_id == user_id,
                    QbQuestionFavorite.deleted == 0,
                ),
            )
            .where(QbPracticeSessionItem.session_id == session_id, QbPracticeSessionItem.deleted == 0)
        )
        return {int(question_id): True for question_id in (await db.execute(stmt)).scalars().all()}

    async def get_statistics(self, db: AsyncSession, *, user_id: int) -> dict[str, int]:
        """获取用户收藏汇总统计"""
        total_count = (
            select(func.count(QbQuestionFavorite.id))
            .where(QbQuestionFavorite.user_id == user_id, QbQuestionFavorite.deleted == 0)
            .scalar_subquery()
        )
        folder_count = (
            select(func.count(QbFavoriteFolder.id))
            .where(
                QbFavoriteFolder.user_id == user_id,
                QbFavoriteFolder.deleted == 0,
                QbFavoriteFolder.status == 'active',
            )
            .scalar_subquery()
        )
        result = await db.execute(
            select(
                total_count.label('total_count'),
                folder_count.label('folder_count'),
            )
        )
        return dict(result.mappings().one())

    async def get_group_counts(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        group_by: str,
        knowledge_system_ids: Sequence[int],
    ) -> list[dict[str, Any]]:
        """获取收藏的题库或知识点分组统计"""
        if group_by == 'bank':
            return await _get_bank_group_counts(db, model=QbQuestionFavorite, user_id=user_id)
        return await _get_knowledge_group_counts(
            db,
            model=QbQuestionFavorite,
            user_id=user_id,
            knowledge_system_ids=knowledge_system_ids,
        )


class CRUDQuestionNote(CRUDPlus[QbQuestionNote]):
    """用户题目笔记数据库操作类"""

    async def get(
        self,
        db: AsyncSession,
        pk: int,
        *,
        user_id: int | None = None,
        for_update: bool = False,
    ) -> QbQuestionNote | None:
        """获取题目笔记"""
        stmt = select(QbQuestionNote).where(QbQuestionNote.id == pk, QbQuestionNote.deleted == 0)
        if user_id is not None:
            stmt = stmt.where(QbQuestionNote.user_id == user_id)
        if for_update:
            stmt = stmt.with_for_update()
        return (await db.execute(stmt)).scalars().first()

    async def get_by_question(self, db: AsyncSession, *, user_id: int, question_id: int) -> QbQuestionNote | None:
        """按稳定题目获取用户笔记"""
        stmt = select(QbQuestionNote).where(
            QbQuestionNote.user_id == user_id,
            QbQuestionNote.question_id == question_id,
            QbQuestionNote.deleted == 0,
        )
        return (await db.execute(stmt)).scalars().first()

    @staticmethod
    def _detail_select() -> Select:
        return (
            select(
                QbQuestionNote.id,
                QbQuestionNote.user_id,
                User.nickname.label('user_nickname'),
                QbQuestionNote.question_id,
                QbQuestionNote.bank_item_id,
                QbQuestionNote.content,
                QbQuestionNote.content_format,
                QbQuestionNote.visibility,
                QbQuestionNote.status,
                QbQuestionNote.like_count,
                QbQuestionNote.dislike_count,
                QbQuestionNote.view_count,
                QbQuestionNote.is_featured,
                QbQuestionNote.created_time,
                QbQuestionNote.updated_time,
                QbQuestion.stem,
                QbQuestion.question_type,
            )
            .join(User, and_(User.id == QbQuestionNote.user_id, User.deleted == 0))
            .join(
                QbQuestion,
                and_(
                    QbQuestion.id == QbQuestionNote.question_id,
                    QbQuestion.deleted == 0,
                ),
            )
            .where(QbQuestionNote.deleted == 0)
        )

    async def get_detail(self, db: AsyncSession, pk: int, *, viewer_id: int) -> dict[str, Any] | None:
        """获取笔记详情及当前用户投票"""
        vote = QbQuestionNoteVote.__table__.alias('viewer_vote')
        stmt = (
            self
            ._detail_select()
            .add_columns(vote.c.vote_value.label('my_vote'))
            .outerjoin(
                vote,
                and_(vote.c.note_id == QbQuestionNote.id, vote.c.user_id == viewer_id, vote.c.deleted == 0),
            )
            .where(QbQuestionNote.id == pk)
        )
        row = (await db.execute(stmt)).mappings().first()
        return dict(row) if row is not None else None

    def get_list_select(
        self,
        *,
        user_id: int,
    ) -> Select:
        """构建用户笔记游标分页查询"""
        return (
            self
            ._detail_select()
            .where(QbQuestionNote.user_id == user_id)
            .order_by(QbQuestionNote.updated_time.desc(), QbQuestionNote.id.desc())
        )

    def get_public_by_question_select(
        self,
        *,
        question_id: int,
        viewer_id: int,
    ) -> Select:
        """构建题目公开笔记游标分页查询"""
        vote = QbQuestionNoteVote.__table__.alias('viewer_vote')
        return (
            self
            ._detail_select()
            .add_columns(vote.c.vote_value.label('my_vote'))
            .outerjoin(
                vote,
                and_(vote.c.note_id == QbQuestionNote.id, vote.c.user_id == viewer_id, vote.c.deleted == 0),
            )
            .where(
                QbQuestionNote.question_id == question_id,
                QbQuestionNote.visibility == 'public',
                QbQuestionNote.status == 'published',
            )
            .order_by(QbQuestionNote.is_featured.desc(), QbQuestionNote.like_count.desc(), QbQuestionNote.id.desc())
        )

    async def create(self, db: AsyncSession, *, user_id: int, data: dict[str, Any]) -> QbQuestionNote:
        """创建题目笔记"""
        note = QbQuestionNote(user_id=user_id, created_by=user_id, **data)
        db.add(note)
        await db.flush()
        return note

    async def update(self, db: AsyncSession, pk: int, *, user_id: int, data: dict[str, Any]) -> int:
        """更新题目笔记"""
        return await self.update_model_by_column(db, data, id=pk, user_id=user_id, deleted=0)

    async def get_session_notes(self, db: AsyncSession, *, session_id: int, user_id: int) -> list[dict[str, Any]]:
        """批量获取会话题目的用户笔记"""
        stmt = (
            self
            ._detail_select()
            .join(QbPracticeSessionItem, QbPracticeSessionItem.question_id == QbQuestionNote.question_id)
            .where(
                QbPracticeSessionItem.session_id == session_id,
                QbPracticeSessionItem.deleted == 0,
                QbQuestionNote.user_id == user_id,
            )
            .order_by(QbPracticeSessionItem.position)
        )
        return [dict(row) for row in (await db.execute(stmt)).mappings().all()]

    async def get_statistics(self, db: AsyncSession, *, user_id: int) -> dict[str, int]:
        """获取用户笔记汇总统计"""
        result = await db.execute(
            select(
                func.count(QbQuestionNote.id).label('total_count'),
                func.sum(case((QbQuestionNote.visibility == 'public', 1), else_=0)).label('public_count'),
                func.sum(case((QbQuestionNote.is_featured.is_(True), 1), else_=0)).label('featured_count'),
            ).where(QbQuestionNote.user_id == user_id, QbQuestionNote.deleted == 0)
        )
        row = dict(result.mappings().one())
        return {key: int(value or 0) for key, value in row.items()}

    async def get_group_counts(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        group_by: str,
        knowledge_system_ids: Sequence[int],
    ) -> list[dict[str, Any]]:
        """获取笔记的题库或知识点分组统计"""
        if group_by == 'bank':
            return await _get_bank_group_counts(db, model=QbQuestionNote, user_id=user_id)
        return await _get_knowledge_group_counts(
            db,
            model=QbQuestionNote,
            user_id=user_id,
            knowledge_system_ids=knowledge_system_ids,
        )


class CRUDQuestionNoteVote(CRUDPlus[QbQuestionNoteVote]):
    """公开笔记投票数据库操作类"""

    async def get(self, db: AsyncSession, *, note_id: int, user_id: int) -> QbQuestionNoteVote | None:
        """获取用户对笔记的投票"""
        stmt = select(QbQuestionNoteVote).where(
            QbQuestionNoteVote.note_id == note_id,
            QbQuestionNoteVote.user_id == user_id,
            QbQuestionNoteVote.deleted == 0,
        )
        return (await db.execute(stmt)).scalars().first()

    async def create(self, db: AsyncSession, *, note_id: int, user_id: int, vote_value: int) -> QbQuestionNoteVote:
        """创建笔记投票"""
        vote = QbQuestionNoteVote(note_id=note_id, user_id=user_id, vote_value=vote_value)
        db.add(vote)
        await db.flush()
        return vote

    async def update(self, db: AsyncSession, pk: int, *, vote_value: int) -> int:
        """切换笔记投票"""
        return await self.update_model_by_column(db, {'vote_value': vote_value}, id=pk, deleted=0)


favorite_folder_dao: CRUDFavoriteFolder = CRUDFavoriteFolder(QbFavoriteFolder)
question_favorite_dao: CRUDQuestionFavorite = CRUDQuestionFavorite(QbQuestionFavorite)
question_note_dao: CRUDQuestionNote = CRUDQuestionNote(QbQuestionNote)
question_note_vote_dao: CRUDQuestionNoteVote = CRUDQuestionNoteVote(QbQuestionNoteVote)
