from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.learning.enums import LearningFocusStatus
from backend.app.learning.model.execution import LearningCompletionRecord, LearningFocusSession


class CRUDLearningFocus(CRUDPlus[LearningFocusSession]):
    async def get(self, db: AsyncSession, session_id: int, user_id: int) -> LearningFocusSession | None:
        return await self.select_model_by_column(db, id=session_id, user_id=user_id, deleted=0)

    async def get_current(self, db: AsyncSession, user_id: int) -> LearningFocusSession | None:
        result = await db.execute(
            select(LearningFocusSession)
            .where(
                LearningFocusSession.user_id == user_id,
                LearningFocusSession.status.in_((LearningFocusStatus.running.value, LearningFocusStatus.paused.value)),
                LearningFocusSession.deleted == 0,
            )
            .order_by(LearningFocusSession.started_at.desc())
        )
        return result.scalars().first()

    async def sum_task_focus_seconds(self, db: AsyncSession, task_id: int) -> int:
        result = await db.execute(
            select(func.coalesce(func.sum(LearningFocusSession.focused_seconds), 0)).where(
                LearningFocusSession.task_id == task_id,
                LearningFocusSession.status == LearningFocusStatus.completed.value,
                LearningFocusSession.deleted == 0,
            )
        )
        return int(result.scalar() or 0)


class CRUDLearningCompletion(CRUDPlus[LearningCompletionRecord]):
    async def get_latest(self, db: AsyncSession, task_id: int) -> LearningCompletionRecord | None:
        result = await db.execute(
            select(LearningCompletionRecord)
            .where(LearningCompletionRecord.task_id == task_id, LearningCompletionRecord.deleted == 0)
            .order_by(LearningCompletionRecord.completed_at.desc(), LearningCompletionRecord.id.desc())
        )
        return result.scalars().first()


learning_focus_dao = CRUDLearningFocus(LearningFocusSession)
learning_completion_dao = CRUDLearningCompletion(LearningCompletionRecord)
