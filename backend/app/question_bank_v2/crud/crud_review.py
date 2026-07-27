from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.question_bank_v2.model.asset import QbAsset, QbQuestionRevisionAsset
from backend.app.question_bank_v2.model.knowledge import QbKnowledgePoint, QbKnowledgeSystem
from backend.app.question_bank_v2.model.question import QbQuestionRevision
from backend.app.question_bank_v2.model.review import (
    QbQuestionReview,
    QbQuestionReviewKnowledgePoint,
    QbQuestionReviewTag,
    QbReviewTag,
    QbWrongQuestionState,
)
from backend.app.question_bank_v2.model.statistics import QbUserQuestionMastery
from backend.app.question_bank_v2.schema.review import ExternalQuestionAssetParam


class CRUDWrongQuestionState(CRUDPlus[QbWrongQuestionState]):
    """用户错题当前状态数据库操作类"""

    async def get(
        self,
        db: AsyncSession,
        pk: int,
        *,
        user_id: int,
        for_update: bool = False,
    ) -> QbWrongQuestionState | None:
        """获取当前用户的一条错题状态"""
        stmt = select(QbWrongQuestionState).where(
            QbWrongQuestionState.id == pk,
            QbWrongQuestionState.user_id == user_id,
            QbWrongQuestionState.deleted == 0,
        )
        if for_update:
            stmt = stmt.with_for_update()
        return (await db.execute(stmt)).scalars().first()

    async def get_by_question(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        question_id: int,
        for_update: bool = False,
    ) -> QbWrongQuestionState | None:
        """按用户和稳定题目获取错题状态"""
        stmt = select(QbWrongQuestionState).where(
            QbWrongQuestionState.user_id == user_id,
            QbWrongQuestionState.question_id == question_id,
            QbWrongQuestionState.deleted == 0,
        )
        if for_update:
            stmt = stmt.with_for_update()
        return (await db.execute(stmt)).scalars().first()

    async def create(self, db: AsyncSession, data: dict[str, Any]) -> QbWrongQuestionState:
        """创建错题状态"""
        state = QbWrongQuestionState(**data)
        db.add(state)
        await db.flush()
        return state

    @staticmethod
    def _list_stmt() -> Any:
        return (
            select(
                QbWrongQuestionState.id,
                QbWrongQuestionState.question_id,
                QbWrongQuestionState.last_question_revision_id.label('question_revision_id'),
                QbWrongQuestionState.entry_source,
                QbWrongQuestionState.status,
                QbWrongQuestionState.wrong_count,
                QbWrongQuestionState.correct_streak,
                QbWrongQuestionState.first_wrong_time,
                QbWrongQuestionState.last_wrong_time,
                QbWrongQuestionState.last_practice_time,
                QbWrongQuestionState.last_wrong_response,
                QbWrongQuestionState.is_pinned,
                QbQuestionRevision.stem,
                QbQuestionRevision.content_format,
                QbQuestionRevision.question_type,
                QbQuestionRevision.option_data,
                QbUserQuestionMastery.next_review_time,
            )
            .join(
                QbQuestionRevision,
                and_(
                    QbQuestionRevision.question_id == QbWrongQuestionState.question_id,
                    QbQuestionRevision.id == QbWrongQuestionState.last_question_revision_id,
                    QbQuestionRevision.deleted == 0,
                ),
            )
            .outerjoin(
                QbUserQuestionMastery,
                and_(
                    QbUserQuestionMastery.user_id == QbWrongQuestionState.user_id,
                    QbUserQuestionMastery.question_id == QbWrongQuestionState.question_id,
                    QbUserQuestionMastery.deleted == 0,
                ),
            )
            .where(QbWrongQuestionState.deleted == 0)
        )

    async def get_list(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        status: str | None,
        entry_source: str | None,
        offset: int,
        limit: int,
    ) -> list[dict[str, Any]]:
        """获取用户错题列表"""
        stmt = self._list_stmt().where(QbWrongQuestionState.user_id == user_id)
        if status is not None:
            stmt = stmt.where(QbWrongQuestionState.status == status)
        if entry_source is not None:
            stmt = stmt.where(QbWrongQuestionState.entry_source == entry_source)
        stmt = (
            stmt.order_by(
                QbWrongQuestionState.is_pinned.desc(),
                QbWrongQuestionState.last_wrong_time.desc().nullslast(),
                QbWrongQuestionState.id.desc(),
            )
            .offset(offset)
            .limit(limit)
        )
        return [dict(row) for row in (await db.execute(stmt)).mappings().all()]

    async def get_detail_row(
        self,
        db: AsyncSession,
        *,
        pk: int,
        user_id: int,
    ) -> dict[str, Any] | None:
        """获取用户错题展示详情"""
        stmt = self._list_stmt().where(
            QbWrongQuestionState.id == pk,
            QbWrongQuestionState.user_id == user_id,
        )
        row = (await db.execute(stmt)).mappings().first()
        return dict(row) if row is not None else None

    async def get_due(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        now: datetime,
        limit: int,
    ) -> tuple[int, list[dict[str, Any]]]:
        """获取用户当前到期的活跃错题"""
        conditions = (
            QbWrongQuestionState.user_id == user_id,
            QbWrongQuestionState.status == 'active',
            QbWrongQuestionState.deleted == 0,
            QbUserQuestionMastery.state.in_({'learning', 'review'}),
            QbUserQuestionMastery.next_review_time <= now,
            QbUserQuestionMastery.deleted == 0,
        )
        count_stmt = (
            select(func.count())
            .select_from(QbWrongQuestionState)
            .join(
                QbUserQuestionMastery,
                and_(
                    QbUserQuestionMastery.user_id == QbWrongQuestionState.user_id,
                    QbUserQuestionMastery.question_id == QbWrongQuestionState.question_id,
                ),
            )
            .where(*conditions)
        )
        total = int((await db.execute(count_stmt)).scalar_one())
        stmt = (
            self._list_stmt()
            .where(*conditions)
            .order_by(QbUserQuestionMastery.next_review_time, QbWrongQuestionState.id)
            .limit(limit)
        )
        rows = [dict(row) for row in (await db.execute(stmt)).mappings().all()]
        return total, rows


class CRUDUserQuestionMastery(CRUDPlus[QbUserQuestionMastery]):
    """用户题目掌握度和调度状态数据库操作类"""

    async def get_by_question(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        question_id: int,
        for_update: bool = False,
    ) -> QbUserQuestionMastery | None:
        """按用户和题目获取掌握度"""
        stmt = select(QbUserQuestionMastery).where(
            QbUserQuestionMastery.user_id == user_id,
            QbUserQuestionMastery.question_id == question_id,
            QbUserQuestionMastery.deleted == 0,
        )
        if for_update:
            stmt = stmt.with_for_update()
        return (await db.execute(stmt)).scalars().first()

    async def create(self, db: AsyncSession, data: dict[str, Any]) -> QbUserQuestionMastery:
        """创建掌握度和调度状态"""
        mastery = QbUserQuestionMastery(**data)
        db.add(mastery)
        await db.flush()
        return mastery


class CRUDQuestionReview(CRUDPlus[QbQuestionReview]):
    """错题复盘事件数据库操作类"""

    async def get(self, db: AsyncSession, pk: int, *, user_id: int) -> QbQuestionReview | None:
        """获取当前用户的一次复盘事件"""
        stmt = select(QbQuestionReview).where(
            QbQuestionReview.id == pk,
            QbQuestionReview.user_id == user_id,
            QbQuestionReview.deleted == 0,
        )
        return (await db.execute(stmt)).scalars().first()

    async def get_by_idempotency_key(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        idempotency_key: str,
    ) -> QbQuestionReview | None:
        """按用户和客户端幂等键获取复盘事件"""
        stmt = select(QbQuestionReview).where(
            QbQuestionReview.user_id == user_id,
            QbQuestionReview.idempotency_key == idempotency_key,
            QbQuestionReview.deleted == 0,
        )
        return (await db.execute(stmt)).scalars().first()

    async def create(self, db: AsyncSession, data: dict[str, Any]) -> QbQuestionReview:
        """追加复盘事件"""
        review = QbQuestionReview(**data)
        db.add(review)
        await db.flush()
        return review

    async def get_link_ids(self, db: AsyncSession, review_id: int) -> tuple[list[int], list[int]]:
        """获取复盘事件的标签和知识点 ID"""
        tag_ids = list(
            (
                await db.execute(
                    select(QbQuestionReviewTag.tag_id).where(
                        QbQuestionReviewTag.review_id == review_id,
                        QbQuestionReviewTag.deleted == 0,
                    )
                )
            )
            .scalars()
            .all()
        )
        knowledge_point_ids = list(
            (
                await db.execute(
                    select(QbQuestionReviewKnowledgePoint.knowledge_point_id).where(
                        QbQuestionReviewKnowledgePoint.review_id == review_id,
                        QbQuestionReviewKnowledgePoint.deleted == 0,
                    )
                )
            )
            .scalars()
            .all()
        )
        return tag_ids, knowledge_point_ids

    async def create_links(
        self,
        db: AsyncSession,
        *,
        review_id: int,
        tag_ids: Sequence[int],
        knowledge_point_ids: Sequence[int],
    ) -> None:
        """创建复盘标签和知识点关联"""
        db.add_all([QbQuestionReviewTag(review_id=review_id, tag_id=tag_id) for tag_id in tag_ids])
        db.add_all(
            [
                QbQuestionReviewKnowledgePoint(
                    review_id=review_id,
                    knowledge_point_id=knowledge_point_id,
                )
                for knowledge_point_id in knowledge_point_ids
            ]
        )
        await db.flush()


class CRUDReviewReference:
    """复盘标签、知识点和题目资产引用数据库操作类"""

    @staticmethod
    async def get_valid_tag_ids(db: AsyncSession, *, user_id: int, tag_ids: Sequence[int]) -> set[int]:
        """获取用户可使用的复盘标签 ID"""
        if not tag_ids:
            return set()
        stmt = select(QbReviewTag.id).where(
            QbReviewTag.id.in_(tag_ids),
            QbReviewTag.is_active.is_(True),
            QbReviewTag.deleted == 0,
            or_(QbReviewTag.user_id.is_(None), QbReviewTag.user_id == user_id),
        )
        return set((await db.execute(stmt)).scalars().all())

    @staticmethod
    async def get_valid_knowledge_point_ids(
        db: AsyncSession,
        *,
        knowledge_point_ids: Sequence[int],
    ) -> set[int]:
        """获取有效知识点 ID"""
        if not knowledge_point_ids:
            return set()
        stmt = (
            select(QbKnowledgePoint.id)
            .join(QbKnowledgeSystem, QbKnowledgeSystem.id == QbKnowledgePoint.system_id)
            .where(
                QbKnowledgePoint.id.in_(knowledge_point_ids),
                QbKnowledgePoint.deleted == 0,
                QbKnowledgeSystem.status == 'active',
                QbKnowledgeSystem.deleted == 0,
            )
        )
        return set((await db.execute(stmt)).scalars().all())

    @staticmethod
    async def get_valid_asset_ids(db: AsyncSession, *, user_id: int, asset_ids: Sequence[int]) -> set[int]:
        """获取用户可使用且已就绪的题库资产 ID"""
        if not asset_ids:
            return set()
        stmt = select(QbAsset.id).where(
            QbAsset.id.in_(asset_ids),
            QbAsset.status == 'ready',
            QbAsset.deleted == 0,
            or_(QbAsset.visibility != 'private', QbAsset.owner_id == user_id),
        )
        return set((await db.execute(stmt)).scalars().all())

    @staticmethod
    async def create_question_asset_links(
        db: AsyncSession,
        *,
        revision_id: int,
        items: Sequence[ExternalQuestionAssetParam],
        user_id: int,
    ) -> None:
        """创建外部错题版本资产关联"""
        db.add_all(
            [
                QbQuestionRevisionAsset(
                    question_revision_id=revision_id,
                    asset_id=item.asset_id,
                    link_key=item.link_key,
                    role=item.role,
                    locator=item.locator,
                    sort_order=item.sort_order,
                    created_by=user_id,
                )
                for item in items
            ]
        )
        await db.flush()


class CRUDReviewTag(CRUDPlus[QbReviewTag]):
    """系统和用户复盘标签数据库操作类"""

    async def get_all(self, db: AsyncSession, *, user_id: int) -> Sequence[QbReviewTag]:
        """获取系统标签和当前用户自定义标签"""
        stmt = (
            select(QbReviewTag)
            .where(
                QbReviewTag.deleted == 0,
                QbReviewTag.is_active.is_(True),
                or_(QbReviewTag.user_id.is_(None), QbReviewTag.user_id == user_id),
            )
            .order_by(QbReviewTag.tag_type, QbReviewTag.sort_order, QbReviewTag.id)
        )
        return (await db.execute(stmt)).scalars().all()

    async def get_by_name(self, db: AsyncSession, *, user_id: int, name: str) -> QbReviewTag | None:
        """按用户和名称获取自定义标签"""
        stmt = select(QbReviewTag).where(
            QbReviewTag.user_id == user_id,
            QbReviewTag.name == name,
            QbReviewTag.deleted == 0,
        )
        return (await db.execute(stmt)).scalars().first()

    async def create(self, db: AsyncSession, data: dict[str, Any]) -> QbReviewTag:
        """创建用户自定义复盘标签"""
        tag = QbReviewTag(**data)
        db.add(tag)
        await db.flush()
        return tag


wrong_question_state_dao: CRUDWrongQuestionState = CRUDWrongQuestionState(QbWrongQuestionState)
user_question_mastery_dao: CRUDUserQuestionMastery = CRUDUserQuestionMastery(QbUserQuestionMastery)
question_review_dao: CRUDQuestionReview = CRUDQuestionReview(QbQuestionReview)
review_reference_dao: CRUDReviewReference = CRUDReviewReference()
review_tag_dao: CRUDReviewTag = CRUDReviewTag(QbReviewTag)
