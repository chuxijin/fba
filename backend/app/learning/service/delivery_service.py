from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.admin.model.user import User
from backend.app.learning.crud import learning_delivery_dao, learning_plan_dao
from backend.app.learning.enums import LearningDeliveryStatus, LearningPlanSource, LearningPlanStatus
from backend.app.learning.model.plan import LearningPlan, LearningPlanDelivery
from backend.app.learning.model.task import LearningTask
from backend.app.learning.schema.plan import (
    CreateLearningDeliveryParam,
    GetLearningDeliveryDetail,
    UpdateLearningDeliveryParam,
)
from backend.app.learning.schema.template import InstantiateLearningPlanParam
from backend.app.learning.service.template_service import learning_template_service
from backend.common.exception import errors
from backend.utils.timezone import timezone


class LearningDeliveryService:
    async def get(self, *, db: AsyncSession, delivery_id: int) -> LearningPlanDelivery:
        delivery = await learning_delivery_dao.get(db, delivery_id)
        if delivery is None:
            raise errors.NotFoundError(msg='学习计划交付单不存在')
        return delivery

    async def get_detail(self, *, db: AsyncSession, delivery_id: int) -> GetLearningDeliveryDetail:
        return await self._build_detail(db=db, delivery=await self.get(db=db, delivery_id=delivery_id))

    async def get_all(
        self,
        *,
        db: AsyncSession,
        user_id: int | None = None,
        status: str | None = None,
        source_channel: str | None = None,
    ) -> list[GetLearningDeliveryDetail]:
        stmt = await learning_delivery_dao.get_select(
            user_id=user_id,
            status=status,
            source_channel=source_channel,
        )
        result = await db.execute(stmt.limit(500))
        return [await self._build_detail(db=db, delivery=item) for item in result.scalars().all()]

    async def create(
        self,
        *,
        db: AsyncSession,
        obj: CreateLearningDeliveryParam,
        created_by: int,
    ) -> GetLearningDeliveryDetail:
        if obj.user_id is not None:
            await self._ensure_user(db=db, user_id=obj.user_id)
        await self._ensure_external_unique(
            db=db,
            source_channel=obj.source_channel,
            external_order_no=obj.external_order_no,
        )
        data = obj.model_dump(mode='python', exclude={'plan'})
        delivery = LearningPlanDelivery(
            delivery_no=self._generate_delivery_no(),
            created_by=created_by,
            **data,
        )
        db.add(delivery)
        await db.flush()

        if obj.plan is not None:
            if obj.user_id is None:
                raise errors.RequestError(msg='同步创建计划时必须选择接收用户')
            if obj.plan.template_id is not None:
                await learning_template_service.instantiate(
                    db=db,
                    template_id=obj.plan.template_id,
                    obj=InstantiateLearningPlanParam(
                        user_id=obj.user_id,
                        start_date=obj.plan.start_date,
                        title=obj.plan.title,
                        delivery_id=delivery.id,
                        description=obj.plan.description,
                    ),
                    created_by=created_by,
                )
            else:
                plan = LearningPlan(
                    user_id=obj.user_id,
                    title=obj.plan.title or '定制学习计划',
                    start_date=obj.plan.start_date,
                    end_date=obj.plan.end_date,
                    source_type=LearningPlanSource.admin_custom.value,
                    status=LearningPlanStatus.draft.value,
                    delivery_id=delivery.id,
                    description=obj.plan.description,
                    created_by=created_by,
                )
                db.add(plan)
                await db.flush()

        return await self._build_detail(db=db, delivery=delivery)

    async def update(
        self,
        *,
        db: AsyncSession,
        delivery_id: int,
        obj: UpdateLearningDeliveryParam,
        updated_by: int,
    ) -> GetLearningDeliveryDetail:
        delivery = await self.get(db=db, delivery_id=delivery_id)
        fields = obj.model_dump(mode='python', exclude_unset=True)
        if fields.get('user_id') is not None:
            await self._ensure_user(db=db, user_id=fields['user_id'])
            plan_result = await db.execute(
                select(LearningPlan.user_id).where(
                    LearningPlan.delivery_id == delivery_id,
                    LearningPlan.deleted == 0,
                )
            )
            plan_user_ids = set(plan_result.scalars().all())
            if plan_user_ids and plan_user_ids != {fields['user_id']}:
                raise errors.RequestError(msg='接收用户与交付单已有计划用户不一致')
        source_channel = fields.get('source_channel', delivery.source_channel)
        external_order_no = fields.get('external_order_no', delivery.external_order_no)
        await self._ensure_external_unique(
            db=db,
            source_channel=source_channel,
            external_order_no=external_order_no,
            exclude_id=delivery_id,
        )
        if fields:
            fields['updated_by'] = updated_by
            await learning_delivery_dao.update_model(db, delivery_id, fields)
        return await self.get_detail(db=db, delivery_id=delivery_id)

    async def publish(
        self,
        *,
        db: AsyncSession,
        delivery_id: int,
        delivered_by: int,
    ) -> GetLearningDeliveryDetail:
        delivery = await self.get(db=db, delivery_id=delivery_id)
        if delivery.status == LearningDeliveryStatus.canceled.value:
            raise errors.RequestError(msg='已取消的交付单不能发布')
        if delivery.status == LearningDeliveryStatus.delivered.value:
            return await self.get_detail(db=db, delivery_id=delivery_id)
        if delivery.user_id is None:
            raise errors.RequestError(msg='交付前必须绑定接收用户')
        plan_result = await db.execute(
            select(LearningPlan).where(
                LearningPlan.delivery_id == delivery_id,
                LearningPlan.deleted == 0,
            )
        )
        plans = plan_result.scalars().all()
        task_result = await db.execute(
            select(func.count(LearningTask.id)).where(
                LearningTask.delivery_id == delivery_id,
                LearningTask.deleted == 0,
            )
        )
        if not plans and int(task_result.scalar() or 0) == 0:
            raise errors.RequestError(msg='交付单尚未创建计划或任务')
        for plan in plans:
            if plan.status == LearningPlanStatus.draft.value:
                await learning_plan_dao.update_model(
                    db,
                    plan.id,
                    {'status': LearningPlanStatus.active.value, 'updated_by': delivered_by},
                )
        await learning_delivery_dao.update_model(
            db,
            delivery_id,
            {
                'status': LearningDeliveryStatus.delivered.value,
                'delivered_by': delivered_by,
                'delivered_at': timezone.now(),
                'updated_by': delivered_by,
            },
        )
        return await self.get_detail(db=db, delivery_id=delivery_id)

    async def _build_detail(
        self,
        *,
        db: AsyncSession,
        delivery: LearningPlanDelivery,
    ) -> GetLearningDeliveryDetail:
        user_row = None
        if delivery.user_id is not None:
            result = await db.execute(select(User.username, User.nickname).where(User.id == delivery.user_id))
            user_row = result.first()
        plan_result = await db.execute(
            select(LearningPlan.id, LearningPlan.title, LearningPlan.template_id)
            .where(LearningPlan.delivery_id == delivery.id, LearningPlan.deleted == 0)
            .order_by(LearningPlan.id.asc())
        )
        plan_row = plan_result.first()
        task_count_result = await db.execute(
            select(func.count(LearningTask.id)).where(
                LearningTask.delivery_id == delivery.id,
                LearningTask.deleted == 0,
            )
        )
        detail = GetLearningDeliveryDetail.model_validate(delivery)
        detail.username = user_row.username if user_row else None
        detail.nickname = user_row.nickname if user_row else None
        detail.plan_id = plan_row.id if plan_row else None
        detail.plan_title = plan_row.title if plan_row else None
        detail.template_id = plan_row.template_id if plan_row else None
        if plan_row and plan_row.template_id is not None:
            from backend.app.learning.model.template import LearningPlanTemplate

            template_result = await db.execute(
                select(LearningPlanTemplate.name).where(LearningPlanTemplate.id == plan_row.template_id)
            )
            detail.template_name = template_result.scalar_one_or_none()
        detail.task_count = int(task_count_result.scalar() or 0)
        return detail

    @staticmethod
    def _generate_delivery_no() -> str:
        return f'LPD{timezone.now().strftime("%Y%m%d%H%M%S")}{uuid4().hex[:6].upper()}'

    @staticmethod
    async def _ensure_user(*, db: AsyncSession, user_id: int) -> None:
        result = await db.execute(select(User.id).where(User.id == user_id, User.deleted == 0))
        if result.scalar_one_or_none() is None:
            raise errors.NotFoundError(msg='用户不存在')

    @staticmethod
    async def _ensure_external_unique(
        *,
        db: AsyncSession,
        source_channel: str | None,
        external_order_no: str | None,
        exclude_id: int | None = None,
    ) -> None:
        if not source_channel or not external_order_no:
            return
        stmt = select(LearningPlanDelivery.id).where(
            LearningPlanDelivery.source_channel == source_channel,
            LearningPlanDelivery.external_order_no == external_order_no,
            LearningPlanDelivery.deleted == 0,
        )
        if exclude_id is not None:
            stmt = stmt.where(LearningPlanDelivery.id != exclude_id)
        result = await db.execute(stmt)
        if result.scalar_one_or_none() is not None:
            raise errors.ConflictError(msg='该渠道订单已经创建过交付单')


learning_delivery_service = LearningDeliveryService()
