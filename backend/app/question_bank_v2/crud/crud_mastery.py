from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import and_, select
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.question_bank_v2.model.knowledge import (
    QbKnowledgePoint,
    QbKnowledgeSystem,
    QbQuestionKnowledgePoint,
)
from backend.app.question_bank_v2.model.mastery import (
    QbQuestionAttemptKnowledgePoint,
    QbUserKnowledgeMastery,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy.ext.asyncio import AsyncSession

    from backend.app.question_bank_v2.model.practice import QbQuestionAttempt


class CRUDKnowledgeMastery(CRUDPlus[QbUserKnowledgeMastery]):
    """用户知识点掌握度投影数据库操作类。"""

    async def get(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        system_id: int,
        knowledge_point_id: int,
        for_update: bool = False,
    ) -> QbUserKnowledgeMastery | None:
        stmt = select(QbUserKnowledgeMastery).where(
            QbUserKnowledgeMastery.user_id == user_id,
            QbUserKnowledgeMastery.system_id == system_id,
            QbUserKnowledgeMastery.knowledge_point_id == knowledge_point_id,
            QbUserKnowledgeMastery.deleted == 0,
        )
        if for_update:
            stmt = stmt.with_for_update()
        return (await db.execute(stmt)).scalars().first()

    async def create(self, db: AsyncSession, data: dict[str, Any]) -> QbUserKnowledgeMastery:
        mastery = QbUserKnowledgeMastery(**data)
        db.add(mastery)
        await db.flush()
        return mastery

    async def get_scope(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        system_id: int,
        knowledge_point_ids: Sequence[int] | None = None,
    ) -> list[QbUserKnowledgeMastery]:
        stmt = select(QbUserKnowledgeMastery).where(
            QbUserKnowledgeMastery.user_id == user_id,
            QbUserKnowledgeMastery.system_id == system_id,
            QbUserKnowledgeMastery.deleted == 0,
        )
        if knowledge_point_ids:
            stmt = stmt.where(QbUserKnowledgeMastery.knowledge_point_id.in_(knowledge_point_ids))
        stmt = stmt.order_by(QbUserKnowledgeMastery.knowledge_point_id)
        return list((await db.execute(stmt)).scalars().all())


class CRUDAttemptKnowledgePoint(CRUDPlus[QbQuestionAttemptKnowledgePoint]):
    """作答知识点快照数据库操作类。"""

    async def get_for_attempt(
        self,
        db: AsyncSession,
        *,
        attempt_id: int,
        system_id: int,
        for_update: bool = False,
    ) -> list[QbQuestionAttemptKnowledgePoint]:
        stmt = select(QbQuestionAttemptKnowledgePoint).where(
            QbQuestionAttemptKnowledgePoint.attempt_id == attempt_id,
            QbQuestionAttemptKnowledgePoint.system_id == system_id,
            QbQuestionAttemptKnowledgePoint.deleted == 0,
        )
        if for_update:
            stmt = stmt.with_for_update()
        return list((await db.execute(stmt)).scalars().all())

    async def get_question_mappings(
        self,
        db: AsyncSession,
        *,
        question_id: int,
        system_id: int,
    ) -> list[dict[str, Any]]:
        stmt = (
            select(
                QbQuestionKnowledgePoint.knowledge_point_id,
                QbQuestionKnowledgePoint.role,
                QbQuestionKnowledgePoint.weight,
                QbQuestionKnowledgePoint.source,
            )
            .join(
                QbKnowledgePoint,
                and_(
                    QbKnowledgePoint.id == QbQuestionKnowledgePoint.knowledge_point_id,
                    QbKnowledgePoint.deleted == 0,
                    QbKnowledgePoint.system_id == system_id,
                ),
            )
            .join(
                QbKnowledgeSystem,
                and_(
                    QbKnowledgeSystem.id == QbKnowledgePoint.system_id,
                    QbKnowledgeSystem.deleted == 0,
                    QbKnowledgeSystem.status == 'active',
                ),
            )
            .where(
                QbQuestionKnowledgePoint.question_id == question_id,
                QbQuestionKnowledgePoint.deleted == 0,
            )
            .order_by(QbQuestionKnowledgePoint.role, QbQuestionKnowledgePoint.id)
        )
        return [dict(row) for row in (await db.execute(stmt)).mappings().all()]

    async def get_applied_evidence(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        system_id: int,
        knowledge_point_id: int,
    ) -> list[QbQuestionAttemptKnowledgePoint]:
        stmt = (
            select(QbQuestionAttemptKnowledgePoint)
            .where(
                QbQuestionAttemptKnowledgePoint.user_id == user_id,
                QbQuestionAttemptKnowledgePoint.system_id == system_id,
                QbQuestionAttemptKnowledgePoint.knowledge_point_id == knowledge_point_id,
                QbQuestionAttemptKnowledgePoint.deleted == 0,
                QbQuestionAttemptKnowledgePoint.evidence_applied.is_(True),
                QbQuestionAttemptKnowledgePoint.correctness.is_not(None),
                QbQuestionAttemptKnowledgePoint.role.in_({'primary', 'secondary'}),
            )
            .order_by(QbQuestionAttemptKnowledgePoint.graded_time, QbQuestionAttemptKnowledgePoint.id)
        )
        return list((await db.execute(stmt)).scalars().all())

    async def create_snapshots(
        self,
        db: AsyncSession,
        *,
        attempt: QbQuestionAttempt,
        system_id: int,
        correctness: Any,
        graded_time: Any,
    ) -> list[QbQuestionAttemptKnowledgePoint]:
        mappings = await self.get_question_mappings(
            db,
            question_id=attempt.question_id,
            system_id=system_id,
        )
        if not mappings:
            return []
        active = [row for row in mappings if row['role'] in {'primary', 'secondary'}]
        total_weight = sum((row['weight'] for row in active), start=0)
        snapshots: list[QbQuestionAttemptKnowledgePoint] = []
        for row in mappings:
            normalized_weight = row['weight']
            if row['role'] in {'primary', 'secondary'} and total_weight > 0:
                normalized_weight = row['weight'] / total_weight
            snapshot = QbQuestionAttemptKnowledgePoint(
                attempt_id=attempt.id,
                user_id=attempt.user_id,
                question_id=attempt.question_id,
                system_id=system_id,
                knowledge_point_id=row['knowledge_point_id'],
                role=row['role'],
                weight=normalized_weight,
                source=row['source'],
                correctness=correctness if row['role'] in {'primary', 'secondary'} else None,
                graded_time=graded_time if correctness is not None else None,
            )
            db.add(snapshot)
            snapshots.append(snapshot)
        await db.flush()
        return snapshots


user_knowledge_mastery_dao = CRUDKnowledgeMastery(QbUserKnowledgeMastery)
attempt_knowledge_point_dao = CRUDAttemptKnowledgePoint(QbQuestionAttemptKnowledgePoint)
