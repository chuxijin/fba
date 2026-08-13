from collections.abc import Sequence

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.learning.model.template import (
    LearningPlanTemplate,
    LearningPlanTemplateStage,
    LearningPlanTemplateTask,
    LearningPlanTemplateTaskGoal,
    LearningPlanTemplateTaskKnowledgePoint,
)


class CRUDLearningPlanTemplate(CRUDPlus[LearningPlanTemplate]):
    async def get(self, db: AsyncSession, template_id: int) -> LearningPlanTemplate | None:
        return await self.select_model_by_column(db, id=template_id, deleted=0)

    async def get_by_code(self, db: AsyncSession, code: str) -> LearningPlanTemplate | None:
        return await self.select_model_by_column(db, code=code, deleted=0)

    async def get_select(
        self,
        *,
        status: str | None = None,
        exam_type: str | None = None,
    ) -> Select:
        stmt = select(LearningPlanTemplate).where(LearningPlanTemplate.deleted == 0)
        if status:
            stmt = stmt.where(LearningPlanTemplate.status == status)
        if exam_type:
            stmt = stmt.where(LearningPlanTemplate.exam_type == exam_type)
        return stmt.order_by(LearningPlanTemplate.status.asc(), LearningPlanTemplate.updated_time.desc().nullslast())


class CRUDLearningPlanTemplateStage(CRUDPlus[LearningPlanTemplateStage]):
    async def get(self, db: AsyncSession, stage_id: int) -> LearningPlanTemplateStage | None:
        return await self.select_model_by_column(db, id=stage_id, deleted=0)

    async def list_by_template(self, db: AsyncSession, template_id: int) -> Sequence[LearningPlanTemplateStage]:
        result = await db.execute(
            select(LearningPlanTemplateStage)
            .where(
                LearningPlanTemplateStage.template_id == template_id,
                LearningPlanTemplateStage.deleted == 0,
            )
            .order_by(LearningPlanTemplateStage.order_index.asc(), LearningPlanTemplateStage.start_day.asc())
        )
        return result.scalars().all()


class CRUDLearningPlanTemplateTask(CRUDPlus[LearningPlanTemplateTask]):
    async def get(self, db: AsyncSession, task_id: int) -> LearningPlanTemplateTask | None:
        return await self.select_model_by_column(db, id=task_id, deleted=0)

    async def list_by_template(self, db: AsyncSession, template_id: int) -> Sequence[LearningPlanTemplateTask]:
        result = await db.execute(
            select(LearningPlanTemplateTask)
            .where(
                LearningPlanTemplateTask.template_id == template_id,
                LearningPlanTemplateTask.deleted == 0,
            )
            .order_by(
                LearningPlanTemplateTask.relative_day.asc(),
                LearningPlanTemplateTask.order_index.asc(),
                LearningPlanTemplateTask.id.asc(),
            )
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
                LearningPlanTemplateTaskKnowledgePoint.__table__.delete().where(
                    LearningPlanTemplateTaskKnowledgePoint.template_task_id == task_id
                )
            )
            if knowledge_points:
                db.add_all(
                    [
                        LearningPlanTemplateTaskKnowledgePoint(template_task_id=task_id, **item)
                        for item in knowledge_points
                    ]
                )
        if goals is not None:
            await db.execute(
                LearningPlanTemplateTaskGoal.__table__.delete().where(
                    LearningPlanTemplateTaskGoal.template_task_id == task_id
                )
            )
            if goals:
                db.add_all([LearningPlanTemplateTaskGoal(template_task_id=task_id, **item) for item in goals])
        await db.flush()


learning_template_dao = CRUDLearningPlanTemplate(LearningPlanTemplate)
learning_template_stage_dao = CRUDLearningPlanTemplateStage(LearningPlanTemplateStage)
learning_template_task_dao = CRUDLearningPlanTemplateTask(LearningPlanTemplateTask)
