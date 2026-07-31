import secrets

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.question_bank_v2.model.bank import QbBankItem, QbBankRevision, QbBankSection
from backend.app.question_bank_v2.model.knowledge import QbQuestionKnowledgePoint
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
from backend.app.question_bank_v2.model.review import QbWrongQuestionState
from backend.app.question_bank_v2.model.user_content import QbQuestionFavorite, QbQuestionNote


@dataclass(frozen=True, slots=True)
class PracticeCandidate:
    """自由组题候选题的固定投递上下文"""

    question_id: int
    bank_item_id: int | None
    max_score: Decimal
    display_config: dict[str, Any]


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
        status: str | None,
        mode: str | None,
        source_type: str | None,
        bank_id: int | None,
    ) -> Select:
        """构建用户练习会话分页查询"""
        user_session_ids = select(QbPracticeSession.id).where(
            QbPracticeSession.user_id == user_id,
            QbPracticeSession.deleted == 0,
        )
        response_stats = (
            select(
                QbPracticeSessionResponse.session_id,
                func.count(
                    case(
                        (
                            QbPracticeSessionResponse.status.in_({'submitted', 'graded', 'review_required'}),
                            QbPracticeSessionResponse.id,
                        )
                    )
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
            .where(QbPracticeSession.user_id == user_id, QbPracticeSession.deleted == 0)
            .order_by(QbPracticeSession.created_time.desc(), QbPracticeSession.id.desc())
        )
        if status is not None:
            stmt = stmt.where(QbPracticeSession.status == status)
        if mode is not None:
            stmt = stmt.where(QbPracticeSession.mode == mode)
        if source_type is not None:
            stmt = stmt.where(QbPracticeSession.source_type == source_type)
        if bank_id is not None:
            stmt = stmt.where(QbBankRevision.bank_id == bank_id)
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
                QbBankSection.name.label('section_name'),
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
            await db.execute(
                select(
                    func.count(
                        case(
                            (
                                QbPracticeSessionResponse.status.in_({'submitted', 'graded', 'review_required'}),
                                QbPracticeSessionResponse.id,
                            )
                        )
                    ).label('answered_items'),
                    func.count(case((QbPracticeSessionResponse.is_correct.is_(True), 1))).label('correct_items'),
                    func.coalesce(func.sum(QbPracticeSessionResponse.score), 0).label('score'),
                    func.count(
                        case(
                            (
                                QbPracticeSessionResponse.grading_status.in_({'pending', 'review_required', 'failed'}),
                                QbPracticeSessionResponse.id,
                            )
                        )
                    ).label('pending_items'),
                ).where(
                    QbPracticeSessionResponse.session_id == session.id,
                    QbPracticeSessionResponse.deleted == 0,
                )
            )
        ).mappings().one()
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
    ) -> Sequence[QbBankItem]:
        """获取待投递的题库编排项"""
        filters = (
            QbBankItem.bank_revision_id == bank_revision_id,
            QbBankItem.deleted == 0,
            QbBankItem.is_active.is_(True),
        )
        if section_id is not None:
            filters = (*filters, QbBankItem.section_id == section_id)
        if year_start is not None:
            filters = (*filters, QbBankItem.exam_year >= year_start)
        if year_end is not None:
            filters = (*filters, QbBankItem.exam_year <= year_end)

        base_stmt = select(QbBankItem)
        bounds_stmt = select(func.min(QbBankItem.id), func.max(QbBankItem.id)).select_from(QbBankItem)
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

        bounds_result = await db.execute(bounds_stmt.where(*filters))
        min_id, max_id = bounds_result.one()
        if min_id is None or max_id is None:
            return []

        randomizer = secrets.SystemRandom()
        pivot = randomizer.randint(min_id, max_id)
        first_result = await db.execute(
            base_stmt.where(QbBankItem.id >= pivot).order_by(QbBankItem.id).limit(limit)
        )
        candidates = list(first_result.scalars().all())
        remaining = limit - len(candidates)
        if remaining > 0:
            second_result = await db.execute(
                base_stmt.where(QbBankItem.id < pivot).order_by(QbBankItem.id).limit(remaining)
            )
            candidates.extend(second_result.scalars().all())
        randomizer.shuffle(candidates)
        return candidates

    async def get_user_candidates(  # noqa: C901
        self,
        db: AsyncSession,
        *,
        user_id: int,
        source_type: str,
        bank_id: int | None,
        section_id: int | None,
        favorite_folder_id: int | None,
        question_ids: Sequence[int],
        knowledge_point_ids: Sequence[int],
        question_types: Sequence[str],
        year_start: int | None,
        year_end: int | None,
        shuffle: bool,
        limit: int,
    ) -> list[PracticeCandidate]:
        """获取错题、收藏、笔记或指定题目来源的固定版本候选题"""
        if source_type == 'custom':
            stmt = (
                select(
                    QbQuestion.id.label('question_id'),
                    QbQuestion.default_score.label('max_score'),
                )
                .where(
                    QbQuestion.id.in_(question_ids),
                    QbQuestion.status == 'active',
                    QbQuestion.deleted == 0,
                    or_(QbQuestion.visibility != 'private', QbQuestion.owner_id == user_id),
                )
            )
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
            requested_order = {question_id: position for position, question_id in enumerate(question_ids)}
            rows = list(
                (
                    await db.execute(
                        stmt.order_by(
                            case(requested_order, value=QbQuestion.id, else_=len(requested_order))
                        ).limit(limit)
                    )
                )
                .mappings()
                .all()
            )
            if shuffle:
                secrets.SystemRandom().shuffle(rows)
            return [
                PracticeCandidate(
                    question_id=int(row['question_id']),
                    bank_item_id=None,
                    max_score=row['max_score'],
                    display_config={},
                )
                for row in rows
            ]

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
        if section_id is not None:
            stmt = stmt.where(QbBankItem.section_id == section_id)
        if year_start is not None:
            stmt = stmt.where(QbBankItem.exam_year >= year_start)
        if year_end is not None:
            stmt = stmt.where(QbBankItem.exam_year <= year_end)
        if bank_id is not None:
            stmt = stmt.join(
                QbBankRevision,
                and_(QbBankRevision.id == QbBankItem.bank_revision_id, QbBankRevision.deleted == 0),
            ).where(QbBankRevision.bank_id == bank_id)

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


class CRUDQuestionAttempt(CRUDPlus[QbQuestionAttempt]):
    """不可变题目提交事实数据库操作类"""

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
