from collections.abc import Sequence

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.learning.model.plan import LearningPlan, LearningPlanDelivery


class CRUDLearningPlan(CRUDPlus[LearningPlan]):
    async def get(self, db: AsyncSession, plan_id: int) -> LearningPlan | None:
        return await self.select_model_by_column(db, id=plan_id, deleted=0)

    async def get_select(
        self,
        *,
        user_id: int | None = None,
        status: str | None = None,
        source_type: str | None = None,
    ) -> Select:
        stmt = select(LearningPlan).where(LearningPlan.deleted == 0)
        if user_id is not None:
            stmt = stmt.where(LearningPlan.user_id == user_id)
        if status:
            stmt = stmt.where(LearningPlan.status == status)
        if source_type:
            stmt = stmt.where(LearningPlan.source_type == source_type)
        return stmt.order_by(LearningPlan.created_time.desc())

    async def list_by_user(self, db: AsyncSession, user_id: int) -> Sequence[LearningPlan]:
        result = await db.execute(
            select(LearningPlan)
            .where(LearningPlan.user_id == user_id, LearningPlan.deleted == 0)
            .order_by(LearningPlan.created_time.desc())
        )
        return result.scalars().all()


class CRUDLearningDelivery(CRUDPlus[LearningPlanDelivery]):
    async def get(self, db: AsyncSession, delivery_id: int) -> LearningPlanDelivery | None:
        return await self.select_model_by_column(db, id=delivery_id, deleted=0)

    async def get_by_external_order(
        self,
        db: AsyncSession,
        source_channel: str,
        external_order_no: str,
    ) -> LearningPlanDelivery | None:
        return await self.select_model_by_column(
            db,
            source_channel=source_channel,
            external_order_no=external_order_no,
            deleted=0,
        )

    async def get_select(
        self,
        *,
        user_id: int | None = None,
        status: str | None = None,
        source_channel: str | None = None,
    ) -> Select:
        stmt = select(LearningPlanDelivery).where(LearningPlanDelivery.deleted == 0)
        if user_id is not None:
            stmt = stmt.where(LearningPlanDelivery.user_id == user_id)
        if status:
            stmt = stmt.where(LearningPlanDelivery.status == status)
        if source_channel:
            stmt = stmt.where(LearningPlanDelivery.source_channel == source_channel)
        return stmt.order_by(LearningPlanDelivery.created_time.desc())


learning_plan_dao = CRUDLearningPlan(LearningPlan)
learning_delivery_dao = CRUDLearningDelivery(LearningPlanDelivery)
