from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, String, and_, case, cast, exists, func, literal_column, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.functions import aggregate_strings
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.question_bank_v2.model.asset import QbAsset, QbQuestionAsset
from backend.app.question_bank_v2.model.bank import QbBank, QbBankItem, QbBankRevision, QbBankSection
from backend.app.question_bank_v2.model.catalog import QbBankCategory
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
from backend.app.question_bank_v2.schema.review import (
    ENTRY_METADATA_BATCH_KEY,
    ENTRY_METADATA_DOMAIN_KEY,
    ENTRY_METADATA_MODULE_PATH_KEY,
    ENTRY_METADATA_SECTION_KEY,
    EXTERNAL_ENTRY_SOURCES,
    UNSECTIONED_SECTION_NAME,
    ExternalQuestionAssetParam,
    WrongQuestionFilters,
    WrongQuestionListView,
)


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
    def _section_name_expr() -> Any:
        """章节优先取导入时记录的原试卷章节，题库来源再回退到题库章节"""
        stored = func.nullif(
            func.trim(QbWrongQuestionState.entry_metadata[ENTRY_METADATA_SECTION_KEY].as_string()),
            '',
        )
        saved_section = (
            select(QbBankSection.name)
            .select_from(QbBankItem)
            .join(QbBankSection, and_(QbBankSection.id == QbBankItem.section_id, QbBankSection.deleted == 0))
            .where(
                QbBankItem.id == QbWrongQuestionState.source_bank_item_id,
                QbBankItem.question_id == QbWrongQuestionState.question_id,
                QbBankItem.deleted == 0,
            )
            .limit(1)
            .scalar_subquery()
        )
        bank_section = (
            select(QbBankSection.name)
            .select_from(QbBankItem)
            .join(
                QbBankSection,
                and_(
                    QbBankSection.id == QbBankItem.section_id,
                    QbBankSection.deleted == 0,
                ),
            )
            .where(
                QbBankItem.question_id == QbWrongQuestionState.question_id,
                QbBankItem.deleted == 0,
            )
            .order_by(QbBankItem.id.desc())
            .limit(1)
            .scalar_subquery()
        )
        return func.coalesce(
            stored,
            func.nullif(func.trim(saved_section), ''),
            func.nullif(func.trim(bank_section), ''),
        )

    @staticmethod
    def _pending_review_expr() -> Any:
        """待复盘：从未复盘，或复盘后再次做错"""
        return or_(
            QbWrongQuestionState.review_count == 0,
            and_(
                QbWrongQuestionState.last_reviewed_time.is_not(None),
                QbWrongQuestionState.last_wrong_time > QbWrongQuestionState.last_reviewed_time,
            ),
        )

    @staticmethod
    def _batch_id_expr() -> Any:
        return func.nullif(func.trim(QbWrongQuestionState.entry_metadata[ENTRY_METADATA_BATCH_KEY].as_string()), '')

    @staticmethod
    def _wrong_time_expr() -> Any:
        """优先最近答错时间，历史录入缺失时回退到首次答错或创建时间。"""
        return func.coalesce(
            QbWrongQuestionState.last_wrong_time,
            QbWrongQuestionState.first_wrong_time,
            QbWrongQuestionState.created_time,
        )

    @staticmethod
    def _module_path_expr() -> Any:
        """原试卷模块路径；导入时按最新一次练习快照写入，缺失时为空。"""
        return QbWrongQuestionState.entry_metadata[ENTRY_METADATA_MODULE_PATH_KEY]

    @staticmethod
    def _module_group_expr() -> Any:
        """模块路径二级分类，如“判断推理/图形推理”，用于章节内聚拢题型。"""
        return CRUDWrongQuestionState._module_path_expr()[1].as_string()

    @staticmethod
    def _module_group_rank_expr() -> Any:
        """缺失二级分类的题排在最后，避免游标排序键出现 NULL。"""
        return case((CRUDWrongQuestionState._module_group_expr().is_(None), 1), else_=0)

    @staticmethod
    def _module_group_order_expr() -> Any:
        return func.coalesce(CRUDWrongQuestionState._module_group_expr(), '')

    @staticmethod
    def _list_stmt(view: WrongQuestionListView = 'full', *, include_module_group: bool = False) -> Any:
        if view == 'full':
            columns = [
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
                # 原试卷章节优先，题库来源回退到题库章节，供详情页答题卡分组
                CRUDWrongQuestionState._section_name_expr().label('section_name'),
                func.coalesce(QbUserQuestionMastery.state, 'new').label('mastery_state'),
            ]
        else:
            columns = [
                QbWrongQuestionState.id,
                CRUDWrongQuestionState._section_name_expr().label('section_name'),
            ]
            if view == 'summary':
                columns.extend([
                    QbQuestion.stem.label('_stem'),
                    QbWrongQuestionState.status,
                    QbWrongQuestionState.wrong_count,
                    QbWrongQuestionState.review_count,
                ])
        if include_module_group:
            # 只取二级分类文本，避免把 JSON 数组放进游标分页的唯一性计算。
            columns.extend([
                CRUDWrongQuestionState._module_group_expr().label('module_group'),
                CRUDWrongQuestionState._module_group_rank_expr().label('_module_group_rank'),
                CRUDWrongQuestionState._module_group_order_expr().label('_module_group_order'),
            ])
        stmt = (
            select(*columns)
            .join(
                QbQuestion,
                and_(
                    QbQuestion.id == QbWrongQuestionState.question_id,
                    QbQuestion.deleted == 0,
                ),
            )
            .where(QbWrongQuestionState.deleted == 0)
        )
        if view == 'full':
            stmt = stmt.outerjoin(
                QbUserQuestionMastery,
                and_(
                    QbUserQuestionMastery.user_id == QbWrongQuestionState.user_id,
                    QbUserQuestionMastery.question_id == QbWrongQuestionState.question_id,
                    QbUserQuestionMastery.deleted == 0,
                ),
            )
        return stmt

    @staticmethod
    def _apply_entry_scope(stmt: Any, entry_scope: str | None) -> Any:
        """按题库错题或自主录入收窄范围"""
        if entry_scope == 'bank':
            return stmt.where(QbWrongQuestionState.entry_source == 'attempt')
        if entry_scope == 'external':
            return stmt.where(QbWrongQuestionState.entry_source.in_(EXTERNAL_ENTRY_SOURCES))
        return stmt

    @staticmethod
    def _domain_condition(
        domain_category_ids: Sequence[int],
        *,
        question_id_column: Any,
        metadata_column: Any,
    ) -> Any:
        """领域归属条件

        - 题库错题：题目命中的任一批库挂在当前领域的分类下；
        - 自主录入：录入时把当时的领域写进了 entry_metadata，按记录的领域归属。
        """
        category_ids = list(domain_category_ids)
        bank_in_domain = (
            select(QbBankItem.id)
            .join(QbBankRevision, QbBankRevision.id == QbBankItem.bank_revision_id)
            .join(QbBank, QbBank.id == QbBankRevision.bank_id)
            .join(
                QbBankCategory,
                and_(
                    QbBankCategory.bank_id == QbBank.id,
                    QbBankCategory.deleted == 0,
                ),
            )
            .where(
                QbBankItem.deleted == 0,
                QbBankItem.question_id == question_id_column,
                QbBankCategory.category_id.in_(category_ids),
            )
        )
        recorded_domain = cast(metadata_column[ENTRY_METADATA_DOMAIN_KEY].as_string(), BigInteger)
        # 未记录领域的自主录入（历史数据、扩展导入时拿不到领域）不参与领域过滤：
        # 与写侧「拿不到领域就不写、保持不过滤语义」保持一致，
        # 否则这些题会被领域条件整体排除，表现为「导入成功但列表里看不到」。
        domain_unrecorded = metadata_column[ENTRY_METADATA_DOMAIN_KEY].as_string().is_(None)
        return or_(exists(bank_in_domain), recorded_domain.in_(category_ids), domain_unrecorded)

    @classmethod
    def _apply_domain_scope(
        cls,
        stmt: Any,
        domain_category_ids: Sequence[int] | None,
        *,
        question_id_column: Any | None = None,
        metadata_column: Any | None = None,
    ) -> Any:
        """按领域分类子树收窄错题

        错题本本身是跨领域的全局账本，必须显式限定范围才不会把别的领域题目混进来。
        """
        if domain_category_ids is None:
            return stmt

        return stmt.where(
            cls._domain_condition(
                domain_category_ids,
                question_id_column=(
                    QbWrongQuestionState.question_id if question_id_column is None else question_id_column
                ),
                metadata_column=(QbWrongQuestionState.entry_metadata if metadata_column is None else metadata_column),
            )
        )

    def _apply_list_filters(
        self,
        stmt: Any,
        *,
        user_id: int,
        filters: WrongQuestionFilters,
        domain_category_ids: Sequence[int] | None,
        section_name: str | None = None,
    ) -> Any:
        """错题列表与章节筛选共用的过滤条件"""
        stmt = stmt.where(QbWrongQuestionState.user_id == user_id, QbWrongQuestionState.deleted == 0)
        if filters.status is not None:
            stmt = stmt.where(QbWrongQuestionState.status == filters.status)
        if filters.review_state == 'reviewed':
            # 已复盘：有过复盘记录
            stmt = stmt.where(QbWrongQuestionState.review_count > 0)
        elif filters.review_state == 'pending':
            # 待复盘：尚无复盘记录，或复盘后再次做错
            stmt = stmt.where(self._pending_review_expr())
        if filters.since is not None:
            stmt = stmt.where(self._wrong_time_expr() >= filters.since)
        if filters.entry_source is not None:
            stmt = stmt.where(QbWrongQuestionState.entry_source == filters.entry_source)
        if filters.import_batch_id is not None:
            # 按导入批次收窄：用于「导入记录」里展开某一批的题目
            stmt = stmt.where(self._batch_id_expr() == filters.import_batch_id)
        if filters.bank_id is not None:
            # 按题库收窄：集合详情页看某个题库下的错题
            stmt = stmt.where(
                QbWrongQuestionState.source_bank_item_id.in_(
                    select(QbBankItem.id)
                    .join(QbBankRevision, QbBankRevision.id == QbBankItem.bank_revision_id)
                    .where(QbBankRevision.bank_id == filters.bank_id)
                )
            )
        if filters.external_unbatched:
            # 无批次的散题集合
            stmt = stmt.where(
                QbWrongQuestionState.entry_source.in_(EXTERNAL_ENTRY_SOURCES),
                self._batch_id_expr().is_(None),
                QbWrongQuestionState.source_bank_item_id.is_(None),
            )
        if filters.unassigned:
            stmt = stmt.where(
                QbWrongQuestionState.entry_source.not_in(EXTERNAL_ENTRY_SOURCES),
                QbWrongQuestionState.source_bank_item_id.is_(None),
                self._batch_id_expr().is_(None),
            )
        stmt = self._apply_section_filter(stmt, section_name)
        stmt = self._apply_entry_scope(stmt, filters.entry_scope)
        return self._apply_domain_scope(stmt, domain_category_ids)

    def _apply_section_filter(self, stmt: Any, section_name: str | None) -> Any:
        if section_name is None:
            return stmt
        section_expr = self._section_name_expr()
        condition = section_expr.is_(None) if section_name == UNSECTIONED_SECTION_NAME else section_expr == section_name
        return stmt.where(condition)

    def get_list_select(
        self,
        *,
        user_id: int,
        filters: WrongQuestionFilters,
        domain_category_ids: Sequence[int] | None = None,
        section_name: str | None = None,
        view: WrongQuestionListView = 'full',
    ) -> Any:
        """构建用户错题游标分页查询

        章节内先把相同模块路径的题排在一起，方便按图形推理、逻辑判断等题型浏览；
        其他入口仍按最近答错时间排序。
        """
        include_module_group = section_name is not None
        stmt = self._apply_list_filters(
            self._list_stmt(view, include_module_group=include_module_group),
            user_id=user_id,
            filters=filters,
            domain_category_ids=domain_category_ids,
            section_name=section_name,
        )
        if view != 'full':
            # 游标编码仍需要排序键；响应 Schema 会过滤这些内部字段。
            stmt = stmt.add_columns(QbWrongQuestionState.is_pinned, QbWrongQuestionState.last_wrong_time)
        order_by = [QbWrongQuestionState.is_pinned.desc()]
        if include_module_group:
            # 按二级分类排序，避免路径层级不同导致同一题型被拆到两段。
            order_by.extend([
                self._module_group_rank_expr().asc(),
                self._module_group_order_expr().asc(),
            ])
        order_by.extend([
            QbWrongQuestionState.last_wrong_time.desc().nullslast(),
            QbWrongQuestionState.id.desc(),
        ])
        return stmt.order_by(*order_by)

    async def get_section_counts(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        filters: WrongQuestionFilters,
        domain_category_ids: Sequence[int] | None = None,
    ) -> tuple[int, list[dict[str, Any]]]:
        """按原试卷模块统计当前集合的题量，供集合详情页章节筛选"""
        section_expr = self._section_name_expr()
        stmt = (
            select(
                section_expr.label('section_name'),
                func.count().label('total'),
            )
            .select_from(QbWrongQuestionState)
            .join(QbQuestion, and_(QbQuestion.id == QbWrongQuestionState.question_id, QbQuestion.deleted == 0))
        )
        stmt = self._apply_list_filters(
            stmt,
            user_id=user_id,
            filters=filters,
            domain_category_ids=domain_category_ids,
        )
        rows = (await db.execute(stmt.group_by(section_expr))).mappings().all()
        total = sum(int(row['total']) for row in rows)
        items = [
            {
                'section_name': str(row['section_name']) if row['section_name'] else UNSECTIONED_SECTION_NAME,
                'total': int(row['total']),
            }
            for row in rows
        ]
        items.sort(key=lambda item: (-item['total'], item['section_name']))
        return total, items

    async def get_browse_total(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        status: str,
        review_state: str | None,
        domain_category_ids: Sequence[int] | None,
        since: datetime | None = None,
    ) -> int:
        """浏览总数取同一题目查询，不累加可能重叠的集合，也不只计算当前页。"""
        scoped = (
            self
            .get_list_select(
                user_id=user_id,
                filters=WrongQuestionFilters(status=status, review_state=review_state, since=since),
                domain_category_ids=domain_category_ids,
                view='outline',
            )
            .with_only_columns(QbWrongQuestionState.id, maintain_column_froms=True)
            .order_by(None)
            .subquery()
        )
        return int((await db.execute(select(func.count()).select_from(scoped))).scalar_one())

    @staticmethod
    def _review_knowledge_subtree(knowledge_point_id: int) -> Any:
        """按稳定知识点 ID 展开同一启用体系的子孙，不依赖历史物化路径格式。"""
        subtree = (
            select(QbKnowledgePoint.id, QbKnowledgePoint.system_id)
            .join(QbKnowledgeSystem, QbKnowledgeSystem.id == QbKnowledgePoint.system_id)
            .where(
                QbKnowledgePoint.id == knowledge_point_id,
                QbKnowledgePoint.deleted == 0,
                QbKnowledgeSystem.deleted == 0,
                QbKnowledgeSystem.status == 'active',
            )
            .cte('review_knowledge_subtree', recursive=True)
        )
        return subtree.union(
            select(QbKnowledgePoint.id, QbKnowledgePoint.system_id)
            .join(
                subtree,
                and_(
                    QbKnowledgePoint.parent_id == subtree.c.id,
                    QbKnowledgePoint.system_id == subtree.c.system_id,
                ),
            )
            .where(QbKnowledgePoint.deleted == 0)
        )

    def get_reviewed_list_select(
        self,
        *,
        user_id: int,
        mastery_state: str | None,
        tag_id: int | None,
        knowledge_point_id: int | None,
        keyword: str | None = None,
        domain_category_ids: Sequence[int] | None = None,
    ) -> Any:
        """构建复盘档案游标分页查询"""
        stmt = self._list_stmt().where(
            QbWrongQuestionState.user_id == user_id,
            QbWrongQuestionState.review_count > 0,
        )
        stmt = self._apply_domain_scope(stmt, domain_category_ids)
        if keyword and keyword.strip():
            stmt = stmt.where(QbQuestion.stem.ilike(f'%{keyword.strip()}%'))
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
            subtree = self._review_knowledge_subtree(knowledge_point_id)
            stmt = stmt.where(
                exists(
                    select(QbQuestionReviewKnowledgePoint.id)
                    .join(QbQuestionReview, QbQuestionReview.id == QbQuestionReviewKnowledgePoint.review_id)
                    .where(
                        QbQuestionReview.wrong_state_id == QbWrongQuestionState.id,
                        QbQuestionReview.user_id == user_id,
                        QbQuestionReview.deleted == 0,
                        QbQuestionReview.event_type == 'review',
                        QbQuestionReviewKnowledgePoint.knowledge_point_id.in_(select(subtree.c.id)),
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
        domain_category_ids: Sequence[int] | None = None,
        since: datetime | None = None,
    ) -> Any:
        """构建待复盘队列游标分页查询

        口径：仍活跃且从未复盘，或上次复盘后又重新答错的题才需要再次复盘。
        """
        return self.get_list_select(
            user_id=user_id,
            filters=WrongQuestionFilters(entry_scope=entry_scope, review_state='pending', since=since),
            domain_category_ids=domain_category_ids,
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
            self
            ._list_stmt()
            .add_columns(
                QbWrongQuestionState.last_wrong_response,
                QbQuestion.option_data,
                QbQuestionAnswer.answer_data,
                QbQuestionExplanation.content.label('explanation'),
                QbBankRevision.name.label('bank_name'),
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
            (await db.execute(select(func.count()).select_from(QbWrongQuestionState).where(*conditions))).scalar_one()
        )
        stmt = (
            self
            ._list_stmt()
            .where(*conditions)
            .order_by(QbWrongQuestionState.next_practice_time, QbWrongQuestionState.id)
            .limit(limit)
        )
        rows = [dict(row) for row in (await db.execute(stmt)).mappings().all()]
        return total, rows

    async def get_statistics(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        now: datetime,
        domain_category_ids: Sequence[int] | None = None,
    ) -> dict[str, int]:
        """获取用户错题状态汇总"""
        stmt = (
            select(
                func.count(QbWrongQuestionState.id).label('total_count'),
                func.sum(case((QbWrongQuestionState.status == 'active', 1), else_=0)).label('active_count'),
                func.sum(case((QbWrongQuestionState.status == 'resolved', 1), else_=0)).label('resolved_count'),
                func.coalesce(func.sum(QbWrongQuestionState.wrong_count), 0).label('wrong_occurrence_count'),
                func.sum(case((QbWrongQuestionState.review_count > 0, 1), else_=0)).label('reviewed_count'),
                func.sum(
                    case(
                        (and_(QbWrongQuestionState.status == 'active', QbWrongQuestionState.review_count > 0), 1),
                        else_=0,
                    )
                ).label('active_reviewed_count'),
                func.sum(
                    case(
                        (
                            and_(
                                QbWrongQuestionState.status == 'active',
                                self._pending_review_expr(),
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
            )
            .where(QbWrongQuestionState.user_id == user_id, QbWrongQuestionState.deleted == 0)
            .join(QbQuestion, and_(QbQuestion.id == QbWrongQuestionState.question_id, QbQuestion.deleted == 0))
        )
        # 计数必须和列表用同一套领域口径，否则会出现「列表 3 条、角标 28」
        stmt = self._apply_domain_scope(stmt, domain_category_ids)
        row = (await db.execute(stmt)).mappings().one()
        return {key: int(value or 0) for key, value in row.items()}

    async def get_dashboard_rows(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        since: datetime,
        knowledge_system_ids: Sequence[int],
        domain_category_ids: Sequence[int] | None = None,
    ) -> tuple[int, list[dict[str, Any]], list[dict[str, Any]]]:
        """按用户复盘时主观选择的标签和知识点聚合分布"""
        review_scope_stmt = (
            select(QbQuestionReview.id)
            # 事件本身不带 entry_metadata，领域归属要回到错题状态上取（FK 保证状态行存在）
            .join(
                QbWrongQuestionState,
                QbWrongQuestionState.id == QbQuestionReview.wrong_state_id,
            )
            .join(QbQuestion, and_(QbQuestion.id == QbQuestionReview.question_id, QbQuestion.deleted == 0))
            .where(
                QbQuestionReview.user_id == user_id,
                QbQuestionReview.deleted == 0,
                QbQuestionReview.event_type == 'review',
                QbQuestionReview.reviewed_time >= since,
                QbWrongQuestionState.user_id == user_id,
                QbWrongQuestionState.deleted == 0,
            )
        )
        review_scope_stmt = self._apply_domain_scope(
            review_scope_stmt,
            domain_category_ids,
            question_id_column=QbQuestionReview.question_id,
            metadata_column=QbWrongQuestionState.entry_metadata,
        )
        review_scope = review_scope_stmt.subquery()
        event_count = int((await db.execute(select(func.count()).select_from(review_scope))).scalar_one())
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
        # 祖先关系完全从 parent_id 展开；同一次复盘选择父级和多个子点时，父级只计一次。
        ancestors = (
            select(
                QbKnowledgePoint.id.label('point_id'),
                QbKnowledgePoint.id.label('ancestor_id'),
                QbKnowledgePoint.parent_id,
                QbKnowledgePoint.system_id,
            )
            .where(
                QbKnowledgePoint.system_id.in_(list(knowledge_system_ids) or [0]),
                QbKnowledgePoint.deleted == 0,
            )
            .cte('review_point_ancestors', recursive=True)
        )
        parent = QbKnowledgePoint.__table__.alias('review_point_parent')
        ancestors = ancestors.union(
            select(ancestors.c.point_id, parent.c.id, parent.c.parent_id, parent.c.system_id).join(
                parent,
                and_(
                    parent.c.id == ancestors.c.parent_id,
                    parent.c.system_id == ancestors.c.system_id,
                    parent.c.deleted == 0,
                ),
            )
        )
        knowledge_rows_select = (
            select(
                QbKnowledgePoint.id,
                QbKnowledgePoint.name,
                QbKnowledgePoint.parent_id,
                QbKnowledgePoint.sort_order,
                QbKnowledgeSystem.name.label('system_name'),
                func.count(func.distinct(review_scope.c.id)).label('count'),
            )
            .select_from(QbQuestionReviewKnowledgePoint)
            .join(review_scope, review_scope.c.id == QbQuestionReviewKnowledgePoint.review_id)
            .join(
                ancestors,
                ancestors.c.point_id == QbQuestionReviewKnowledgePoint.knowledge_point_id,
            )
            .join(QbKnowledgePoint, QbKnowledgePoint.id == ancestors.c.ancestor_id)
            .join(QbKnowledgeSystem, QbKnowledgeSystem.id == QbKnowledgePoint.system_id)
            .where(
                QbQuestionReviewKnowledgePoint.deleted == 0,
                QbKnowledgeSystem.deleted == 0,
                QbKnowledgeSystem.status == 'active',
            )
        )
        knowledge_rows = [
            dict(row)
            for row in (
                await db.execute(
                    knowledge_rows_select.group_by(
                        QbKnowledgePoint.id,
                        QbKnowledgePoint.name,
                        QbKnowledgePoint.parent_id,
                        QbKnowledgePoint.sort_order,
                        QbKnowledgeSystem.name,
                    ).order_by(
                        func.count(func.distinct(review_scope.c.id)).desc(),
                        QbKnowledgePoint.sort_order,
                        QbKnowledgePoint.id,
                    )
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
        knowledge_system_ids: Sequence[int],
        domain_category_ids: Sequence[int] | None = None,
    ) -> list[dict[str, Any]]:
        """按题库篇章或知识点统计活跃错题"""
        if group_by == 'knowledge_point':
            knowledge_scope = case(
                (QbWrongQuestionState.entry_source.in_(EXTERNAL_ENTRY_SOURCES), 'external'),
                else_='bank',
            ).label('entry_scope')
            stmt = (
                select(
                    QbKnowledgePoint.id,
                    QbKnowledgePoint.name,
                    func.count(func.distinct(QbWrongQuestionState.question_id)).label('count'),
                    knowledge_scope,
                    aggregate_strings(func.distinct(QbWrongQuestionState.question_id.cast(String)), ',').label(
                        'question_ids_csv'
                    ),
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
            if not knowledge_system_ids:
                return []
            stmt = stmt.where(QbKnowledgePoint.system_id.in_(list(knowledge_system_ids)))
            stmt = self._apply_domain_scope(stmt, domain_category_ids)
            stmt = stmt.group_by(
                QbKnowledgePoint.id,
                QbKnowledgePoint.name,
                QbKnowledgePoint.sort_order,
                knowledge_scope,
            ).order_by(QbKnowledgePoint.sort_order, QbKnowledgePoint.id, knowledge_scope)
            knowledge_rows = []
            for row in (await db.execute(stmt)).mappings().all():
                result = dict(row)
                question_ids_csv = result.pop('question_ids_csv', None)
                result['question_ids'] = (
                    [int(question_id) for question_id in question_ids_csv.split(',')] if question_ids_csv else []
                )
                knowledge_rows.append(result)
            return knowledge_rows
        # 窗口函数只需对当前用户的错题题目范围计算一次，避免按错题行重复触发全表扫描；
        # 用 CTE 物化后先解析每道错题最终归属的 bank item，再 JOIN，规避 OR 条件导致的笛卡尔扫描
        user_wrongs = (
            select(
                QbWrongQuestionState.question_id,
                QbWrongQuestionState.source_bank_item_id,
            )
            .where(
                QbWrongQuestionState.user_id == user_id,
                QbWrongQuestionState.status == 'active',
                QbWrongQuestionState.deleted == 0,
                QbWrongQuestionState.entry_source == 'attempt',
            )
            .cte('user_wrongs')
        )
        ranked_items = (
            select(
                QbBankItem.id,
                QbBankItem.question_id,
                func
                .row_number()
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
            .where(QbBankItem.question_id.in_(select(user_wrongs.c.question_id)))
            .cte('ranked_items')
        )
        fallback_item_ids = (
            select(ranked_items.c.question_id, ranked_items.c.id.label('item_id'))
            .where(ranked_items.c.rank == 1)
            .subquery()
        )
        saved_item = QbBankItem.__table__.alias('saved_wrong_bank_item')
        resolved = (
            select(
                user_wrongs.c.question_id,
                case(
                    (saved_item.c.id.is_not(None), user_wrongs.c.source_bank_item_id),
                    else_=fallback_item_ids.c.item_id,
                ).label('item_id'),
            )
            .select_from(user_wrongs)
            .outerjoin(saved_item, saved_item.c.id == user_wrongs.c.source_bank_item_id)
            .outerjoin(
                fallback_item_ids,
                fallback_item_ids.c.question_id == user_wrongs.c.question_id,
            )
            .cte('resolved')
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
                resolved,
                resolved.c.question_id == QbWrongQuestionState.question_id,
            )
            .outerjoin(QbBankItem, QbBankItem.id == resolved.c.item_id)
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
                QbWrongQuestionState.entry_source == 'attempt',
            )
        )
        stmt = self._apply_domain_scope(stmt, domain_category_ids)
        if domain_category_ids is not None:
            # 题目可能同时存在于多个领域；分组还必须限制最终展示的题库。
            stmt = stmt.where(
                exists(
                    select(QbBankCategory.id).where(
                        QbBankCategory.bank_id == QbBank.id,
                        QbBankCategory.deleted == 0,
                        QbBankCategory.category_id.in_(list(domain_category_ids)),
                    )
                )
            )
        stmt = stmt.group_by(
            QbBank.id,
            QbBankItem.bank_revision_id,
            QbBankRevision.name,
            QbBankSection.id,
            QbBankSection.name,
        ).order_by(QbBankRevision.name.nullsfirst(), QbBankSection.name)
        external_source = func.coalesce(
            func.nullif(QbWrongQuestionState.entry_metadata['source'].as_string(), ''),
            '未填写来源',
        )
        external_stmt = select(
            external_source.label('external_source'),
            func.count(func.distinct(QbWrongQuestionState.question_id)).label('count'),
            aggregate_strings(func.distinct(QbWrongQuestionState.question_id.cast(String)), ',').label(
                'question_ids_csv'
            ),
        ).where(
            QbWrongQuestionState.user_id == user_id,
            QbWrongQuestionState.status == 'active',
            QbWrongQuestionState.deleted == 0,
            QbWrongQuestionState.entry_source.in_(EXTERNAL_ENTRY_SOURCES),
        )
        # 自主录入按录入时记录的领域归属
        external_stmt = self._apply_domain_scope(external_stmt, domain_category_ids)
        external_stmt = external_stmt.group_by(external_source).order_by(external_source)
        rows = []
        for row in (await db.execute(stmt)).mappings().all():
            result = dict(row)
            # 题库分组不下发题目 ID：列表只做统计展示，
            # 投递与导出按 bank_id/section_id 上下文由会话/采集接口现查
            result['question_ids'] = []
            rows.append(result)
        for row in (await db.execute(external_stmt)).mappings().all():
            question_ids_csv = row['question_ids_csv']
            rows.append({
                'bank_id': None,
                'bank_revision_id': None,
                'bank_name': None,
                'section_id': None,
                'section_name': None,
                'count': int(row['count'] or 0),
                'question_ids': (
                    [int(question_id) for question_id in question_ids_csv.split(',')] if question_ids_csv else []
                ),
                'external_source': row['external_source'],
            })
        return rows

    async def get_collection_counts(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        status: str = 'active',
        domain_category_ids: Sequence[int] | None = None,
        since: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """按集合统计错题：题库、导入批次、无批次散题三类集合

        集合是「已复盘 / 待复盘」两页共用的分组单位：
        题库来源按题库分组，自己导入/录入的按导入批次分组，无批次的归为散题集合。
        """
        reviewed_flag = case((QbWrongQuestionState.review_count > 0, 1), else_=0)
        pending_flag = case((and_(QbWrongQuestionState.status == 'active', self._pending_review_expr()), 1), else_=0)
        last_time = func.max(
            QbWrongQuestionState.resolved_time if status == 'resolved' else QbWrongQuestionState.last_wrong_time
        )
        base_filters = [
            QbWrongQuestionState.user_id == user_id,
            QbWrongQuestionState.deleted == 0,
            QbWrongQuestionState.status == status,
            exists(
                select(QbQuestion.id).where(QbQuestion.id == QbWrongQuestionState.question_id, QbQuestion.deleted == 0)
            ),
        ]
        if since is not None:
            base_filters.append(self._wrong_time_expr() >= since)

        bank_stmt = (
            select(
                QbBank.id.label('bank_id'),
                func.min(QbBankRevision.name).label('title'),
                func.count().label('total'),
                func.sum(reviewed_flag).label('reviewed'),
                func.sum(pending_flag).label('pending'),
                last_time.label('last_time'),
            )
            .select_from(QbWrongQuestionState)
            .join(QbBankItem, QbBankItem.id == QbWrongQuestionState.source_bank_item_id)
            .join(QbBankRevision, QbBankRevision.id == QbBankItem.bank_revision_id)
            .join(QbBank, QbBank.id == QbBankRevision.bank_id)
            .where(*base_filters, QbWrongQuestionState.source_bank_item_id.is_not(None))
            .group_by(QbBank.id)
        )
        bank_stmt = self._apply_domain_scope(bank_stmt, domain_category_ids)

        batch_expr = self._batch_id_expr()
        batch_stmt = (
            select(
                batch_expr.label('batch_id'),
                func.min(QbWrongQuestionState.entry_metadata['source'].as_string()).label('title'),
                func.count().label('total'),
                func.sum(reviewed_flag).label('reviewed'),
                func.sum(pending_flag).label('pending'),
                last_time.label('last_time'),
            )
            .where(*base_filters, batch_expr.is_not(None))
            .group_by(literal_column('1'))
        )
        batch_stmt = self._apply_domain_scope(batch_stmt, domain_category_ids)

        single_stmt = select(
            func.count().label('total'),
            func.sum(reviewed_flag).label('reviewed'),
            func.sum(pending_flag).label('pending'),
            last_time.label('last_time'),
        ).where(
            *base_filters,
            QbWrongQuestionState.entry_source.in_(EXTERNAL_ENTRY_SOURCES),
            batch_expr.is_(None),
            QbWrongQuestionState.source_bank_item_id.is_(None),
        )
        single_stmt = self._apply_domain_scope(single_stmt, domain_category_ids)

        unassigned_stmt = select(
            func.count().label('total'),
            func.sum(reviewed_flag).label('reviewed'),
            func.sum(pending_flag).label('pending'),
            last_time.label('last_time'),
        ).where(
            *base_filters,
            QbWrongQuestionState.entry_source.not_in(EXTERNAL_ENTRY_SOURCES),
            batch_expr.is_(None),
            QbWrongQuestionState.source_bank_item_id.is_(None),
        )
        unassigned_stmt = self._apply_domain_scope(unassigned_stmt, domain_category_ids)

        collections: list[dict[str, Any]] = []

        for row in (await db.execute(bank_stmt)).mappings().all():
            total = int(row['total'] or 0)
            reviewed = int(row['reviewed'] or 0)
            pending = int(row['pending'] or 0)
            collections.append({
                'collection_id': str(int(row['bank_id'])),
                'collection_type': 'bank',
                'title': row['title'] or '未知题库',
                'total': total,
                'reviewed': reviewed,
                'pending': pending,
                'mastered': total if status == 'resolved' else 0,
                'last_time': row['last_time'],
            })

        for row in (await db.execute(batch_stmt)).mappings().all():
            total = int(row['total'] or 0)
            reviewed = int(row['reviewed'] or 0)
            pending = int(row['pending'] or 0)
            collections.append({
                'collection_id': str(row['batch_id']),
                'collection_type': 'import',
                'title': row['title'] or '未命名导入批次',
                'total': total,
                'reviewed': reviewed,
                'pending': pending,
                'mastered': total if status == 'resolved' else 0,
                'last_time': row['last_time'],
            })

        single_row = (await db.execute(single_stmt)).mappings().first()
        if single_row is not None and int(single_row['total'] or 0) > 0:
            total = int(single_row['total'] or 0)
            reviewed = int(single_row['reviewed'] or 0)
            pending = int(single_row['pending'] or 0)
            collections.append({
                'collection_id': '',
                'collection_type': 'single',
                'title': '单条录入',
                'total': total,
                'reviewed': reviewed,
                'pending': pending,
                'mastered': total if status == 'resolved' else 0,
                'last_time': single_row['last_time'],
            })

        unassigned_row = (await db.execute(unassigned_stmt)).mappings().first()
        if unassigned_row is not None and int(unassigned_row['total'] or 0) > 0:
            total = int(unassigned_row['total'])
            collections.append({
                'collection_id': '',
                'collection_type': 'unassigned',
                'title': '未归集错题',
                'total': total,
                'reviewed': int(unassigned_row['reviewed'] or 0),
                'pending': int(unassigned_row['pending'] or 0),
                'mastered': total if status == 'resolved' else 0,
                'last_time': unassigned_row['last_time'],
            })

        return collections


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
        event_type: str | None = None,
    ) -> Any:
        """构建一道错题的事件时间线游标查询"""
        stmt = (
            select(QbQuestionReview)
            .where(
                QbQuestionReview.user_id == user_id,
                QbQuestionReview.wrong_state_id == wrong_state_id,
                QbQuestionReview.deleted == 0,
            )
            .order_by(QbQuestionReview.reviewed_time.desc(), QbQuestionReview.id.desc())
        )
        if event_type is not None:
            stmt = stmt.where(QbQuestionReview.event_type == event_type)
        return stmt

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
        db.add_all([
            QbQuestionReviewKnowledgePoint(
                review_id=review_id,
                knowledge_point_id=knowledge_point_id,
            )
            for knowledge_point_id in knowledge_point_ids
        ])
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
        knowledge_system_id: int,
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
        db.add_all([
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
        ])
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
