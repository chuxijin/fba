from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.admin.model.user import User
from backend.app.learning.crud import learning_delivery_dao, learning_plan_dao
from backend.app.learning.model.plan import LearningPlan
from backend.app.learning.model.task import LearningTask
from backend.app.learning.model.template import LearningPlanTemplate
from backend.app.learning.schema.plan import (
    CreateLearningPlanParam,
    GetLearningPlanDetail,
    UpdateLearningPlanParam,
)
from backend.common.exception import errors


class LearningPlanService:
    async def get(self, *, db: AsyncSession, plan_id: int) -> LearningPlan:
        plan = await learning_plan_dao.get(db, plan_id)
        if plan is None:
            raise errors.NotFoundError(msg='学习计划不存在')
        return plan

    async def get_detail(self, *, db: AsyncSession, plan_id: int) -> GetLearningPlanDetail:
        plan = await self.get(db=db, plan_id=plan_id)
        return await self._build_detail(db=db, plan=plan)

    async def get_all(
        self,
        *,
        db: AsyncSession,
        user_id: int | None = None,
        status: str | None = None,
        source_type: str | None = None,
    ) -> list[GetLearningPlanDetail]:
        stmt = await learning_plan_dao.get_select(user_id=user_id, status=status, source_type=source_type)
        result = await db.execute(stmt.limit(500))
        plans = result.scalars().all()
        return [await self._build_detail(db=db, plan=plan) for plan in plans]

    async def create(
        self,
        *,
        db: AsyncSession,
        obj: CreateLearningPlanParam,
        created_by: int,
    ) -> GetLearningPlanDetail:
        await self._ensure_user(db=db, user_id=obj.user_id)
        if obj.delivery_id is not None:
            delivery = await learning_delivery_dao.get(db, obj.delivery_id)
            if delivery is None:
                raise errors.NotFoundError(msg='交付单不存在')
            if delivery.user_id is not None and delivery.user_id != obj.user_id:
                raise errors.RequestError(msg='交付单用户与计划用户不一致')

        data = obj.model_dump(mode='python')
        plan = LearningPlan(**data, created_by=created_by)
        db.add(plan)
        await db.flush()
        await db.refresh(plan)
        return await self._build_detail(db=db, plan=plan)

    async def update(
        self,
        *,
        db: AsyncSession,
        plan_id: int,
        obj: UpdateLearningPlanParam,
        updated_by: int,
    ) -> GetLearningPlanDetail:
        plan = await self.get(db=db, plan_id=plan_id)
        fields = obj.model_dump(mode='python', exclude_unset=True)
        start_date = fields.get('start_date', plan.start_date)
        end_date = fields.get('end_date', plan.end_date)
        if end_date is not None and end_date < start_date:
            raise errors.RequestError(msg='结束日期不能早于开始日期')
        if fields.get('delivery_id') is not None:
            delivery = await learning_delivery_dao.get(db, fields['delivery_id'])
            if delivery is None:
                raise errors.NotFoundError(msg='交付单不存在')
            if delivery.user_id is not None and delivery.user_id != plan.user_id:
                raise errors.RequestError(msg='交付单用户与计划用户不一致')
        if fields:
            fields['updated_by'] = updated_by
            await learning_plan_dao.update_model(db, plan_id, fields)
        refreshed = await self.get(db=db, plan_id=plan_id)
        return await self._build_detail(db=db, plan=refreshed)

    async def delete(self, *, db: AsyncSession, plan_id: int) -> None:
        await self.get(db=db, plan_id=plan_id)
        await learning_plan_dao.delete_model(db, plan_id)

    async def _build_detail(self, *, db: AsyncSession, plan: LearningPlan) -> GetLearningPlanDetail:
        user_result = await db.execute(select(User.username, User.nickname).where(User.id == plan.user_id))
        user_row = user_result.first()
        count_result = await db.execute(
            select(
                func.count(LearningTask.id),
                func.count(LearningTask.id).filter(LearningTask.status == 'completed'),
            ).where(LearningTask.plan_id == plan.id, LearningTask.deleted == 0)
        )
        task_count, completed_count = count_result.one()
        detail = GetLearningPlanDetail.model_validate(plan)
        if plan.template_id is not None:
            template_result = await db.execute(
                select(LearningPlanTemplate.name).where(LearningPlanTemplate.id == plan.template_id)
            )
            detail.template_name = template_result.scalar_one_or_none()
        detail.username = user_row.username if user_row else None
        detail.nickname = user_row.nickname if user_row else None
        detail.task_count = int(task_count or 0)
        detail.completed_task_count = int(completed_count or 0)
        return detail

    @staticmethod
    async def _ensure_user(*, db: AsyncSession, user_id: int) -> None:
        result = await db.execute(select(User.id).where(User.id == user_id, User.deleted == 0))
        if result.scalar_one_or_none() is None:
            raise errors.NotFoundError(msg='用户不存在')


learning_plan_service = LearningPlanService()
