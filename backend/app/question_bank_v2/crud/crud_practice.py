import secrets

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import String, and_, case, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.question_bank_v2.crud.crud_composition import bank_section_dao
from backend.app.question_bank_v2.model.bank import QbBank, QbBankItem, QbBankRevision, QbBankSection
from backend.app.question_bank_v2.model.catalog import QbBankCategory
from backend.app.question_bank_v2.model.knowledge import QbKnowledgePoint, QbQuestionKnowledgePoint
from backend.app.question_bank_v2.model.practice import (
    QbPracticeSession,
    QbPracticeSessionItem,
    QbPracticeSessionResponse,
    QbQuestionAttempt,
)
from backend.app.question_bank_v2.model.question import (
    QbQuestion,
    QbQuestionAnswer,
    QbQuestionExplanation,
)
from backend.app.question_bank_v2.model.review import (
    QbQuestionReview,
    QbQuestionReviewKnowledgePoint,
    QbQuestionReviewTag,
    QbReviewTag,
    QbWrongQuestionState,
)
from backend.app.question_bank_v2.model.user_content import QbQuestionFavorite, QbQuestionNote
from backend.app.question_bank_v2.schema.review import ENTRY_METADATA_SECTION_KEY
from backend.app.question_bank_v2.utils.external_practice import online_session_condition
from backend.core.conf import settings


@dataclass(frozen=True, slots=True)
class PracticeCandidate:
    """自由组题候选题的固定投递上下文"""

    question_id: int
    bank_item_id: int | None
    max_score: Decimal
    display_config: dict[str, Any]


def _session_section_name(session_id: int) -> ColumnElement[str | None]:
    """题库章节优先；自主导入题回退到会话所属用户保存的原卷章节"""
    imported_section = (
        select(QbWrongQuestionState.entry_metadata[ENTRY_METADATA_SECTION_KEY].as_string())
        .join(
            QbPracticeSession,
            and_(
                QbPracticeSession.id == session_id,
                QbPracticeSession.user_id == QbWrongQuestionState.user_id,
            ),
        )
        .where(
            QbWrongQuestionState.question_id == QbPracticeSessionItem.question_id,
            QbWrongQuestionState.deleted == 0,
        )
        .correlate(QbPracticeSessionItem)
        .scalar_subquery()
    )
    return func.coalesce(QbBankSection.name, func.nullif(func.trim(imported_section), '')).label('section_name')


def _filter_values(value: str | Sequence[str] | None) -> list[str]:
    """把筛选条件归一成去重后的列表，兼容单值、逗号分隔与多值传参"""
    if value is None:
        return []
    raw = [value] if isinstance(value, str) else list(value)
    items: list[str] = []
    for item in raw:
        items.extend(part.strip() for part in str(item).split(','))
    return [item for item in dict.fromkeys(items) if item]


def build_region_filter(region: str | None) -> ColumnElement[bool] | None:
    """
    构建题库地区关键字模糊匹配条件

    地区在 v2 没有独立字段，沿用 v1 语义按题库版本名称、稳定编码和描述模糊匹配。
    调用方需自行保证语句里已经 join 了 QbBankRevision 与 QbBank。

    :param region: 地区关键字
    :return:
    """
    region_text = (region or '').strip()
    if not region_text:
        return None
    pattern = f'%{region_text}%'
    return or_(
        QbBankRevision.name.ilike(pattern),
        QbBank.code.ilike(pattern),
        QbBankRevision.description.ilike(pattern),
    )


def _random_order() -> Any:
    """跨库随机排序表达式"""
    return func.rand() if settings.DATABASE_TYPE == 'mysql' else func.random()


def build_attempt_priority(
    question_id_col: Any,
    user_id: int | None,
) -> tuple[ColumnElement[bool], Any] | None:
    """
    构建「未做优先 + 最久没练优先」所需的判定表达式

    只统计真实作答事实（qbank_v2_question_attempt）：只打开没提交不算做过。

    :param question_id_col: 与作答表 question_id 对齐的题目 ID 列
    :param user_id: 当前用户，为空时不启用优先级
    :return: (已做判定条件, 最近作答时间标量)；未启用时返回 None
    """
    if user_id is None:
        return None
    user_attempts = (
        QbQuestionAttempt.user_id == user_id,
        QbQuestionAttempt.question_id == question_id_col,
        QbQuestionAttempt.deleted == 0,
    )
    attempted = select(QbQuestionAttempt.id).where(*user_attempts).exists()
    last_submitted = select(func.max(QbQuestionAttempt.submitted_time)).where(*user_attempts).scalar_subquery()
    return attempted, last_submitted


class CRUDPracticeSession(CRUDPlus[QbPracticeSession]):
    """练习会话数据库操作类"""

    async def get_by_key(
        self,
        db: AsyncSession,
        session_key: str,
        *,
        user_id: int | None = None,
        for_update: bool = False,
    ) -> QbPracticeSession | None:
        """通过会话标识获取练习会话"""
        stmt = select(QbPracticeSession).where(
            QbPracticeSession.session_key == session_key,
            QbPracticeSession.deleted == 0,
        )
        if user_id is not None:
            stmt = stmt.where(QbPracticeSession.user_id == user_id)
        if for_update:
            stmt = stmt.with_for_update()
        result = await db.execute(stmt)
        return result.scalars().first()

    async def get_owned_item(
        self,
        db: AsyncSession,
        *,
        session_key: str,
        user_id: int,
        session_item_id: int,
        for_update: bool = False,
    ) -> tuple[QbPracticeSession, QbPracticeSessionItem] | None:
        """获取当前用户会话中的投递题目"""
        stmt = (
            select(QbPracticeSession, QbPracticeSessionItem)
            .join(
                QbPracticeSessionItem,
                and_(
                    QbPracticeSessionItem.session_id == QbPracticeSession.id,
                    QbPracticeSessionItem.id == session_item_id,
                    QbPracticeSessionItem.deleted == 0,
                ),
            )
            .where(
                QbPracticeSession.session_key == session_key,
                QbPracticeSession.user_id == user_id,
                QbPracticeSession.deleted == 0,
            )
        )
        if for_update:
            stmt = stmt.with_for_update()
        result = await db.execute(stmt)
        row = result.first()
        return (row[0], row[1]) if row is not None else None

    async def get_detail(
        self,
        db: AsyncSession,
        session_key: str,
        user_id: int,
    ) -> dict[str, Any] | None:
        """获取用户练习会话聚合详情"""
        stmt = (
            select(
                QbPracticeSession.id,
                QbPracticeSession.session_key,
                QbPracticeSession.user_id,
                QbPracticeSession.bank_revision_id,
                QbBankRevision.bank_id,
                QbPracticeSession.mode,
                QbPracticeSession.source_type,
                QbPracticeSession.source_ref,
                QbPracticeSession.title_snapshot,
                QbPracticeSession.status,
                QbPracticeSession.started_time,
                QbPracticeSession.submitted_time,
                QbPracticeSession.expires_time,
                QbPracticeSession.total_items,
                QbPracticeSession.answered_items,
                QbPracticeSession.correct_items,
                QbPracticeSession.score,
                QbPracticeSession.delivery_config,
                QbPracticeSession.source_snapshot,
                QbPracticeSession.created_time,
                QbPracticeSession.updated_time,
            )
            .outerjoin(
                QbBankRevision,
                and_(
                    QbBankRevision.id == QbPracticeSession.bank_revision_id,
                    QbBankRevision.deleted == 0,
                ),
            )
            .where(
                QbPracticeSession.session_key == session_key,
                QbPracticeSession.user_id == user_id,
                QbPracticeSession.deleted == 0,
            )
        )
        result = await db.execute(stmt)
        row = result.mappings().first()
        return dict(row) if row is not None else None

    def get_list_select(
        self,
        *,
        user_id: int,
        status: str | Sequence[str] | None,
        mode: str | Sequence[str] | None,
        source_type: str | None,
        bank_id: int | None,
        created_after: datetime | None = None,
        category_ids: list[int] | None = None,
    ) -> Select:
        """构建用户练习会话分页查询"""
        user_session_ids = select(QbPracticeSession.id).where(
            QbPracticeSession.user_id == user_id,
            QbPracticeSession.deleted == 0,
            online_session_condition(),
        )
        response_stats = (
            select(
                QbPracticeSessionResponse.session_id,
                func.count(
                    case((
                        QbPracticeSessionResponse.status.in_({'submitted', 'graded', 'review_required'}),
                        QbPracticeSessionResponse.id,
                    ))
                ).label('answered_items'),
                func.count(case((QbPracticeSessionResponse.is_correct.is_not(None), 1))).label('graded_items'),
                func.count(case((QbPracticeSessionResponse.is_correct.is_(True), 1))).label('correct_items'),
                func.count(case((QbPracticeSessionResponse.is_correct.is_(False), 1))).label('wrong_items'),
                func.coalesce(func.sum(QbPracticeSessionResponse.duration_ms), 0).label('total_duration_ms'),
            )
            .where(
                QbPracticeSessionResponse.session_id.in_(user_session_ids),
                QbPracticeSessionResponse.deleted == 0,
            )
            .group_by(QbPracticeSessionResponse.session_id)
            .subquery()
        )
        score_stats = (
            select(
                QbPracticeSessionItem.session_id,
                func.coalesce(func.sum(QbPracticeSessionItem.max_score), 0).label('total_score'),
            )
            .where(
                QbPracticeSessionItem.session_id.in_(user_session_ids),
                QbPracticeSessionItem.deleted == 0,
            )
            .group_by(QbPracticeSessionItem.session_id)
            .subquery()
        )
        graded_items = func.coalesce(response_stats.c.graded_items, 0)
        correct_items = func.coalesce(response_stats.c.correct_items, 0)
        stmt = (
            select(
                QbPracticeSession.id,
                QbPracticeSession.session_key,
                QbBankRevision.bank_id,
                QbPracticeSession.bank_revision_id,
                QbPracticeSession.mode,
                QbPracticeSession.source_type,
                QbPracticeSession.source_ref,
                QbPracticeSession.title_snapshot,
                QbPracticeSession.status,
                QbPracticeSession.total_items,
                func.coalesce(response_stats.c.answered_items, 0).label('answered_items'),
                graded_items.label('graded_items'),
                correct_items.label('correct_items'),
                func.coalesce(response_stats.c.wrong_items, 0).label('wrong_items'),
                case((graded_items > 0, correct_items * 1.0 / graded_items), else_=0).label('accuracy_rate'),
                QbPracticeSession.score,
                func.coalesce(score_stats.c.total_score, 0).label('total_score'),
                func.coalesce(response_stats.c.total_duration_ms, 0).label('total_duration_ms'),
                QbPracticeSession.delivery_config,
                QbPracticeSession.source_snapshot,
                QbPracticeSession.started_time,
                QbPracticeSession.submitted_time,
                QbPracticeSession.expires_time,
                QbPracticeSession.created_time,
                QbPracticeSession.updated_time,
            )
            .outerjoin(
                QbBankRevision,
                and_(
                    QbBankRevision.id == QbPracticeSession.bank_revision_id,
                    QbBankRevision.deleted == 0,
                ),
            )
            .outerjoin(response_stats, response_stats.c.session_id == QbPracticeSession.id)
            .outerjoin(score_stats, score_stats.c.session_id == QbPracticeSession.id)
            .where(QbPracticeSession.user_id == user_id, QbPracticeSession.deleted == 0, online_session_condition())
            .order_by(QbPracticeSession.created_time.desc(), QbPracticeSession.id.desc())
        )
        if statuses := _filter_values(status):
            stmt = stmt.where(QbPracticeSession.status.in_(statuses))
        if modes := _filter_values(mode):
            stmt = stmt.where(QbPracticeSession.mode.in_(modes))
        if source_type is not None:
            stmt = stmt.where(QbPracticeSession.source_type == source_type)
        if bank_id is not None:
            stmt = stmt.where(QbBankRevision.bank_id == bank_id)
        if created_after is not None:
            stmt = stmt.where(QbPracticeSession.created_time >= created_after)
        if category_ids:
            bank_in_domain = (
                select(QbBankCategory.id)
                .select_from(QbBankCategory)
                .where(
                    QbBankCategory.bank_id == QbBankRevision.bank_id,
                    QbBankCategory.deleted == 0,
                    QbBankCategory.category_id.in_(category_ids),
                )
                .exists()
            )
            stmt = stmt.where(or_(QbPracticeSession.bank_revision_id.is_(None), bank_in_domain))
        return stmt

    async def get_report_items(self, db: AsyncSession, session_id: int) -> list[dict[str, Any]]:
        """获取整场报告所需的去答案答题卡事实"""
        stmt = (
            select(
                QbPracticeSessionItem.id.label('session_item_id'),
                QbPracticeSessionItem.position,
                QbPracticeSessionItem.question_id,
                QbPracticeSessionItem.bank_item_id,
                QbBankItem.section_id,
                _session_section_name(session_id),
                QbPracticeSessionItem.max_score,
                QbPracticeSessionResponse.status.label('response_status'),
                QbPracticeSessionResponse.is_correct,
                QbPracticeSessionResponse.score,
                func.coalesce(QbPracticeSessionResponse.duration_ms, 0).label('duration_ms'),
                QbPracticeSessionResponse.grading_status,
            )
            .select_from(QbPracticeSessionItem)
            .outerjoin(
                QbPracticeSessionResponse,
                and_(
                    QbPracticeSessionResponse.session_item_id == QbPracticeSessionItem.id,
                    QbPracticeSessionResponse.deleted == 0,
                ),
            )
            .outerjoin(
                QbBankItem,
                and_(QbBankItem.id == QbPracticeSessionItem.bank_item_id, QbBankItem.deleted == 0),
            )
            .outerjoin(
                QbBankSection,
                and_(QbBankSection.id == QbBankItem.section_id, QbBankSection.deleted == 0),
            )
            .where(
                QbPracticeSessionItem.session_id == session_id,
                QbPracticeSessionItem.deleted == 0,
            )
            .order_by(QbPracticeSessionItem.position, QbPracticeSessionItem.id)
        )
        return [dict(row) for row in (await db.execute(stmt)).mappings().all()]

    async def get_solutions(self, db: AsyncSession, session_id: int) -> list[dict[str, Any]]:
        """一次查询获取整卷答案、用户最终答案和已发布解析"""
        stmt = (
            select(
                QbPracticeSessionItem.id.label('session_item_id'),
                QbPracticeSessionItem.position,
                QbPracticeSessionItem.question_id,
                QbPracticeSessionItem.max_score,
                QbPracticeSessionResponse.response_data,
                QbPracticeSessionResponse.is_correct,
                QbPracticeSessionResponse.score,
                QbPracticeSessionResponse.grading_status,
                QbQuestionAnswer.answer_data,
                QbQuestionAnswer.grading_method,
                QbQuestionAnswer.grading_config,
                QbQuestionExplanation.content.label('explanation_content'),
                QbQuestionExplanation.explanation_type,
                QbQuestionExplanation.is_default.label('explanation_is_default'),
            )
            .select_from(QbPracticeSessionItem)
            .join(
                QbQuestionAnswer,
                and_(
                    QbQuestionAnswer.question_id == QbPracticeSessionItem.question_id,
                    QbQuestionAnswer.deleted == 0,
                ),
            )
            .outerjoin(
                QbPracticeSessionResponse,
                and_(
                    QbPracticeSessionResponse.session_item_id == QbPracticeSessionItem.id,
                    QbPracticeSessionResponse.deleted == 0,
                ),
            )
            .outerjoin(
                QbQuestionExplanation,
                and_(
                    QbQuestionExplanation.question_id == QbPracticeSessionItem.question_id,
                    QbQuestionExplanation.status == 'published',
                    QbQuestionExplanation.deleted == 0,
                ),
            )
            .where(
                QbPracticeSessionItem.session_id == session_id,
                QbPracticeSessionItem.deleted == 0,
            )
            .order_by(
                QbPracticeSessionItem.position,
                QbPracticeSessionItem.id,
                QbQuestionExplanation.is_default.desc(),
                QbQuestionExplanation.id,
            )
        )
        rows = (await db.execute(stmt)).mappings().all()
        solutions: dict[int, dict[str, Any]] = {}
        for raw in rows:
            row = dict(raw)
            item = solutions.setdefault(
                row['session_item_id'],
                {
                    key: row[key]
                    for key in (
                        'session_item_id',
                        'position',
                        'question_id',
                        'max_score',
                        'response_data',
                        'is_correct',
                        'score',
                        'grading_status',
                        'answer_data',
                        'grading_method',
                        'grading_config',
                    )
                }
                | {'explanations': []},
            )
            if row['explanation_content'] is not None:
                item['explanations'].append({
                    'content': row['explanation_content'],
                    'explanation_type': row['explanation_type'],
                    'is_default': row['explanation_is_default'],
                })
        return list(solutions.values())

    async def create(self, db: AsyncSession, data: dict[str, Any]) -> QbPracticeSession:
        """创建练习会话"""
        session = QbPracticeSession(**data)
        db.add(session)
        await db.flush()
        return session

    async def refresh_aggregates(self, db: AsyncSession, session: QbPracticeSession) -> None:
        """从当前作答投影重算会话缓存，并在全部判分完成后结束待判状态"""
        row = (
            (
                await db.execute(
                    select(
                        func.count(
                            case((
                                QbPracticeSessionResponse.status.in_({'submitted', 'graded', 'review_required'}),
                                QbPracticeSessionResponse.id,
                            ))
                        ).label('answered_items'),
                        func.count(case((QbPracticeSessionResponse.is_correct.is_(True), 1))).label('correct_items'),
                        func.coalesce(func.sum(QbPracticeSessionResponse.score), 0).label('score'),
                        func.count(
                            case((
                                QbPracticeSessionResponse.grading_status.in_({'pending', 'review_required', 'failed'}),
                                QbPracticeSessionResponse.id,
                            ))
                        ).label('pending_items'),
                    ).where(
                        QbPracticeSessionResponse.session_id == session.id,
                        QbPracticeSessionResponse.deleted == 0,
                    )
                )
            )
            .mappings()
            .one()
        )
        session.answered_items = int(row['answered_items'])
        session.correct_items = int(row['correct_items'])
        session.score = Decimal(row['score'])
        if session.status == 'submitted' and int(row['pending_items']) == 0 and session.answered_items > 0:
            session.status = 'graded'
        await db.flush()


class CRUDPracticeSessionItem(CRUDPlus[QbPracticeSessionItem]):
    """练习会话题目数据库操作类"""

    async def get(self, db: AsyncSession, pk: int) -> QbPracticeSessionItem | None:
        """获取一条会话投递题目"""
        stmt = select(QbPracticeSessionItem).where(
            QbPracticeSessionItem.id == pk,
            QbPracticeSessionItem.deleted == 0,
        )
        return (await db.execute(stmt)).scalars().first()

    @staticmethod
    async def _resolve_section_ids(
        db: AsyncSession,
        bank_revision_id: int,
        section_id: int,
    ) -> list[int]:
        """解析选中章节及其全部后代章节 ID（章节树向下包含）。"""
        return await bank_section_dao.resolve_ids_with_descendants(db, bank_revision_id, section_id)

    async def get_candidates(
        self,
        db: AsyncSession,
        *,
        bank_revision_id: int,
        section_id: int | None,
        knowledge_point_ids: Sequence[int],
        question_types: Sequence[str],
        year_start: int | None,
        year_end: int | None,
        shuffle: bool,
        limit: int,
        region: str | None = None,
        user_id: int | None = None,
        prioritize_unseen: bool = False,
    ) -> Sequence[QbBankItem]:
        """获取待投递的题库编排项"""
        filters = (
            QbBankItem.bank_revision_id == bank_revision_id,
            QbBankItem.deleted == 0,
            QbBankItem.is_active.is_(True),
        )
        if section_id is not None:
            section_ids = await self._resolve_section_ids(db, bank_revision_id, section_id)
            filters = (*filters, QbBankItem.section_id.in_(section_ids))
        if year_start is not None:
            filters = (*filters, QbBankItem.exam_year >= year_start)
        if year_end is not None:
            filters = (*filters, QbBankItem.exam_year <= year_end)

        base_stmt = select(QbBankItem)
        bounds_stmt = select(func.min(QbBankItem.id), func.max(QbBankItem.id)).select_from(QbBankItem)
        region_filter = build_region_filter(region)
        if region_filter is not None:
            revision_join = and_(
                QbBankRevision.id == QbBankItem.bank_revision_id,
                QbBankRevision.deleted == 0,
            )
            bank_join = and_(QbBank.id == QbBankRevision.bank_id, QbBank.deleted == 0)
            base_stmt = base_stmt.join(QbBankRevision, revision_join).join(QbBank, bank_join)
            bounds_stmt = bounds_stmt.join(QbBankRevision, revision_join).join(QbBank, bank_join)
            filters = (*filters, region_filter)
        if question_types:
            question_join = and_(
                QbQuestion.id == QbBankItem.question_id,
                QbQuestion.deleted == 0,
            )
            base_stmt = base_stmt.join(
                QbQuestion,
                question_join,
            )
            bounds_stmt = bounds_stmt.join(QbQuestion, question_join)
            filters = (*filters, QbQuestion.question_type.in_(question_types))
        if knowledge_point_ids:
            knowledge_join = and_(
                QbQuestionKnowledgePoint.question_id == QbBankItem.question_id,
                QbQuestionKnowledgePoint.knowledge_point_id.in_(knowledge_point_ids),
                QbQuestionKnowledgePoint.deleted == 0,
            )
            base_stmt = base_stmt.join(
                QbQuestionKnowledgePoint,
                knowledge_join,
            )
            bounds_stmt = bounds_stmt.join(QbQuestionKnowledgePoint, knowledge_join)

        base_stmt = base_stmt.where(*filters).distinct()
        if not shuffle:
            stmt = base_stmt.order_by(
                QbBankItem.section_id.nulls_first(),
                QbBankItem.sort_order,
                QbBankItem.id,
            )
            result = await db.execute(stmt.limit(limit))
            return result.scalars().all()

        return await self._sample_items_with_priority(
            db,
            base_stmt=base_stmt,
            bounds_stmt=bounds_stmt.where(*filters),
            limit=limit,
            user_id=user_id if prioritize_unseen else None,
        )

    async def _sample_items_with_priority(
        self,
        db: AsyncSession,
        *,
        base_stmt: Select,
        bounds_stmt: Select,
        limit: int,
        user_id: int | None = None,
    ) -> Sequence[QbBankItem]:
        """随机采样投递项：启用优先级时先取未做过的题，不足再按最久没练补齐"""
        priority = build_attempt_priority(QbBankItem.question_id, user_id)
        if priority is None:
            return await self._sample_items_by_pivot(
                db,
                base_stmt=base_stmt,
                bounds_stmt=bounds_stmt,
                limit=limit,
            )

        attempted, last_submitted = priority
        candidates = list(
            await self._sample_items_by_pivot(
                db,
                base_stmt=base_stmt.where(~attempted),
                bounds_stmt=bounds_stmt.where(~attempted),
                limit=limit,
            )
        )
        remaining = limit - len(candidates)
        if remaining <= 0:
            return candidates

        # 新题不够时用做过的题补齐；集合已经被作用域与作答历史收窄，量级可控
        priority_column = last_submitted.label('last_submitted_time')
        seen_stmt = (
            base_stmt
            .where(attempted)
            .add_columns(priority_column)
            .order_by(priority_column.asc(), _random_order())
            .limit(remaining)
        )
        candidates.extend((await db.execute(seen_stmt)).scalars().all())
        return candidates

    async def _sample_items_by_pivot(
        self,
        db: AsyncSession,
        *,
        base_stmt: Select,
        bounds_stmt: Select,
        limit: int,
    ) -> Sequence[QbBankItem]:
        """按主键区间随机采样，避免对大表做全量随机排序"""
        bounds_result = await db.execute(bounds_stmt)
        min_id, max_id = bounds_result.one()
        if min_id is None or max_id is None:
            return []

        randomizer = secrets.SystemRandom()
        pivot = randomizer.randint(min_id, max_id)
        candidates = list(
            (await db.execute(base_stmt.where(QbBankItem.id >= pivot).order_by(QbBankItem.id).limit(limit)))
            .scalars()
            .all()
        )
        remaining = limit - len(candidates)
        if remaining > 0:
            candidates.extend(
                (await db.execute(base_stmt.where(QbBankItem.id < pivot).order_by(QbBankItem.id).limit(remaining)))
                .scalars()
                .all()
            )
        randomizer.shuffle(candidates)
        return candidates

    async def _sample_rows_with_priority(
        self,
        db: AsyncSession,
        *,
        stmt: Select,
        question_id_col: Any,
        user_id: int | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        """
        随机抽取候选行，启用优先级时先取未做过的题，不足再按最久没练补齐

        :param stmt: 已应用作用域筛选、尚未排序的候选查询
        :param question_id_col: 与作答表 question_id 对齐的题目 ID 列
        :param user_id: 当前用户；为空时退化为纯随机
        :param limit: 需要抽取的数量
        :return: 候选行映射
        """
        priority = build_attempt_priority(question_id_col, user_id)
        if priority is None:
            return list((await db.execute(stmt.order_by(_random_order()).limit(limit))).mappings().all())

        attempted, last_submitted = priority
        rows = list((await db.execute(stmt.where(~attempted).order_by(_random_order()).limit(limit))).mappings().all())
        remaining = limit - len(rows)
        if remaining <= 0:
            return rows
        rows.extend(
            (await db.execute(stmt.where(attempted).order_by(last_submitted.asc(), _random_order()).limit(remaining)))
            .mappings()
            .all()
        )
        return rows

    async def get_user_candidates(  # noqa: C901
        self,
        db: AsyncSession,
        *,
        user_id: int,
        source_type: str,
        bank_id: int | None,
        section_ids: Sequence[int],
        favorite_folder_id: int | None,
        question_ids: Sequence[int],
        knowledge_point_ids: Sequence[int],
        question_types: Sequence[str],
        year_start: int | None,
        year_end: int | None,
        shuffle: bool,
        limit: int,
        region: str | None = None,
        prioritize_unseen: bool = False,
    ) -> list[PracticeCandidate]:
        """获取错题、收藏、笔记或指定题目来源的固定版本候选题"""
        if source_type == 'custom':
            stmt = (
                select(
                    QbQuestion.id.label('question_id'),
                    QbQuestion.default_score.label('max_score'),
                    QbWrongQuestionState.last_wrong_response,
                )
                .outerjoin(
                    QbWrongQuestionState,
                    and_(
                        QbWrongQuestionState.user_id == user_id,
                        QbWrongQuestionState.question_id == QbQuestion.id,
                        QbWrongQuestionState.deleted == 0,
                    ),
                )
                .where(
                    QbQuestion.status == 'active',
                    QbQuestion.deleted == 0,
                    or_(QbQuestion.visibility != 'private', QbQuestion.owner_id == user_id),
                )
            )
            if question_ids:
                stmt = stmt.where(QbQuestion.id.in_(question_ids))
            else:
                # 无显式题目 ID 的自由组题必须限定知识点，不能退化为全量题目。
                if not knowledge_point_ids:
                    return []
                placement_scope = (
                    select(QbBankItem.id)
                    .join(QbBankRevision, QbBankRevision.id == QbBankItem.bank_revision_id)
                    .join(QbBank, QbBank.id == QbBankRevision.bank_id)
                    .where(
                        QbBankItem.question_id == QbQuestion.id,
                        QbBankItem.deleted == 0,
                        QbBankItem.is_active.is_(True),
                        QbBankRevision.deleted == 0,
                        QbBankRevision.status == 'published',
                        QbBank.current_revision_id == QbBankRevision.id,
                        QbBank.deleted == 0,
                        QbBank.status == 'active',
                    )
                )
                if bank_id is not None:
                    placement_scope = placement_scope.where(QbBank.id == bank_id)
                if year_start is not None:
                    placement_scope = placement_scope.where(QbBankItem.exam_year >= year_start)
                if year_end is not None:
                    placement_scope = placement_scope.where(QbBankItem.exam_year <= year_end)
                region_filter = build_region_filter(region)
                if region_filter is not None:
                    placement_scope = placement_scope.where(region_filter)
                if bank_id is not None or year_start is not None or year_end is not None or region:
                    stmt = stmt.where(placement_scope.exists())
            if question_types:
                stmt = stmt.where(QbQuestion.question_type.in_(question_types))
            if knowledge_point_ids:
                stmt = stmt.where(
                    select(QbQuestionKnowledgePoint.question_id)
                    .where(
                        QbQuestionKnowledgePoint.question_id == QbQuestion.id,
                        QbQuestionKnowledgePoint.knowledge_point_id.in_(knowledge_point_ids),
                        QbQuestionKnowledgePoint.deleted == 0,
                    )
                    .exists()
                )
            if question_ids:
                requested_order = {question_id: position for position, question_id in enumerate(question_ids)}
                stmt = stmt.order_by(case(requested_order, value=QbQuestion.id, else_=len(requested_order)))
                rows = list((await db.execute(stmt.limit(limit))).mappings().all())
                if shuffle:
                    secrets.SystemRandom().shuffle(rows)
            elif shuffle:
                # 启用未做优先时，两阶段的顺序本身已经是随机的，不再二次打乱
                rows = await self._sample_rows_with_priority(
                    db,
                    stmt=stmt,
                    question_id_col=QbQuestion.id,
                    user_id=user_id if prioritize_unseen else None,
                    limit=limit,
                )
            else:
                stmt = stmt.order_by(QbQuestion.id)
                rows = list((await db.execute(stmt.limit(limit))).mappings().all())
            candidate_question_ids = [int(row['question_id']) for row in rows]
            review_ranked = (
                select(
                    QbQuestionReview.id.label('review_id'),
                    QbQuestionReview.question_id,
                    QbQuestionReview.summary,
                    QbQuestionReview.review_data,
                    func
                    .row_number()
                    .over(
                        partition_by=QbQuestionReview.question_id,
                        order_by=(QbQuestionReview.reviewed_time.desc(), QbQuestionReview.id.desc()),
                    )
                    .label('review_rank'),
                )
                .where(
                    QbQuestionReview.user_id == user_id,
                    QbQuestionReview.question_id.in_(candidate_question_ids),
                    QbQuestionReview.event_type == 'review',
                    QbQuestionReview.deleted == 0,
                )
                .subquery()
            )
            latest_reviews = (
                select(
                    review_ranked.c.review_id,
                    review_ranked.c.question_id,
                    review_ranked.c.summary,
                    review_ranked.c.review_data,
                )
                .where(review_ranked.c.review_rank == 1)
                .subquery()
            )
            latest_review_rows = (await db.execute(select(latest_reviews))).mappings().all()
            latest_review_map = {int(row['question_id']): row for row in latest_review_rows}

            history_rows = (
                (
                    await db.execute(
                        select(
                            QbQuestionReview.id,
                            QbQuestionReview.question_id,
                            QbQuestionReview.summary,
                            QbQuestionReview.review_data,
                            QbQuestionReview.reviewed_time,
                        )
                        .where(
                            QbQuestionReview.user_id == user_id,
                            QbQuestionReview.question_id.in_(candidate_question_ids),
                            QbQuestionReview.event_type == 'review',
                            QbQuestionReview.deleted == 0,
                        )
                        .order_by(
                            QbQuestionReview.question_id,
                            QbQuestionReview.reviewed_time.desc(),
                            QbQuestionReview.id.desc(),
                        )
                    )
                )
                .mappings()
                .all()
            )
            history_review_ids = [int(row['id']) for row in history_rows]
            history_tag_rows = (
                (
                    await db.execute(
                        select(QbQuestionReviewTag.review_id, QbReviewTag.name)
                        .join(QbReviewTag, QbReviewTag.id == QbQuestionReviewTag.tag_id)
                        .where(
                            QbQuestionReviewTag.review_id.in_(history_review_ids),
                            QbQuestionReviewTag.deleted == 0,
                            QbReviewTag.deleted == 0,
                        )
                    )
                ).all()
                if history_review_ids
                else []
            )
            history_tag_names: dict[int, list[str]] = {}
            for review_id, name in history_tag_rows:
                history_tag_names.setdefault(int(review_id), []).append(name)

            history_knowledge_rows = (
                (
                    await db.execute(
                        select(QbQuestionReviewKnowledgePoint.review_id, QbKnowledgePoint.name)
                        .join(
                            QbKnowledgePoint,
                            QbKnowledgePoint.id == QbQuestionReviewKnowledgePoint.knowledge_point_id,
                        )
                        .where(
                            QbQuestionReviewKnowledgePoint.review_id.in_(history_review_ids),
                            QbQuestionReviewKnowledgePoint.deleted == 0,
                            QbKnowledgePoint.deleted == 0,
                        )
                    )
                ).all()
                if history_review_ids
                else []
            )
            history_knowledge_names: dict[int, list[str]] = {}
            for review_id, name in history_knowledge_rows:
                history_knowledge_names.setdefault(int(review_id), []).append(name)
            review_history: dict[int, list[dict[str, Any]]] = {}
            for row in history_rows:
                review_id = int(row['id'])
                review_data = dict(row['review_data'] or {})
                review_history.setdefault(int(row['question_id']), []).append({
                    'summary': row['summary'],
                    'prevention': review_data.get('prevention', ''),
                    'tag_names': history_tag_names.get(review_id, []),
                    'knowledge_point_names': history_knowledge_names.get(review_id, []),
                    'reviewed_time': row['reviewed_time'].isoformat(),
                })

            wrong_attempt_rows = (
                (
                    await db.execute(
                        select(
                            QbQuestionAttempt.question_id,
                            QbQuestionAttempt.attempt_no,
                            QbQuestionAttempt.response_data,
                            QbQuestionAttempt.submitted_time,
                        )
                        .where(
                            QbQuestionAttempt.user_id == user_id,
                            QbQuestionAttempt.question_id.in_(candidate_question_ids),
                            QbQuestionAttempt.is_correct.is_(False),
                            QbQuestionAttempt.deleted == 0,
                        )
                        .order_by(
                            QbQuestionAttempt.question_id,
                            QbQuestionAttempt.submitted_time.desc(),
                            QbQuestionAttempt.id.desc(),
                        )
                    )
                )
                .mappings()
                .all()
            )
            wrong_answer_history: dict[int, list[dict[str, Any]]] = {}
            for row in wrong_attempt_rows:
                response_data = row['response_data']
                if (
                    isinstance(response_data, dict)
                    and response_data.get('mode') == 'memorize'
                    and response_data.get('viewed') is True
                ):
                    continue
                wrong_answer_history.setdefault(int(row['question_id']), []).append({
                    'answer': response_data,
                    'attempt_no': row['attempt_no'],
                    'submitted_time': row['submitted_time'].isoformat(),
                })

            tag_rows = (
                await db.execute(
                    select(latest_reviews.c.question_id, QbReviewTag.name)
                    .select_from(latest_reviews)
                    .join(
                        QbQuestionReviewTag,
                        and_(
                            QbQuestionReviewTag.review_id == latest_reviews.c.review_id,
                            QbQuestionReviewTag.deleted == 0,
                        ),
                    )
                    .join(
                        QbReviewTag,
                        and_(QbReviewTag.id == QbQuestionReviewTag.tag_id, QbReviewTag.deleted == 0),
                    )
                )
            ).all()
            tag_names: dict[int, list[str]] = {}
            for question_id, name in tag_rows:
                tag_names.setdefault(int(question_id), []).append(name)

            knowledge_rows = (
                await db.execute(
                    select(latest_reviews.c.question_id, QbKnowledgePoint.name)
                    .select_from(latest_reviews)
                    .join(
                        QbQuestionReviewKnowledgePoint,
                        and_(
                            QbQuestionReviewKnowledgePoint.review_id == latest_reviews.c.review_id,
                            QbQuestionReviewKnowledgePoint.deleted == 0,
                        ),
                    )
                    .join(
                        QbKnowledgePoint,
                        and_(
                            QbKnowledgePoint.id == QbQuestionReviewKnowledgePoint.knowledge_point_id,
                            QbKnowledgePoint.deleted == 0,
                        ),
                    )
                )
            ).all()
            knowledge_names: dict[int, list[str]] = {}
            for question_id, name in knowledge_rows:
                knowledge_names.setdefault(int(question_id), []).append(name)

            candidates: list[PracticeCandidate] = []
            for row in rows:
                question_id = int(row['question_id'])
                latest_review = latest_review_map.get(question_id)
                review_data = dict((latest_review or {}).get('review_data') or {})
                display_config: dict[str, Any] = {}
                if row['last_wrong_response'] is not None:
                    display_config['last_wrong_response'] = row['last_wrong_response']
                if wrong_answer_history.get(question_id):
                    display_config['wrong_answer_history'] = wrong_answer_history[question_id]
                if latest_review is not None:
                    display_config.update({
                        'review_summary': latest_review['summary'],
                        'review_prevention': review_data.get('prevention', ''),
                        'review_tag_names': tag_names.get(question_id, []),
                        'review_knowledge_point_names': knowledge_names.get(question_id, []),
                        'review_history': review_history.get(question_id, []),
                    })
                candidates.append(
                    PracticeCandidate(
                        question_id=question_id,
                        bank_item_id=None,
                        max_score=row['max_score'],
                        display_config=display_config,
                    )
                )
            return candidates

        source_model: type[QbWrongQuestionState | QbQuestionFavorite | QbQuestionNote]
        if source_type == 'wrong':
            source_model = QbWrongQuestionState
            bank_item_id = QbWrongQuestionState.source_bank_item_id
        elif source_type == 'favorite':
            source_model = QbQuestionFavorite
            bank_item_id = QbQuestionFavorite.bank_item_id
        else:
            source_model = QbQuestionNote
            bank_item_id = QbQuestionNote.bank_item_id

        stmt = (
            select(
                source_model.id.label('source_id'),
                source_model.question_id.label('question_id'),
                bank_item_id.label('bank_item_id'),
                func.coalesce(QbBankItem.score, QbQuestion.default_score).label('max_score'),
                QbBankItem.settings.label('display_config'),
            )
            .join(
                QbQuestion,
                and_(
                    QbQuestion.id == source_model.question_id,
                    QbQuestion.deleted == 0,
                ),
            )
            .outerjoin(
                QbBankItem,
                and_(
                    QbBankItem.id == bank_item_id,
                    QbBankItem.question_id == source_model.question_id,
                    QbBankItem.deleted == 0,
                ),
            )
            .where(source_model.user_id == user_id, source_model.deleted == 0)
        )
        if source_type == 'wrong':
            stmt = stmt.where(QbWrongQuestionState.status == 'active')
        elif source_type == 'favorite' and favorite_folder_id is not None:
            stmt = stmt.where(QbQuestionFavorite.folder_id == favorite_folder_id)
        if question_types:
            stmt = stmt.where(QbQuestion.question_type.in_(question_types))
        if knowledge_point_ids:
            stmt = stmt.join(
                QbQuestionKnowledgePoint,
                and_(
                    QbQuestionKnowledgePoint.question_id == QbQuestion.id,
                    QbQuestionKnowledgePoint.knowledge_point_id.in_(knowledge_point_ids),
                    QbQuestionKnowledgePoint.deleted == 0,
                ),
            ).distinct()
        if section_ids:
            stmt = stmt.where(QbBankItem.section_id.in_(section_ids))
        if year_start is not None:
            stmt = stmt.where(QbBankItem.exam_year >= year_start)
        if year_end is not None:
            stmt = stmt.where(QbBankItem.exam_year <= year_end)
        region_filter = build_region_filter(region)
        if bank_id is not None or region_filter is not None:
            stmt = stmt.join(
                QbBankRevision,
                and_(QbBankRevision.id == QbBankItem.bank_revision_id, QbBankRevision.deleted == 0),
            )
            if bank_id is not None:
                stmt = stmt.where(QbBankRevision.bank_id == bank_id)
            if region_filter is not None:
                stmt = stmt.join(
                    QbBank,
                    and_(QbBank.id == QbBankRevision.bank_id, QbBank.deleted == 0),
                ).where(region_filter)

        source_rows = stmt.subquery()
        if not shuffle:
            result = await db.execute(select(source_rows).order_by(source_rows.c.source_id.desc()).limit(limit))
            rows = result.mappings().all()
        else:
            min_id, max_id = (
                await db.execute(select(func.min(source_rows.c.source_id), func.max(source_rows.c.source_id)))
            ).one()
            if min_id is None or max_id is None:
                return []
            randomizer = secrets.SystemRandom()
            pivot = randomizer.randint(min_id, max_id)
            rows = list(
                (
                    await db.execute(
                        select(source_rows)
                        .where(source_rows.c.source_id >= pivot)
                        .order_by(source_rows.c.source_id)
                        .limit(limit)
                    )
                )
                .mappings()
                .all()
            )
            remaining = limit - len(rows)
            if remaining > 0:
                rows.extend(
                    (
                        await db.execute(
                            select(source_rows)
                            .where(source_rows.c.source_id < pivot)
                            .order_by(source_rows.c.source_id)
                            .limit(remaining)
                        )
                    )
                    .mappings()
                    .all()
                )
            randomizer.shuffle(rows)
        return [
            PracticeCandidate(
                question_id=int(row['question_id']),
                bank_item_id=row['bank_item_id'],
                max_score=row['max_score'],
                display_config=dict(row['display_config'] or {}),
            )
            for row in rows
        ]

    async def create_all(
        self,
        db: AsyncSession,
        *,
        session_id: int,
        candidates: Sequence[QbBankItem | PracticeCandidate],
    ) -> None:
        """批量创建会话题目快照"""
        session_items: list[QbPracticeSessionItem] = []
        for position, item in enumerate(candidates):
            is_bank_item = isinstance(item, QbBankItem)
            session_items.append(
                QbPracticeSessionItem(
                    session_id=session_id,
                    question_id=item.question_id,
                    position=position,
                    bank_item_id=item.id if is_bank_item else item.bank_item_id,
                    max_score=item.score if is_bank_item else item.max_score,
                    display_config=dict(item.settings if is_bank_item else item.display_config),
                )
            )
        db.add_all(session_items)
        await db.flush()

    async def get_all(self, db: AsyncSession, session_id: int) -> list[dict[str, Any]]:
        """获取会话投递题目，不返回标准答案与解析"""
        stmt = (
            select(
                QbPracticeSessionItem.id,
                QbPracticeSessionItem.position,
                QbPracticeSessionItem.question_id,
                QbPracticeSessionItem.bank_item_id,
                QbBankItem.exam_year,
                QbBankItem.section_id,
                _session_section_name(session_id),
                QbPracticeSessionItem.max_score,
                QbPracticeSessionItem.display_config,
                QbQuestion.question_type,
                QbQuestion.stem,
                QbQuestion.content_format,
                QbQuestion.option_data,
                QbQuestion.difficulty,
                QbPracticeSessionResponse.response_data,
                QbPracticeSessionResponse.status.label('response_status'),
                QbPracticeSessionResponse.is_correct,
                QbPracticeSessionResponse.score,
                QbPracticeSessionResponse.is_flagged,
                QbPracticeSessionResponse.duration_ms,
                QbPracticeSessionResponse.save_version,
            )
            .select_from(QbPracticeSessionItem)
            .join(
                QbQuestion,
                and_(
                    QbQuestion.id == QbPracticeSessionItem.question_id,
                    QbQuestion.deleted == 0,
                ),
            )
            .outerjoin(
                QbBankItem,
                and_(
                    QbBankItem.id == QbPracticeSessionItem.bank_item_id,
                    QbBankItem.deleted == 0,
                ),
            )
            .outerjoin(
                QbBankSection,
                and_(QbBankSection.id == QbBankItem.section_id, QbBankSection.deleted == 0),
            )
            .outerjoin(
                QbPracticeSessionResponse,
                and_(
                    QbPracticeSessionResponse.session_item_id == QbPracticeSessionItem.id,
                    QbPracticeSessionResponse.deleted == 0,
                ),
            )
            .where(
                QbPracticeSessionItem.session_id == session_id,
                QbPracticeSessionItem.deleted == 0,
            )
            .order_by(QbPracticeSessionItem.position, QbPracticeSessionItem.id)
        )
        result = await db.execute(stmt)
        return [dict(row) for row in result.mappings().all()]


practice_session_dao: CRUDPracticeSession = CRUDPracticeSession(QbPracticeSession)
practice_session_item_dao: CRUDPracticeSessionItem = CRUDPracticeSessionItem(QbPracticeSessionItem)


class CRUDPracticeSessionResponse(CRUDPlus[QbPracticeSessionResponse]):
    """练习题目当前作答状态数据库操作类"""

    async def get(
        self,
        db: AsyncSession,
        *,
        session_id: int,
        session_item_id: int,
        for_update: bool = False,
    ) -> QbPracticeSessionResponse | None:
        """获取会话题目当前作答状态"""
        stmt = select(QbPracticeSessionResponse).where(
            QbPracticeSessionResponse.session_id == session_id,
            QbPracticeSessionResponse.session_item_id == session_item_id,
            QbPracticeSessionResponse.deleted == 0,
        )
        if for_update:
            stmt = stmt.with_for_update()
        result = await db.execute(stmt)
        return result.scalars().first()

    async def create(self, db: AsyncSession, data: dict[str, Any]) -> QbPracticeSessionResponse:
        """创建题目当前作答状态"""
        response = QbPracticeSessionResponse(**data)
        db.add(response)
        await db.flush()
        return response

    async def has_pending_grading(self, db: AsyncSession, session_id: int) -> bool:
        """判断会话是否仍有未完成判分的已提交答案"""
        result = await db.execute(
            select(func.count(QbPracticeSessionResponse.id)).where(
                QbPracticeSessionResponse.session_id == session_id,
                QbPracticeSessionResponse.deleted == 0,
                QbPracticeSessionResponse.status.in_({'submitted', 'review_required'}),
                QbPracticeSessionResponse.grading_status.in_({'pending', 'review_required', 'failed'}),
            )
        )
        return int(result.scalar_one()) > 0

    async def get_total_duration_ms(self, db: AsyncSession, session_id: int) -> int:
        """会话累计有效作答时长（毫秒），与整场报告同口径：逐题 duration_ms 求和"""
        result = await db.execute(
            select(func.coalesce(func.sum(QbPracticeSessionResponse.duration_ms), 0)).where(
                QbPracticeSessionResponse.session_id == session_id,
                QbPracticeSessionResponse.deleted == 0,
            )
        )
        return int(result.scalar_one() or 0)

    async def get_today_practice_summary(self, db: AsyncSession, *, user_id: int, since: datetime) -> dict[str, int]:
        """今日练习摘要：该时刻之后提交的题数与有效作答时长（秒），供签到门槛判断"""
        stmt = (
            select(
                func.count(QbPracticeSessionResponse.id).label('practice_count'),
                func.coalesce(func.sum(QbPracticeSessionResponse.duration_ms), 0).label('duration_ms'),
            )
            .join(QbPracticeSession, QbPracticeSession.id == QbPracticeSessionResponse.session_id)
            .where(
                QbPracticeSession.user_id == user_id,
                QbPracticeSession.deleted == 0,
                online_session_condition(),
                QbPracticeSessionResponse.deleted == 0,
                QbPracticeSessionResponse.status.in_({'submitted', 'graded', 'review_required'}),
                QbPracticeSessionResponse.last_submitted_time >= since,
            )
        )
        row = (await db.execute(stmt)).one()
        return {
            'practice_count': int(row.practice_count or 0),
            'duration_seconds': int((row.duration_ms or 0) // 1000),
        }


class CRUDQuestionAttempt(CRUDPlus[QbQuestionAttempt]):
    """不可变题目提交事实数据库操作类"""

    async def get_latest_wrong_response(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        question_id: int,
    ) -> dict[str, Any] | None:
        """仅取最近一次有效错误答案，不加载整道题的作答历史。"""
        # SQLite 把 JSON 布尔值提取为 1，使用 json_type 区分 true 与数字 1；
        # 其他数据库比较 JSON 文本，避免布尔强转把字符串 "true" 也当作浏览标记。
        viewed_true = (
            func.json_type(QbQuestionAttempt.response_data, '$.viewed') == 'true'
            if db.get_bind().dialect.name == 'sqlite'
            else cast(QbQuestionAttempt.response_data['viewed'], String) == 'true'
        )
        memorize_view = and_(
            func.coalesce(QbQuestionAttempt.response_data['mode'].as_string() == 'memorize', False),
            func.coalesce(viewed_true, False),
        )
        stmt = (
            select(QbQuestionAttempt.response_data)
            .where(
                QbQuestionAttempt.user_id == user_id,
                QbQuestionAttempt.question_id == question_id,
                QbQuestionAttempt.is_correct.is_(False),
                QbQuestionAttempt.deleted == 0,
                ~memorize_view,
            )
            .order_by(QbQuestionAttempt.submitted_time.desc(), QbQuestionAttempt.id.desc())
            .limit(1)
        )
        row = (await db.execute(stmt)).mappings().first()
        return dict(row) if row is not None else None

    async def get(
        self,
        db: AsyncSession,
        pk: int,
        *,
        user_id: int,
        question_id: int | None = None,
    ) -> QbQuestionAttempt | None:
        """获取当前用户的一次不可变题目提交事实"""
        stmt = select(QbQuestionAttempt).where(
            QbQuestionAttempt.id == pk,
            QbQuestionAttempt.user_id == user_id,
            QbQuestionAttempt.deleted == 0,
        )
        if question_id is not None:
            stmt = stmt.where(QbQuestionAttempt.question_id == question_id)
        return (await db.execute(stmt)).scalars().first()

    async def get_next_attempt_no(self, db: AsyncSession, session_item_id: int) -> int:
        """获取会话题目的下一提交序号"""
        result = await db.execute(
            select(func.coalesce(func.max(QbQuestionAttempt.attempt_no), 0) + 1).where(
                QbQuestionAttempt.session_item_id == session_item_id,
                QbQuestionAttempt.deleted == 0,
            )
        )
        return int(result.scalar_one())

    async def create(self, db: AsyncSession, data: dict[str, Any]) -> QbQuestionAttempt:
        """追加一次题目提交事实"""
        attempt = QbQuestionAttempt(**data)
        db.add(attempt)
        await db.flush()
        return attempt

    async def is_latest_for_item(self, db: AsyncSession, attempt: QbQuestionAttempt) -> bool:
        """判断作答事实是否仍是会话题目的最近一次提交"""
        if attempt.session_item_id is None:
            return False
        latest_no = await db.scalar(
            select(func.max(QbQuestionAttempt.attempt_no)).where(
                QbQuestionAttempt.session_item_id == attempt.session_item_id,
                QbQuestionAttempt.deleted == 0,
            )
        )
        return int(latest_no or 0) == attempt.attempt_no

    async def get_latest_by_session(
        self,
        db: AsyncSession,
        session_id: int,
    ) -> list[tuple[QbQuestionAttempt, QbPracticeSessionItem]]:
        """Return the latest attempt and delivery context for each answered item."""
        latest = (
            select(
                QbQuestionAttempt.session_item_id,
                func.max(QbQuestionAttempt.attempt_no).label('attempt_no'),
            )
            .where(
                QbQuestionAttempt.session_id == session_id,
                QbQuestionAttempt.session_item_id.is_not(None),
                QbQuestionAttempt.deleted == 0,
            )
            .group_by(QbQuestionAttempt.session_item_id)
            .subquery()
        )
        stmt = (
            select(QbQuestionAttempt, QbPracticeSessionItem)
            .join(
                latest,
                and_(
                    latest.c.session_item_id == QbQuestionAttempt.session_item_id,
                    latest.c.attempt_no == QbQuestionAttempt.attempt_no,
                ),
            )
            .join(QbPracticeSessionItem, QbPracticeSessionItem.id == QbQuestionAttempt.session_item_id)
            .where(
                QbQuestionAttempt.session_id == session_id,
                QbQuestionAttempt.deleted == 0,
                QbPracticeSessionItem.deleted == 0,
            )
            .order_by(QbPracticeSessionItem.position)
        )
        return [(row[0], row[1]) for row in (await db.execute(stmt)).all()]


practice_response_dao: CRUDPracticeSessionResponse = CRUDPracticeSessionResponse(QbPracticeSessionResponse)
question_attempt_dao: CRUDQuestionAttempt = CRUDQuestionAttempt(QbQuestionAttempt)
