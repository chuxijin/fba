from __future__ import annotations

import math

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from backend.app.question_bank_v2.crud.crud_knowledge import DEFAULT_KNOWLEDGE_SYSTEM_VERSION
from backend.app.question_bank_v2.crud.crud_mastery import (
    attempt_knowledge_point_dao,
    user_knowledge_mastery_dao,
)
from backend.app.question_bank_v2.model.knowledge import (
    QbKnowledgePoint,
    QbKnowledgeSystem,
    QbQuestionKnowledgePoint,
)
from backend.core.conf import settings
from backend.utils.timezone import timezone

if TYPE_CHECKING:
    from datetime import datetime

    from sqlalchemy.ext.asyncio import AsyncSession

    from backend.app.question_bank_v2.model.mastery import QbQuestionAttemptKnowledgePoint
    from backend.app.question_bank_v2.model.practice import QbPracticeSessionItem, QbQuestionAttempt

MODEL_VERSION = 'beta_decay_v1'
HALF_LIFE_DAYS = Decimal(str(settings.QBANK_V2_MASTERY_HALF_LIFE_DAYS))
ALPHA_PRIOR = Decimal(1)
BETA_PRIOR = Decimal(1)
MASTERED_MIN_EFFECTIVE_SAMPLE = Decimal(5)
STABLE_MIN_EFFECTIVE_SAMPLE = Decimal(3)


class KnowledgeMasteryService:
    """维护用户-知识体系-知识点掌握度投影。"""

    @staticmethod
    async def resolve_default_system_ids(db: AsyncSession, *, question_id: int) -> list[int]:
        """当前阶段解析题目所属的 default 体系；未来版本选择集中替换这里。"""
        stmt = (
            select(QbKnowledgeSystem.id)
            .join(QbKnowledgePoint, QbKnowledgePoint.system_id == QbKnowledgeSystem.id)
            .join(
                QbQuestionKnowledgePoint,
                QbQuestionKnowledgePoint.knowledge_point_id == QbKnowledgePoint.id,
            )
            .where(
                QbQuestionKnowledgePoint.question_id == question_id,
                QbQuestionKnowledgePoint.deleted == 0,
                QbKnowledgePoint.deleted == 0,
                QbKnowledgeSystem.deleted == 0,
                QbKnowledgeSystem.status == 'active',
                QbKnowledgeSystem.version == DEFAULT_KNOWLEDGE_SYSTEM_VERSION,
            )
            .distinct()
            .order_by(QbKnowledgeSystem.id)
        )
        return [int(value) for value in (await db.execute(stmt)).scalars().all()]

    @staticmethod
    def _correctness(*, attempt: QbQuestionAttempt, max_score: Decimal | None) -> Decimal | None:
        grading_method = getattr(attempt, 'grading_method', None)
        if grading_method in {'ai', 'manual', 'hybrid'} and attempt.score is not None and max_score and max_score > 0:
            score_rate = min(Decimal(1), max(Decimal(0), Decimal(attempt.score) / Decimal(max_score)))
            return score_rate
        if attempt.is_correct is not None:
            return Decimal(1) if attempt.is_correct else Decimal(0)
        if attempt.score is None or max_score is None or max_score <= 0:
            return None
        return min(Decimal(1), max(Decimal(0), Decimal(attempt.score) / Decimal(max_score)))

    @staticmethod
    def _decay(*, elapsed_days: Decimal) -> Decimal:
        if elapsed_days <= 0:
            return Decimal(1)
        return Decimal(str(math.pow(0.5, float(elapsed_days / HALF_LIFE_DAYS))))

    @staticmethod
    def _refresh_state(*, score: Decimal, effective_sample_size: Decimal) -> str:
        if effective_sample_size < Decimal(1):
            return 'unknown'
        if effective_sample_size >= MASTERED_MIN_EFFECTIVE_SAMPLE and score >= Decimal('0.8'):
            return 'mastered'
        if effective_sample_size >= STABLE_MIN_EFFECTIVE_SAMPLE and score >= Decimal('0.6'):
            return 'stable'
        return 'learning'

    @classmethod
    def _refresh_projection_scores(cls, mastery: object) -> None:
        alpha = ALPHA_PRIOR + Decimal(mastery.weighted_correct)
        beta = BETA_PRIOR + Decimal(mastery.weighted_wrong)
        mastery.mastery_score = alpha / (alpha + beta)
        mastery.confidence_score = Decimal(str(1 - math.exp(-float(mastery.effective_sample_size) / 5)))
        mastery.state = cls._refresh_state(
            score=Decimal(mastery.mastery_score),
            effective_sample_size=Decimal(mastery.effective_sample_size),
        )

    @classmethod
    def _rebuild_projection(cls, *, mastery: object, snapshots: list[QbQuestionAttemptKnowledgePoint]) -> None:
        mastery.weighted_correct = Decimal(0)
        mastery.weighted_wrong = Decimal(0)
        mastery.effective_sample_size = Decimal(0)
        mastery.lifetime_correct_weight = Decimal(0)
        mastery.lifetime_wrong_weight = Decimal(0)
        mastery.attempt_count = 0
        mastery.correct_count = 0
        mastery.last_attempt_time = None

        for item in snapshots:
            if item.correctness is None or item.graded_time is None:
                continue
            if mastery.last_attempt_time is not None:
                elapsed_days = max(
                    Decimal(0),
                    Decimal(str((item.graded_time - mastery.last_attempt_time).total_seconds())) / Decimal(86400),
                )
                decay = cls._decay(elapsed_days=elapsed_days)
                mastery.weighted_correct *= decay
                mastery.weighted_wrong *= decay
                mastery.effective_sample_size *= decay
            weight = Decimal(item.weight)
            correctness = Decimal(item.correctness)
            mastery.weighted_correct += weight * correctness
            mastery.weighted_wrong += weight * (Decimal(1) - correctness)
            mastery.effective_sample_size += weight
            mastery.lifetime_correct_weight += weight * correctness
            mastery.lifetime_wrong_weight += weight * (Decimal(1) - correctness)
            mastery.attempt_count += 1
            mastery.correct_count += int(correctness == Decimal(1))
            mastery.last_attempt_time = item.graded_time

        mastery.model_version = MODEL_VERSION
        mastery.calculated_time = timezone.now()
        cls._refresh_projection_scores(mastery)

    @classmethod
    async def _apply_snapshot(
        cls,
        db: AsyncSession,
        *,
        snapshot: QbQuestionAttemptKnowledgePoint,
        attempt_time: datetime,
        correctness: Decimal,
    ) -> None:
        if snapshot.role == 'prerequisite' or snapshot.evidence_applied:
            return
        mastery = await user_knowledge_mastery_dao.get(
            db,
            user_id=snapshot.user_id,
            system_id=snapshot.system_id,
            knowledge_point_id=snapshot.knowledge_point_id,
            for_update=True,
        )
        if mastery is None:
            # Two submissions for the same user/system/point can arrive at
            # the same time.  Let the unique constraint elect one creator,
            # then reload the winner under a row lock.  The savepoint keeps a
            # duplicate-key race from aborting the surrounding transaction.
            try:
                async with db.begin_nested():
                    mastery = await user_knowledge_mastery_dao.create(
                        db,
                        {
                            'user_id': snapshot.user_id,
                            'system_id': snapshot.system_id,
                            'knowledge_point_id': snapshot.knowledge_point_id,
                            'model_version': MODEL_VERSION,
                        },
                    )
            except IntegrityError:
                mastery = await user_knowledge_mastery_dao.get(
                    db,
                    user_id=snapshot.user_id,
                    system_id=snapshot.system_id,
                    knowledge_point_id=snapshot.knowledge_point_id,
                    for_update=True,
                )
                if mastery is None:
                    raise
        if mastery.last_attempt_time is not None and attempt_time < mastery.last_attempt_time:
            snapshot.correctness = correctness
            snapshot.evidence_applied = True
            snapshot.graded_time = attempt_time
            await db.flush()
            evidence = await attempt_knowledge_point_dao.get_applied_evidence(
                db,
                user_id=snapshot.user_id,
                system_id=snapshot.system_id,
                knowledge_point_id=snapshot.knowledge_point_id,
            )
            cls._rebuild_projection(mastery=mastery, snapshots=evidence)
            await db.flush()
            return
        elapsed_days = Decimal(0)
        if mastery.last_attempt_time is not None:
            elapsed_days = max(
                Decimal(0),
                Decimal(str((attempt_time - mastery.last_attempt_time).total_seconds())) / Decimal(86400),
            )
        decay = cls._decay(elapsed_days=elapsed_days)
        mastery.weighted_correct = Decimal(mastery.weighted_correct or 0) * decay
        mastery.weighted_wrong = Decimal(mastery.weighted_wrong or 0) * decay
        mastery.effective_sample_size = Decimal(mastery.effective_sample_size or 0) * decay
        weight = Decimal(snapshot.weight)
        mastery.weighted_correct += weight * correctness
        mastery.weighted_wrong += weight * (Decimal(1) - correctness)
        mastery.effective_sample_size += weight
        mastery.lifetime_correct_weight = Decimal(mastery.lifetime_correct_weight or 0) + weight * correctness
        mastery.lifetime_wrong_weight = Decimal(mastery.lifetime_wrong_weight or 0) + weight * (
            Decimal(1) - correctness
        )
        mastery.attempt_count += 1
        mastery.correct_count += int(correctness == Decimal(1))
        mastery.last_attempt_time = attempt_time
        mastery.calculated_time = timezone.now()
        cls._refresh_projection_scores(mastery)
        snapshot.correctness = correctness
        snapshot.evidence_applied = True
        snapshot.graded_time = attempt_time
        await db.flush()

    @classmethod
    async def _ensure_snapshots(
        cls,
        db: AsyncSession,
        *,
        attempt: QbQuestionAttempt,
        correctness: Decimal | None,
        max_score: Decimal | None,
    ) -> list[QbQuestionAttemptKnowledgePoint]:
        snapshots: list[QbQuestionAttemptKnowledgePoint] = []
        for system_id in await cls.resolve_default_system_ids(db, question_id=attempt.question_id):
            existing = await attempt_knowledge_point_dao.get_for_attempt(
                db,
                attempt_id=attempt.id,
                system_id=system_id,
                for_update=True,
            )
            if not existing:
                existing = await attempt_knowledge_point_dao.create_snapshots(
                    db,
                    attempt=attempt,
                    system_id=system_id,
                    correctness=correctness,
                    graded_time=attempt.submitted_time if correctness is not None else None,
                )
            snapshots.extend(existing)
        return snapshots

    @classmethod
    async def apply_attempt(
        cls,
        db: AsyncSession,
        *,
        attempt: QbQuestionAttempt,
        session_item: QbPracticeSessionItem,
    ) -> None:
        """保存作答知识点快照，并在已判分时立即更新掌握度。"""
        correctness = cls._correctness(attempt=attempt, max_score=session_item.max_score)
        snapshots = await cls._ensure_snapshots(
            db,
            attempt=attempt,
            correctness=correctness,
            max_score=session_item.max_score,
        )
        if correctness is not None:
            for snapshot in snapshots:
                await cls._apply_snapshot(
                    db,
                    snapshot=snapshot,
                    attempt_time=attempt.submitted_time,
                    correctness=correctness,
                )
        await db.flush()

    @classmethod
    async def apply_delayed_grade(
        cls,
        db: AsyncSession,
        *,
        attempt: QbQuestionAttempt,
        session_item: QbPracticeSessionItem,
    ) -> None:
        """把延迟判分结果补写到已保存的知识点快照和掌握度投影。"""
        correctness = cls._correctness(attempt=attempt, max_score=session_item.max_score)
        if correctness is None:
            return
        snapshots = await cls._ensure_snapshots(
            db,
            attempt=attempt,
            correctness=correctness,
            max_score=session_item.max_score,
        )
        for snapshot in snapshots:
            await cls._apply_snapshot(
                db,
                snapshot=snapshot,
                attempt_time=attempt.submitted_time,
                correctness=correctness,
            )
        await db.flush()


knowledge_mastery_service = KnowledgeMasteryService()
