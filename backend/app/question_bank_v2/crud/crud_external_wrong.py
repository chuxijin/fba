"""外部错误事件与导入批次分开；只使用现有 capture 事件，不制造练习会话。"""

from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.question_bank_v2.model.review import QbQuestionReview, QbWrongQuestionState
from backend.app.question_bank_v2.utils.external_practice import import_digest

EXTERNAL_WRONG_KEY = 'external_wrong'


class CRUDExternalWrong:
    @staticmethod
    async def get_events(db: AsyncSession, *, user_id: int, question_ids: list[int]) -> list[QbQuestionReview]:
        rows = await db.scalars(
            select(QbQuestionReview)
            .where(
                QbQuestionReview.user_id == user_id,
                QbQuestionReview.question_id.in_(question_ids),
                QbQuestionReview.event_type == 'capture',
                QbQuestionReview.deleted == 0,
                or_(
                    QbQuestionReview.review_data[EXTERNAL_WRONG_KEY]['source_key'].as_string().is_not(None),
                    QbQuestionReview.review_data[EXTERNAL_WRONG_KEY]['legacy_initial'].as_boolean().is_(True),
                ),
            )
            .order_by(QbQuestionReview.reviewed_time, QbQuestionReview.id)
        )
        return list(rows)

    @staticmethod
    async def get_state(db: AsyncSession, *, user_id: int, question_id: int) -> QbWrongQuestionState | None:
        return (
            await db.scalars(
                select(QbWrongQuestionState)
                .where(
                    QbWrongQuestionState.user_id == user_id,
                    QbWrongQuestionState.question_id == question_id,
                    QbWrongQuestionState.deleted == 0,
                )
                .with_for_update()
            )
        ).first()

    @staticmethod
    async def get_states(db: AsyncSession, *, user_id: int, question_ids: list[int]) -> list[QbWrongQuestionState]:
        return list(
            await db.scalars(
                select(QbWrongQuestionState)
                .where(
                    QbWrongQuestionState.user_id == user_id,
                    QbWrongQuestionState.question_id.in_(question_ids),
                    QbWrongQuestionState.deleted == 0,
                )
                .order_by(QbWrongQuestionState.id)
                .with_for_update()
            )
        )

    @staticmethod
    async def create_event(
        db: AsyncSession, *, state: QbWrongQuestionState, data: dict[str, Any], source_attempt_id: int | None
    ) -> QbQuestionReview:
        digest = import_digest(state.id, data['platform'], data['source_key'], data['source_question_key'])
        event = QbQuestionReview(
            user_id=state.user_id,
            question_id=state.question_id,
            wrong_state_id=state.id,
            source_attempt_id=source_attempt_id,
            event_type='capture',
            # 复盘耗时不是作答用时；未知作答用时保存在 data 中为 null。
            duration_ms=0,
            review_data={EXTERNAL_WRONG_KEY: data},
            idempotency_key=f'external-wrong:{digest}',
            created_by=state.user_id,
        )
        db.add(event)
        if data.get('legacy_initial'):
            # 原来仅存于状态的快照，采集日期来自旧状态，不伪造真实作答日期。
            event.reviewed_time = state.created_time
        await db.flush()
        return event


external_wrong_dao = CRUDExternalWrong()
