from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.content.model.content import Content
from backend.app.learning.crud import learning_delivery_dao, learning_plan_dao, learning_task_dao
from backend.app.learning.model.plan import LearningPlan
from backend.app.learning.model.task import LearningTask, LearningTaskGoal, LearningTaskKnowledgePoint
from backend.app.learning.schema.task import (
    CreateLearningTaskParam,
    GetLearningTaskDetail,
    GetLearningTaskGoalDetail,
    GetLearningTaskKnowledgePointDetail,
    UpdateLearningTaskParam,
)
from backend.app.question_bank_v2.model.bank import QbBank, QbBankRevision
from backend.app.question_bank_v2.model.knowledge import QbKnowledgePoint, QbKnowledgeSystem
from backend.common.exception import errors


class LearningTaskService:
    async def get(self, *, db: AsyncSession, task_id: int) -> LearningTask:
        task = await learning_task_dao.get(db, task_id)
        if task is None:
            raise errors.NotFoundError(msg='学习任务不存在')
        return task

    async def get_detail(self, *, db: AsyncSession, task_id: int) -> GetLearningTaskDetail:
        return await self._build_detail(db=db, task=await self.get(db=db, task_id=task_id))

    async def list_by_plan(self, *, db: AsyncSession, plan_id: int) -> list[GetLearningTaskDetail]:
        if await learning_plan_dao.get(db, plan_id) is None:
            raise errors.NotFoundError(msg='学习计划不存在')
        tasks = await learning_task_dao.list_by_plan(db, plan_id)
        return [await self._build_detail(db=db, task=task) for task in tasks]

    async def create(
        self,
        *,
        db: AsyncSession,
        obj: CreateLearningTaskParam,
        created_by: int,
    ) -> GetLearningTaskDetail:
        plan = await learning_plan_dao.get(db, obj.plan_id)
        if plan is None:
            raise errors.NotFoundError(msg='学习计划不存在')
        await self._validate_delivery(
            db=db,
            delivery_id=obj.delivery_id,
            plan=plan,
        )
        await self._validate_resource(db=db, data=obj.model_dump(mode='python'))
        await self._validate_knowledge_points(db=db, items=obj.knowledge_points)

        data = obj.model_dump(mode='python', exclude={'knowledge_points', 'goals'})
        if data.get('delivery_id') is None:
            data['delivery_id'] = plan.delivery_id
        task = LearningTask(user_id=plan.user_id, created_by=created_by, **data)
        db.add(task)
        await db.flush()
        await learning_task_dao.replace_relations(
            db,
            task_id=task.id,
            knowledge_points=[item.model_dump(mode='python') for item in obj.knowledge_points],
            goals=[item.model_dump(mode='python') for item in obj.goals],
        )
        await db.refresh(task)
        return await self._build_detail(db=db, task=task)

    async def update(
        self,
        *,
        db: AsyncSession,
        task_id: int,
        obj: UpdateLearningTaskParam,
        updated_by: int,
    ) -> GetLearningTaskDetail:
        task = await self.get(db=db, task_id=task_id)
        fields = obj.model_dump(mode='python', exclude_unset=True)
        knowledge_points = fields.pop('knowledge_points', None) if 'knowledge_points' in fields else None
        goals = fields.pop('goals', None) if 'goals' in fields else None
        if fields.get('delivery_id') is not None:
            plan = await learning_plan_dao.get(db, task.plan_id)
            if plan is None:
                raise errors.NotFoundError(msg='学习计划不存在')
            await self._validate_delivery(
                db=db,
                delivery_id=fields['delivery_id'],
                plan=plan,
            )
        merged = {
            'resource_type': fields.get('resource_type', task.resource_type),
            'resource_id': fields.get('resource_id', task.resource_id),
            'resource_key': fields.get('resource_key', task.resource_key),
            'resource_version_id': fields.get('resource_version_id', task.resource_version_id),
        }
        await self._validate_resource(db=db, data=merged)
        if knowledge_points is not None:
            await self._validate_knowledge_points_dict(db=db, items=knowledge_points)
        if fields:
            fields['updated_by'] = updated_by
            await learning_task_dao.update_model(db, task_id, fields)
        await learning_task_dao.replace_relations(
            db,
            task_id=task_id,
            knowledge_points=knowledge_points,
            goals=goals,
        )
        return await self.get_detail(db=db, task_id=task_id)

    async def delete(self, *, db: AsyncSession, task_id: int) -> None:
        await self.get(db=db, task_id=task_id)
        await learning_task_dao.delete_model(db, task_id)

    async def _build_detail(self, *, db: AsyncSession, task: LearningTask) -> GetLearningTaskDetail:
        knowledge_result = await db.execute(
            select(
                LearningTaskKnowledgePoint,
                QbKnowledgePoint.code,
                QbKnowledgePoint.name,
                QbKnowledgePoint.path,
                QbKnowledgeSystem.name,
            )
            .join(
                QbKnowledgePoint,
                QbKnowledgePoint.id == LearningTaskKnowledgePoint.knowledge_point_id,
            )
            .join(QbKnowledgeSystem, QbKnowledgeSystem.id == LearningTaskKnowledgePoint.knowledge_system_id)
            .where(
                LearningTaskKnowledgePoint.task_id == task.id,
                LearningTaskKnowledgePoint.deleted == 0,
            )
            .order_by(LearningTaskKnowledgePoint.role.asc(), LearningTaskKnowledgePoint.id.asc())
        )
        knowledge_points = []
        for link, point_code, point_name, point_path, system_name in knowledge_result.all():
            knowledge_points.append(
                GetLearningTaskKnowledgePointDetail(
                    id=link.id,
                    knowledge_system_id=link.knowledge_system_id,
                    knowledge_point_id=link.knowledge_point_id,
                    role=link.role,
                    include_descendants=link.include_descendants,
                    weight=link.weight,
                    knowledge_point_code=point_code,
                    knowledge_point_name=point_name,
                    knowledge_point_path=point_path,
                    knowledge_system_name=system_name,
                )
            )
        goal_result = await db.execute(
            select(
                LearningTaskGoal.id,
                LearningTaskGoal.metric,
                LearningTaskGoal.operator,
                LearningTaskGoal.target_value,
                LearningTaskGoal.unit,
                LearningTaskGoal.is_required,
                LearningTaskGoal.config,
            )
            .where(LearningTaskGoal.task_id == task.id, LearningTaskGoal.deleted == 0)
            .order_by(LearningTaskGoal.id.asc())
        )
        goals = [GetLearningTaskGoalDetail(**item) for item in goal_result.mappings().all()]
        detail = GetLearningTaskDetail.model_validate(task)
        detail.knowledge_points = knowledge_points
        detail.goals = goals
        return detail

    async def _validate_knowledge_points(self, *, db: AsyncSession, items: list) -> None:
        await self._validate_knowledge_points_dict(
            db=db,
            items=[item.model_dump(mode='python') for item in items],
        )

    @staticmethod
    async def _validate_delivery(*, db: AsyncSession, delivery_id: int | None, plan: LearningPlan) -> None:
        if delivery_id is None:
            return
        if plan.delivery_id is not None and delivery_id != plan.delivery_id:
            raise errors.RequestError(msg='任务交付单与计划交付单不一致')
        delivery = await learning_delivery_dao.get(db, delivery_id)
        if delivery is None:
            raise errors.NotFoundError(msg='交付单不存在')
        if delivery.user_id is not None and delivery.user_id != plan.user_id:
            raise errors.RequestError(msg='交付单用户与计划用户不一致')

    @staticmethod
    async def _validate_knowledge_points_dict(*, db: AsyncSession, items: list[dict]) -> None:
        if not items:
            return
        for item in items:
            result = await db.execute(
                select(QbKnowledgePoint.id).where(
                    QbKnowledgePoint.id == item['knowledge_point_id'],
                    QbKnowledgePoint.system_id == item['knowledge_system_id'],
                    QbKnowledgePoint.deleted == 0,
                )
            )
            if result.scalar_one_or_none() is None:
                raise errors.RequestError(msg=f'知识点 {item["knowledge_point_id"]} 不属于指定知识体系')

    @staticmethod
    async def _validate_resource(*, db: AsyncSession, data: dict) -> None:
        resource_type = str(data.get('resource_type') or 'none')
        resource_id = data.get('resource_id')
        resource_key = data.get('resource_key')
        version_id = data.get('resource_version_id')
        if resource_type == 'content':
            if resource_id is None:
                raise errors.RequestError(msg='内容任务必须选择内容资源')
            result = await db.execute(select(Content.id).where(Content.id == resource_id, Content.deleted == 0))
            if result.scalar_one_or_none() is None:
                raise errors.NotFoundError(msg='内容资源不存在')
        elif resource_type == 'question_bank':
            if resource_id is None:
                raise errors.RequestError(msg='刷题任务必须选择题库')
            result = await db.execute(select(QbBank.id).where(QbBank.id == resource_id, QbBank.deleted == 0))
            if result.scalar_one_or_none() is None:
                raise errors.NotFoundError(msg='题库不存在')
            if version_id is not None:
                revision = await db.execute(
                    select(QbBankRevision.id).where(
                        QbBankRevision.id == version_id,
                        QbBankRevision.bank_id == resource_id,
                        QbBankRevision.deleted == 0,
                    )
                )
                if revision.scalar_one_or_none() is None:
                    raise errors.RequestError(msg='题库版本与题库不匹配')
        elif resource_type == 'ability' and not resource_key:
            raise errors.RequestError(msg='能力练习必须填写能力标识')


learning_task_service = LearningTaskService()
