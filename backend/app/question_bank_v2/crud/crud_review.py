from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import and_, case, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.question_bank_v2.model.asset import QbAsset, QbQuestionAsset
from backend.app.question_bank_v2.model.bank import QbBank, QbBankItem, QbBankRevision, QbBankSection
from backend.app.question_bank_v2.model.knowledge import (
    QbKnowledgePoint,
    QbKnowledgeSystem,
    QbQuestionKnowledgePoint,
)
from backend.app.question_bank_v2.model.question import QbQuestion, QbQuestionAnswer, QbQuestionExplanation
from backend.app.question_bank_v2.model.review import (
    QbQuestionReview,
    QbQuestionReviewKnowledgePoint,
    QbQuestionReviewTag,
    QbReviewTag,
    QbWrongQuestionState,
)
from backend.app.question_bank_v2.model.statistics import QbUserQuestionMastery
from backend.app.question_bank_v2.schema.review import EXTERNAL_ENTRY_SOURCES, ExternalQuestionAssetParam


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
                QbWrongQuestionState.entry_source,
                QbWrongQuestionState.status,
                QbWrongQuestionState.wrong_count,
                QbWrongQuestionState.correct_streak,
                QbWrongQuestionState.first_wrong_time,
                QbWrongQuestionState.last_wrong_time,
                QbWrongQuestionState.last_practice_time,
                QbWrongQuestionState.is_pinned,
                QbWrongQuestionState.review_count,
                QbWrongQuestionState.last_reviewed_time,
                QbWrongQuestionState.practice_level,
                QbWrongQuestionState.last_rating,
                QbWrongQuestionState.next_practice_time,
                QbQuestion.stem,
                QbQuestion.content_format,
                QbQuestion.question_type,
                func.coalesce(QbUserQuestionMastery.state, 'new').label('mastery_state'),
            )
            .join(
                QbQuestion,
                and_(
                    QbQuestion.id == QbWrongQuestionState.question_id,
                    QbQuestion.deleted == 0,
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

    @staticmethod
    def _apply_entry_scope(stmt: Any, entry_scope: str | None) -> Any:
        """按题库错题或自主录入收窄范围"""
        if entry_scope == 'bank':
            return stmt.where(QbWrongQuestionState.entry_source == 'attempt')
        if entry_scope == 'external':
            return stmt.where(QbWrongQuestionState.entry_source.in_(EXTERNAL_ENTRY_SOURCES))
        return stmt

    def get_list_select(
        self,
        *,
        user_id: int,
        status: str | None,
        entry_source: str | None,
        entry_scope: str | None = None,
    ) -> Any:
        """构建用户错题游标分页查询"""
        stmt = self._list_stmt().where(QbWrongQuestionState.user_id == user_id)
        if status is not None:
            stmt = stmt.where(QbWrongQuestionState.status == status)
        if entry_source is not None:
            stmt = stmt.where(QbWrongQuestionState.entry_source == entry_source)
        stmt = self._apply_entry_scope(stmt, entry_scope)
        return stmt.order_by(
            QbWrongQuestionState.is_pinned.desc(),
            QbWrongQuestionState.last_wrong_time.desc().nullslast(),
            QbWrongQuestionState.id.desc(),
        )

    def get_reviewed_list_select(
        self,
        *,
        user_id: int,
        mastery_state: str | None,
        tag_id: int | None,
        knowledge_point_id: int | None,
    ) -> Any:
        """构建复盘档案游标分页查询"""
        stmt = self._list_stmt().where(
            QbWrongQuestionState.user_id == user_id,
            QbWrongQuestionState.review_count > 0,
        )
        if mastery_state is not None:
            stmt = stmt.where(QbUserQuestionMastery.state == mastery_state)
        if tag_id is not None:
            stmt = stmt.where(
                exists(
                    select(QbQuestionReviewTag.id)
                    .join(QbQuestionReview, QbQuestionReview.id == QbQuestionReviewTag.review_id)
                    .where(
                        QbQuestionReview.wrong_state_id == QbWrongQuestionState.id,
                        QbQuestionReview.deleted == 0,
                        QbQuestionReviewTag.tag_id == tag_id,
                        QbQuestionReviewTag.deleted == 0,
                    )
                )
            )
        if knowledge_point_id is not None:
            stmt = stmt.where(
                exists(
                    select(QbQuestionReviewKnowledgePoint.id)
                    .join(QbQuestionReview, QbQuestionReview.id == QbQuestionReviewKnowledgePoint.review_id)
                    .where(
                        QbQuestionReview.wrong_state_id == QbWrongQuestionState.id,
                        QbQuestionReview.deleted == 0,
                        QbQuestionReviewKnowledgePoint.knowledge_point_id == knowledge_point_id,
                        QbQuestionReviewKnowledgePoint.deleted == 0,
                    )
                )
            )
        return stmt.order_by(
            QbWrongQuestionState.last_reviewed_time.desc().nullslast(),
            QbWrongQuestionState.id.desc(),
        )

    def get_pending_review_list_select(
        self,
        *,
        user_id: int,
        entry_scope: str | None,
    ) -> Any:
        """构建待复盘队列游标分页查询"""
        stmt = self._list_stmt().where(
            QbWrongQuestionState.user_id == user_id,
            QbWrongQuestionState.status == 'active',
            QbWrongQuestionState.review_count == 0,
        )
        stmt = self._apply_entry_scope(stmt, entry_scope)
        return stmt.order_by(
            QbWrongQuestionState.is_pinned.desc(),
            QbWrongQuestionState.last_wrong_time.desc().nullslast(),
            QbWrongQuestionState.id.desc(),
        )

    async def get_detail_row(
        self,
        db: AsyncSession,
        *,
        pk: int,
        user_id: int,
    ) -> dict[str, Any] | None:
        """获取用户错题展示详情，含答案解析与来源题库上下文"""
        stmt = (
            self._list_stmt()
            .add_columns(
                QbWrongQuestionState.last_wrong_response,
                QbQuestion.option_data,
                QbQuestionAnswer.answer_data,
                QbQuestionExplanation.content.label('explanation'),
                QbBankRevision.name.label('bank_name'),
                QbBankSection.name.label('section_name'),
            )
            .outerjoin(
                QbQuestionAnswer,
                and_(
                    QbQuestionAnswer.question_id == QbWrongQuestionState.question_id,
                    QbQuestionAnswer.deleted == 0,
                ),
            )
            .outerjoin(
                QbQuestionExplanation,
                and_(
                    QbQuestionExplanation.question_id == QbWrongQuestionState.question_id,
                    QbQuestionExplanation.is_default.is_(True),
                    QbQuestionExplanation.deleted == 0,
                ),
            )
            .outerjoin(
                QbBankItem,
                and_(
                    QbBankItem.id == QbWrongQuestionState.source_bank_item_id,
                    QbBankItem.deleted == 0,
                ),
            )
            .outerjoin(
                QbBankRevision,
                and_(QbBankRevision.id == QbBankItem.bank_revision_id, QbBankRevision.deleted == 0),
            )
            .outerjoin(
                QbBankSection,
                and_(QbBankSection.id == QbBankItem.section_id, QbBankSection.deleted == 0),
            )
            .where(
                QbWrongQuestionState.id == pk,
                QbWrongQuestionState.user_id == user_id,
            )
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
        """获取用户当前到期重练的错题，单表走 ix_qbv2_wrong_push_due"""
        conditions = (
            QbWrongQuestionState.user_id == user_id,
            QbWrongQuestionState.status == 'active',
            QbWrongQuestionState.deleted == 0,
            QbWrongQuestionState.next_practice_time.is_not(None),
            QbWrongQuestionState.next_practice_time <= now,
        )
        total = int(
            (
                await db.execute(
                    select(func.count()).select_from(QbWrongQuestionState).where(*conditions)
                )
            ).scalar_one()
        )
        stmt = (
            self._list_stmt()
            .where(*conditions)
            .order_by(QbWrongQuestionState.next_practice_time, QbWrongQuestionState.id)
            .limit(limit)
        )
        rows = [dict(row) for row in (await db.execute(stmt)).mappings().all()]
        return total, rows

    async def get_statistics(self, db: AsyncSession, *, user_id: int, now: datetime) -> dict[str, int]:
        """获取用户错题状态汇总"""
        row = (
            await db.execute(
                select(
                    func.count(QbWrongQuestionState.id).label('total_count'),
                    func.sum(case((QbWrongQuestionState.status == 'active', 1), else_=0)).label('active_count'),
                    func.sum(case((QbWrongQuestionState.status == 'resolved', 1), else_=0)).label('resolved_count'),
                    func.coalesce(func.sum(QbWrongQuestionState.wrong_count), 0).label('wrong_occurrence_count'),
                    func.sum(case((QbWrongQuestionState.review_count > 0, 1), else_=0)).label('reviewed_count'),
                    func.sum(
                        case(
                            (
                                and_(
                                    QbWrongQuestionState.status == 'active',
                                    QbWrongQuestionState.review_count == 0,
                                ),
                                1,
                            ),
                            else_=0,
                        )
                    ).label('pending_review_count'),
                    func.sum(
                        case(
                            (
                                and_(
                                    QbWrongQuestionState.status == 'active',
                                    QbWrongQuestionState.next_practice_time.is_not(None),
                                    QbWrongQuestionState.next_practice_time <= now,
                                ),
                                1,
                            ),
                            else_=0,
                        )
                    ).label('due_count'),
                ).where(QbWrongQuestionState.user_id == user_id, QbWrongQuestionState.deleted == 0)
            )
        ).mappings().one()
        return {key: int(value or 0) for key, value in row.items()}

    async def get_dashboard_rows(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        since: datetime,
        knowledge_system_id: int | None = None,
    ) -> tuple[int, list[dict[str, Any]], list[dict[str, Any]]]:
        """按用户复盘时主观选择的标签和知识点聚合分布"""
        review_scope = (
            select(QbQuestionReview.id)
            .where(
                QbQuestionReview.user_id == user_id,
                QbQuestionReview.deleted == 0,
                QbQuestionReview.event_type == 'review',
                QbQuestionReview.reviewed_time >= since,
            )
            .subquery()
        )
        event_count = int(
            (await db.execute(select(func.count()).select_from(review_scope))).scalar_one()
        )
        reason_rows = [
            dict(row)
            for row in (
                await db.execute(
                    select(
                        QbReviewTag.id,
                        QbReviewTag.name,
                        QbReviewTag.color,
                        func.count(QbQuestionReviewTag.id).label('count'),
                    )
                    .select_from(QbQuestionReviewTag)
                    .join(review_scope, review_scope.c.id == QbQuestionReviewTag.review_id)
                    .join(
                        QbReviewTag,
                        and_(QbReviewTag.id == QbQuestionReviewTag.tag_id, QbReviewTag.deleted == 0),
                    )
                    .where(QbQuestionReviewTag.deleted == 0)
                    .group_by(QbReviewTag.id, QbReviewTag.name, QbReviewTag.color)
                    .order_by(func.count(QbQuestionReviewTag.id).desc(), QbReviewTag.id)
                    .limit(20)
                )
            )
            .mappings()
            .all()
        ]
        knowledge_rows_select = (
            select(
                QbKnowledgePoint.id,
                QbKnowledgePoint.name,
                func.count(QbQuestionReviewKnowledgePoint.id).label('count'),
            )
            .select_from(QbQuestionReviewKnowledgePoint)
            .join(review_scope, review_scope.c.id == QbQuestionReviewKnowledgePoint.review_id)
            .join(
                QbKnowledgePoint,
                and_(
                    QbKnowledgePoint.id == QbQuestionReviewKnowledgePoint.knowledge_point_id,
                    QbKnowledgePoint.deleted == 0,
                ),
            )
            .where(QbQuestionReviewKnowledgePoint.deleted == 0)
        )
        knowledge_rows_select = knowledge_rows_select.where(QbKnowledgePoint.system_id == knowledge_system_id)
        knowledge_rows = [
            dict(row)
            for row in (
                await db.execute(
                    knowledge_rows_select.group_by(QbKnowledgePoint.id, QbKnowledgePoint.name).order_by(
                        func.count(QbQuestionReviewKnowledgePoint.id).desc(),
                        QbKnowledgePoint.id,
                    ).limit(20)
                )
            )
            .mappings()
            .all()
        ]
        return event_count, reason_rows, knowledge_rows

    async def scan_due_users(
        self,
        db: AsyncSession,
        *,
        now: datetime,
        user_ids: Sequence[int] | None = None,
    ) -> list[dict[str, int]]:
        """扫描到期重练并按用户聚合，供推送定时任务使用"""
        stmt = (
            select(
                QbWrongQuestionState.user_id,
                func.count(QbWrongQuestionState.id).label('due_count'),
            )
            .where(
                QbWrongQuestionState.deleted == 0,
                QbWrongQuestionState.status == 'active',
                QbWrongQuestionState.next_practice_time.is_not(None),
                QbWrongQuestionState.next_practice_time <= now,
            )
            .group_by(QbWrongQuestionState.user_id)
        )
        if user_ids is not None:
            if not user_ids:
                return []
            stmt = stmt.where(QbWrongQuestionState.user_id.in_(user_ids))
        return [
            {'user_id': int(row['user_id']), 'due_count': int(row['due_count'])}
            for row in (await db.execute(stmt)).mappings().all()
        ]

    async def get_group_counts(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        group_by: str,
        knowledge_system_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """按题库篇章或知识点统计活跃错题"""
        if group_by == 'knowledge_point':
            stmt = (
                select(
                    QbKnowledgePoint.id,
                    QbKnowledgePoint.name,
                    func.count(func.distinct(QbWrongQuestionState.question_id)).label('count'),
                )
                .select_from(QbWrongQuestionState)
                .join(
                    QbQuestionKnowledgePoint,
                    and_(
                        QbQuestionKnowledgePoint.question_id == QbWrongQuestionState.question_id,
                        QbQuestionKnowledgePoint.deleted == 0,
                    ),
                )
                .join(
                    QbKnowledgePoint,
                    and_(
                        QbKnowledgePoint.id == QbQuestionKnowledgePoint.knowledge_point_id,
                        QbKnowledgePoint.deleted == 0,
                    ),
                )
                .where(
                    QbWrongQuestionState.user_id == user_id,
                    QbWrongQuestionState.status == 'active',
                    QbWrongQuestionState.deleted == 0,
                )
            )
            stmt = stmt.where(QbKnowledgePoint.system_id == knowledge_system_id)
            stmt = stmt.group_by(
                QbKnowledgePoint.id,
                QbKnowledgePoint.name,
                QbKnowledgePoint.sort_order,
            ).order_by(QbKnowledgePoint.sort_order, QbKnowledgePoint.id)
        else:
            saved_item = QbBankItem.__table__.alias('saved_wrong_bank_item')
            has_valid_saved_item = exists(
                select(saved_item.c.id).where(
                    saved_item.c.id == QbWrongQuestionState.source_bank_item_id,
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
                ranked_items.c.question_id == QbWrongQuestionState.question_id,
                ranked_items.c.rank == 1,
            )
            stmt = (
                select(
                    QbBank.id.label('bank_id'),
                    QbBankItem.bank_revision_id,
                    QbBankRevision.name.label('bank_name'),
                    QbBankSection.id.label('section_id'),
                    QbBankSection.name.label('section_name'),
                    func.count(func.distinct(QbWrongQuestionState.question_id)).label('count'),
                )
                .select_from(QbWrongQuestionState)
                .outerjoin(
                    QbBankItem,
                    and_(
                        or_(
                            QbBankItem.id == QbWrongQuestionState.source_bank_item_id,
                            and_(
                                QbBankItem.id.in_(fallback_item_ids),
                                ~has_valid_saved_item,
                            ),
                        ),
                    ),
                )
                .outerjoin(
                    QbBankRevision,
                    QbBankRevision.id == QbBankItem.bank_revision_id,
                )
                .outerjoin(QbBank, QbBank.id == QbBankRevision.bank_id)
                .outerjoin(
                    QbBankSection,
                    QbBankSection.id == QbBankItem.section_id,
                )
                .where(
                    QbWrongQuestionState.user_id == user_id,
                    QbWrongQuestionState.status == 'active',
                    QbWrongQuestionState.deleted == 0,
                )
                .group_by(
                    QbBank.id,
                    QbBankItem.bank_revision_id,
                    QbBankRevision.name,
                    QbBankSection.id,
                    QbBankSection.name,
                )
                .order_by(QbBankRevision.name.nullsfirst(), QbBankSection.name)
            )
        return [dict(row) for row in (await db.execute(stmt)).mappings().all()]


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

    def get_by_wrong_state_select(
        self,
        *,
        user_id: int,
        wrong_state_id: int,
    ) -> Any:
        """构建一道错题的事件时间线游标查询"""
        return (
            select(QbQuestionReview)
            .where(
                QbQuestionReview.user_id == user_id,
                QbQuestionReview.wrong_state_id == wrong_state_id,
                QbQuestionReview.deleted == 0,
            )
            .order_by(QbQuestionReview.reviewed_time.desc(), QbQuestionReview.id.desc())
        )

    async def get_link_ids_batch(
        self,
        db: AsyncSession,
        review_ids: Sequence[int],
    ) -> tuple[dict[int, list[int]], dict[int, list[int]]]:
        """批量获取一页复盘事件的标签和知识点 ID"""
        if not review_ids:
            return {}, {}
        tag_rows = (
            await db.execute(
                select(QbQuestionReviewTag.review_id, QbQuestionReviewTag.tag_id).where(
                    QbQuestionReviewTag.review_id.in_(review_ids),
                    QbQuestionReviewTag.deleted == 0,
                )
            )
        ).all()
        knowledge_rows = (
            await db.execute(
                select(
                    QbQuestionReviewKnowledgePoint.review_id,
                    QbQuestionReviewKnowledgePoint.knowledge_point_id,
                ).where(
                    QbQuestionReviewKnowledgePoint.review_id.in_(review_ids),
                    QbQuestionReviewKnowledgePoint.deleted == 0,
                )
            )
        ).all()
        tag_ids: dict[int, list[int]] = {}
        knowledge_point_ids: dict[int, list[int]] = {}
        for review_id, tag_id in tag_rows:
            tag_ids.setdefault(review_id, []).append(tag_id)
        for review_id, knowledge_point_id in knowledge_rows:
            knowledge_point_ids.setdefault(review_id, []).append(knowledge_point_id)
        return tag_ids, knowledge_point_ids

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
        knowledge_system_id: int | None,
    ) -> set[int]:
        """获取有效知识点 ID"""
        if not knowledge_point_ids:
            return set()
        stmt = (
            select(QbKnowledgePoint.id)
            .join(QbKnowledgeSystem, QbKnowledgeSystem.id == QbKnowledgePoint.system_id)
            .where(
                QbKnowledgePoint.id.in_(knowledge_point_ids),
                QbKnowledgePoint.system_id == knowledge_system_id,
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
        question_id: int,
        items: Sequence[ExternalQuestionAssetParam],
        user_id: int,
    ) -> None:
        """创建外部错题资产关联"""
        db.add_all(
            [
                QbQuestionAsset(
                    question_id=question_id,
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
