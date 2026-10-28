from sqlalchemy import BigInteger, case, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.question_bank_v2.model.annotation import QbQuestionAnnotation
from backend.app.question_bank_v2.model.material import QbQuestionMaterial
from backend.app.question_bank_v2.model.practice import QbPracticeSession, QbPracticeSessionItem, QbQuestionAttempt
from backend.app.question_bank_v2.utils.annotation_policy import (
    PERSISTENT_ANNOTATION_MODES,
    TEMPORARY_ANNOTATION_SOURCES,
)


class CRUDQuestionAnnotation(CRUDPlus[QbQuestionAnnotation]):
    async def latest_document(
        self, db: AsyncSession, *, user_id: int, question_id: int, exclude_context_key: str | None = None
    ) -> QbQuestionAnnotation | None:
        """个人标注按题目找回，不依赖原练习会话是否仍在历史入口中。"""
        stmt = select(QbQuestionAnnotation).where(
            QbQuestionAnnotation.user_id == user_id,
            QbQuestionAnnotation.question_id == question_id,
            QbQuestionAnnotation.deleted == 0,
        )
        item_id = case(
            (
                QbQuestionAnnotation.context_key.like('item:%'),
                cast(func.substr(QbQuestionAnnotation.context_key, 6), BigInteger),
            ),
            else_=None,
        )
        meaningful_practice = (
            select(QbPracticeSessionItem.id)
            .join(QbPracticeSession, QbPracticeSession.id == QbPracticeSessionItem.session_id)
            .where(
                QbPracticeSessionItem.id == item_id,
                QbPracticeSessionItem.question_id == QbQuestionAnnotation.question_id,
                QbPracticeSession.user_id == QbQuestionAnnotation.user_id,
                QbPracticeSession.mode.in_(PERSISTENT_ANNOTATION_MODES),
                QbPracticeSession.source_type.not_in(TEMPORARY_ANNOTATION_SOURCES),
                func.coalesce(QbPracticeSession.delivery_config['annotations_enabled'].as_boolean(), True).is_(True),
            )
            .correlate(QbQuestionAnnotation)
            .exists()
        )
        # Hidden sessions remain eligible; temporary drills do not enter the personal history.
        stmt = stmt.where(or_(QbQuestionAnnotation.context_key.like('review:%'), meaningful_practice))
        if exclude_context_key is not None:
            stmt = stmt.where(QbQuestionAnnotation.context_key != exclude_context_key)
        stmt = stmt.order_by(
            func.coalesce(QbQuestionAnnotation.updated_time, QbQuestionAnnotation.created_time).desc(),
            QbQuestionAnnotation.id.desc(),
        ).limit(1)
        return (await db.execute(stmt)).scalars().first()

    async def get_document(
        self, db: AsyncSession, *, user_id: int, question_id: int, context_key: str, for_update: bool = False
    ) -> QbQuestionAnnotation | None:
        stmt = select(QbQuestionAnnotation).where(
            QbQuestionAnnotation.user_id == user_id,
            QbQuestionAnnotation.question_id == question_id,
            QbQuestionAnnotation.context_key == context_key,
            QbQuestionAnnotation.deleted == 0,
        )
        if for_update:
            stmt = stmt.with_for_update()
        return (await db.execute(stmt)).scalars().first()

    async def latest_attempt(
        self, db: AsyncSession, *, user_id: int, question_id: int, wrong: bool = False
    ) -> QbQuestionAttempt | None:
        stmt = select(QbQuestionAttempt).where(
            QbQuestionAttempt.user_id == user_id,
            QbQuestionAttempt.question_id == question_id,
            QbQuestionAttempt.deleted == 0,
        )
        stmt = stmt.options(joinedload(QbQuestionAttempt.session))
        if wrong:
            stmt = stmt.where(QbQuestionAttempt.is_correct.is_(False))
        return (
            (
                await db.execute(
                    stmt.order_by(QbQuestionAttempt.submitted_time.desc(), QbQuestionAttempt.id.desc()).limit(1)
                )
            )
            .scalars()
            .first()
        )

    async def material_contexts(self, db: AsyncSession, question_id: int) -> set[tuple[int, int]]:
        result = await db.execute(
            select(QbQuestionMaterial.material_id, QbQuestionMaterial.material_revision_id).where(
                QbQuestionMaterial.question_id == question_id,
                QbQuestionMaterial.deleted == 0,
            )
        )
        return {(row[0], row[1]) for row in result}


question_annotation_dao = CRUDQuestionAnnotation(QbQuestionAnnotation)
