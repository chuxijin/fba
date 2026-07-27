import secrets

from collections.abc import Sequence
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.question_bank_v2.model.bank import QbBankItem, QbBankRevision
from backend.app.question_bank_v2.model.practice import (
    QbPracticeSession,
    QbPracticeSessionItem,
    QbPracticeSessionResponse,
    QbQuestionAttempt,
)
from backend.app.question_bank_v2.model.question import QbQuestionRevision


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
            .join(
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

    async def create(self, db: AsyncSession, data: dict[str, Any]) -> QbPracticeSession:
        """创建练习会话"""
        session = QbPracticeSession(**data)
        db.add(session)
        await db.flush()
        return session


class CRUDPracticeSessionItem(CRUDPlus[QbPracticeSessionItem]):
    """练习会话题目数据库操作类"""

    async def get_candidates(
        self,
        db: AsyncSession,
        *,
        bank_revision_id: int,
        section_id: int | None,
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

        base_stmt = select(QbBankItem).where(*filters)
        if not shuffle:
            stmt = base_stmt.order_by(
                QbBankItem.section_id.nulls_first(),
                QbBankItem.sort_order,
                QbBankItem.id,
            )
            result = await db.execute(stmt.limit(limit))
            return result.scalars().all()

        bounds_result = await db.execute(select(func.min(QbBankItem.id), func.max(QbBankItem.id)).where(*filters))
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

    async def create_all(
        self,
        db: AsyncSession,
        *,
        session_id: int,
        candidates: Sequence[QbBankItem],
    ) -> None:
        """批量创建会话题目快照"""
        db.add_all([
            QbPracticeSessionItem(
                session_id=session_id,
                question_id=item.question_id,
                question_revision_id=item.question_revision_id,
                position=position,
                bank_item_id=item.id,
                max_score=item.score,
                display_config=dict(item.settings),
            )
            for position, item in enumerate(candidates)
        ])
        await db.flush()

    async def get_all(self, db: AsyncSession, session_id: int) -> list[dict[str, Any]]:
        """获取会话投递题目，不返回标准答案与解析"""
        stmt = (
            select(
                QbPracticeSessionItem.id,
                QbPracticeSessionItem.position,
                QbPracticeSessionItem.question_id,
                QbPracticeSessionItem.question_revision_id,
                QbPracticeSessionItem.bank_item_id,
                QbPracticeSessionItem.max_score,
                QbPracticeSessionItem.display_config,
                QbQuestionRevision.question_type,
                QbQuestionRevision.stem,
                QbQuestionRevision.content_format,
                QbQuestionRevision.option_data,
                QbQuestionRevision.difficulty,
                QbPracticeSessionResponse.response_data,
                QbPracticeSessionResponse.status.label('response_status'),
                QbPracticeSessionResponse.is_flagged,
                QbPracticeSessionResponse.duration_ms,
                QbPracticeSessionResponse.save_version,
            )
            .join(
                QbQuestionRevision,
                and_(
                    QbQuestionRevision.id == QbPracticeSessionItem.question_revision_id,
                    QbQuestionRevision.question_id == QbPracticeSessionItem.question_id,
                    QbQuestionRevision.deleted == 0,
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


practice_response_dao: CRUDPracticeSessionResponse = CRUDPracticeSessionResponse(QbPracticeSessionResponse)
question_attempt_dao: CRUDQuestionAttempt = CRUDQuestionAttempt(QbQuestionAttempt)
