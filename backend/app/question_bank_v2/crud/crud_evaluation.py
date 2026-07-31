from collections.abc import Sequence
from dataclasses import dataclass
from itertools import starmap
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.question_bank_v2.model.evaluation import QbEvaluationRun
from backend.app.question_bank_v2.model.practice import (
    QbPracticeSession,
    QbPracticeSessionItem,
    QbQuestionAttempt,
)
from backend.app.question_bank_v2.model.question import QbQuestion, QbQuestionAnswer


@dataclass(frozen=True, slots=True)
class EvaluationAttemptContext:
    """一次评测所需的固定作答与题目版本上下文"""

    attempt: QbQuestionAttempt
    session: QbPracticeSession
    session_item: QbPracticeSessionItem
    question: QbQuestion
    answer: QbQuestionAnswer


class CRUDEvaluationRun(CRUDPlus[QbEvaluationRun]):
    """评测运行数据库操作类"""

    async def get_latest_attempt(
        self,
        db: AsyncSession,
        *,
        attempt_id: int,
        purpose: str = 'attempt_grading',
        for_update: bool = False,
    ) -> QbEvaluationRun | None:
        """获取一次作答的当前评测运行"""
        stmt = (
            select(QbEvaluationRun)
            .where(
                QbEvaluationRun.attempt_id == attempt_id,
                QbEvaluationRun.purpose == purpose,
                QbEvaluationRun.is_latest.is_(True),
                QbEvaluationRun.deleted == 0,
            )
            .order_by(QbEvaluationRun.id.desc())
            .limit(1)
        )
        if for_update:
            stmt = stmt.with_for_update()
        return (await db.execute(stmt)).scalars().first()

    async def get_latest_attempts(
        self,
        db: AsyncSession,
        *,
        attempt_ids: Sequence[int],
        purpose: str = 'attempt_grading',
        for_update: bool = False,
    ) -> dict[int, QbEvaluationRun]:
        """批量获取一组作答的当前评测运行"""
        if not attempt_ids:
            return {}
        stmt = select(QbEvaluationRun).where(
            QbEvaluationRun.attempt_id.in_(attempt_ids),
            QbEvaluationRun.purpose == purpose,
            QbEvaluationRun.is_latest.is_(True),
            QbEvaluationRun.deleted == 0,
        )
        if for_update:
            stmt = stmt.with_for_update()
        rows = (await db.execute(stmt)).scalars().all()
        return {run.attempt_id: run for run in rows if run.attempt_id is not None}

    async def get_latest_session(
        self,
        db: AsyncSession,
        *,
        session_id: int,
        purpose: str = 'session_summary',
        for_update: bool = False,
    ) -> QbEvaluationRun | None:
        """获取一个会话的当前评测运行"""
        stmt = (
            select(QbEvaluationRun)
            .where(
                QbEvaluationRun.session_id == session_id,
                QbEvaluationRun.purpose == purpose,
                QbEvaluationRun.is_latest.is_(True),
                QbEvaluationRun.deleted == 0,
            )
            .order_by(QbEvaluationRun.id.desc())
            .limit(1)
        )
        if for_update:
            stmt = stmt.with_for_update()
        return (await db.execute(stmt)).scalars().first()

    async def get_attempt_context(
        self,
        db: AsyncSession,
        *,
        attempt_id: int,
        user_id: int,
        for_update: bool = False,
    ) -> EvaluationAttemptContext | None:
        """获取当前用户的一次会话作答及其题目答案"""
        stmt = (
            select(
                QbQuestionAttempt,
                QbPracticeSession,
                QbPracticeSessionItem,
                QbQuestion,
                QbQuestionAnswer,
            )
            .join(
                QbPracticeSession,
                and_(
                    QbPracticeSession.id == QbQuestionAttempt.session_id,
                    QbPracticeSession.user_id == QbQuestionAttempt.user_id,
                    QbPracticeSession.deleted == 0,
                ),
            )
            .join(
                QbPracticeSessionItem,
                and_(
                    QbPracticeSessionItem.id == QbQuestionAttempt.session_item_id,
                    QbPracticeSessionItem.session_id == QbQuestionAttempt.session_id,
                    QbPracticeSessionItem.deleted == 0,
                ),
            )
            .join(
                QbQuestion,
                and_(
                    QbQuestion.id == QbQuestionAttempt.question_id,
                    QbQuestion.deleted == 0,
                ),
            )
            .join(
                QbQuestionAnswer,
                and_(
                    QbQuestionAnswer.question_id == QbQuestionAttempt.question_id,
                    QbQuestionAnswer.deleted == 0,
                ),
            )
            .where(
                QbQuestionAttempt.id == attempt_id,
                QbQuestionAttempt.user_id == user_id,
                QbQuestionAttempt.deleted == 0,
            )
        )
        if for_update:
            stmt = stmt.with_for_update()
        row = (await db.execute(stmt)).first()
        return EvaluationAttemptContext(*row) if row is not None else None

    async def list_latest_subjective_contexts(
        self,
        db: AsyncSession,
        *,
        session_id: int,
        user_id: int,
    ) -> list[EvaluationAttemptContext]:
        """获取会话每道主观题最近一次作答"""
        latest_attempt = (
            select(
                QbQuestionAttempt.session_item_id,
                func.max(QbQuestionAttempt.attempt_no).label('attempt_no'),
            )
            .where(
                QbQuestionAttempt.session_id == session_id,
                QbQuestionAttempt.user_id == user_id,
                QbQuestionAttempt.deleted == 0,
            )
            .group_by(QbQuestionAttempt.session_item_id)
            .subquery()
        )
        stmt = (
            select(
                QbQuestionAttempt,
                QbPracticeSession,
                QbPracticeSessionItem,
                QbQuestion,
                QbQuestionAnswer,
            )
            .join(
                latest_attempt,
                and_(
                    latest_attempt.c.session_item_id == QbQuestionAttempt.session_item_id,
                    latest_attempt.c.attempt_no == QbQuestionAttempt.attempt_no,
                ),
            )
            .join(
                QbPracticeSession,
                and_(
                    QbPracticeSession.id == QbQuestionAttempt.session_id,
                    QbPracticeSession.user_id == QbQuestionAttempt.user_id,
                    QbPracticeSession.deleted == 0,
                ),
            )
            .join(
                QbPracticeSessionItem,
                and_(
                    QbPracticeSessionItem.id == QbQuestionAttempt.session_item_id,
                    QbPracticeSessionItem.session_id == QbQuestionAttempt.session_id,
                    QbPracticeSessionItem.deleted == 0,
                ),
            )
            .join(
                QbQuestion,
                and_(
                    QbQuestion.id == QbQuestionAttempt.question_id,
                    QbQuestion.deleted == 0,
                ),
            )
            .join(
                QbQuestionAnswer,
                and_(
                    QbQuestionAnswer.question_id == QbQuestionAttempt.question_id,
                    QbQuestionAnswer.grading_method.in_({'manual', 'rubric', 'custom'}),
                    QbQuestionAnswer.deleted == 0,
                ),
            )
            .where(
                QbQuestionAttempt.session_id == session_id,
                QbQuestionAttempt.user_id == user_id,
                QbQuestionAttempt.deleted == 0,
            )
            .order_by(QbPracticeSessionItem.position, QbQuestionAttempt.id)
        )
        return list(starmap(EvaluationAttemptContext, (await db.execute(stmt)).all()))

    async def list_latest_attempt_runs_by_session(
        self,
        db: AsyncSession,
        *,
        session_id: int,
    ) -> list[QbEvaluationRun]:
        """获取会话内各作答当前有效的 AI 判分运行"""
        stmt = (
            select(QbEvaluationRun)
            .join(
                QbQuestionAttempt,
                and_(
                    QbQuestionAttempt.id == QbEvaluationRun.attempt_id,
                    QbQuestionAttempt.session_id == session_id,
                    QbQuestionAttempt.deleted == 0,
                ),
            )
            .where(
                QbEvaluationRun.purpose == 'attempt_grading',
                QbEvaluationRun.is_latest.is_(True),
                QbEvaluationRun.deleted == 0,
            )
            .order_by(QbQuestionAttempt.session_item_id, QbEvaluationRun.id)
        )
        return list((await db.execute(stmt)).scalars().all())

    async def create(self, db: AsyncSession, data: dict[str, Any]) -> QbEvaluationRun:
        """创建一条不可覆盖的评测运行"""
        run = QbEvaluationRun(**data)
        db.add(run)
        await db.flush()
        return run


evaluation_run_dao: CRUDEvaluationRun = CRUDEvaluationRun(QbEvaluationRun)
