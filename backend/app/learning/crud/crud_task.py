from collections.abc import Sequence
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.learning.model.task import LearningTask, LearningTaskGoal, LearningTaskKnowledgePoint


class CRUDLearningTask(CRUDPlus[LearningTask]):
    async def get(self, db: AsyncSession, task_id: int) -> LearningTask | None:
        return await self.select_model_by_column(db, id=task_id, deleted=0)

    async def list_by_plan(self, db: AsyncSession, plan_id: int) -> Sequence[LearningTask]:
        result = await db.execute(
            select(LearningTask)
            .where(LearningTask.plan_id == plan_id, LearningTask.deleted == 0)
            .order_by(LearningTask.plan_date.asc(), LearningTask.order_index.asc(), LearningTask.id.asc())
        )
        return result.scalars().all()

    async def list_by_user_date(self, db: AsyncSession, user_id: int, target: date) -> Sequence[LearningTask]:
        result = await db.execute(
            select(LearningTask)
            .where(
                LearningTask.user_id == user_id,
                LearningTask.plan_date == target,
                LearningTask.deleted == 0,
            )
            .order_by(LearningTask.order_index.asc(), LearningTask.id.asc())
        )
        return result.scalars().all()

    async def replace_relations(
        self,
        db: AsyncSession,
        *,
        task_id: int,
        knowledge_points: list[dict] | None = None,
        goals: list[dict] | None = None,
    ) -> None:
        if knowledge_points is not None:
            await db.execute(
                LearningTaskKnowledgePoint.__table__.delete().where(LearningTaskKnowledgePoint.task_id == task_id)
            )
            if knowledge_points:
                db.add_all([LearningTaskKnowledgePoint(task_id=task_id, **item) for item in knowledge_points])
        if goals is not None:
            await db.execute(LearningTaskGoal.__table__.delete().where(LearningTaskGoal.task_id == task_id))
            if goals:
                db.add_all([LearningTaskGoal(task_id=task_id, **item) for item in goals])
        await db.flush()


learning_task_dao = CRUDLearningTask(LearningTask)
