from datetime import timedelta

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.admin.model.user import User
from backend.app.content.model.content import Content
from backend.app.learning.crud import (
    learning_delivery_dao,
    learning_template_dao,
    learning_template_stage_dao,
    learning_template_task_dao,
)
from backend.app.learning.enums import LearningPlanSource, LearningPlanStatus, LearningTemplateStatus
from backend.app.learning.model.plan import LearningPlan
from backend.app.learning.model.task import LearningTask, LearningTaskGoal, LearningTaskKnowledgePoint
from backend.app.learning.model.template import (
    LearningPlanTemplate,
    LearningPlanTemplateStage,
    LearningPlanTemplateTask,
    LearningPlanTemplateTaskGoal,
    LearningPlanTemplateTaskKnowledgePoint,
)
from backend.app.learning.schema.plan import GetLearningPlanDetail
from backend.app.learning.schema.template import (
    CreateLearningPlanTemplateParam,
    CreateLearningPlanTemplateStageParam,
    CreateLearningPlanTemplateTaskParam,
    GetLearningPlanTemplateDetail,
    GetLearningPlanTemplateStageDetail,
    GetLearningPlanTemplateTaskDetail,
    GetLearningPlanTemplateTaskGoalDetail,
    GetLearningPlanTemplateTaskKnowledgePointDetail,
    InstantiateLearningPlanParam,
    UpdateLearningPlanTemplateParam,
    UpdateLearningPlanTemplateStageParam,
    UpdateLearningPlanTemplateTaskParam,
)
from backend.app.question_bank_v2.model.bank import QbBank, QbBankItem, QbBankRevision
from backend.app.question_bank_v2.model.knowledge import QbKnowledgePoint, QbKnowledgeSystem
from backend.common.exception import errors


class LearningTemplateService:
    async def get(self, *, db: AsyncSession, template_id: int) -> LearningPlanTemplate:
        template = await learning_template_dao.get(db, template_id)
        if template is None:
            raise errors.NotFoundError(msg='学习计划模板不存在')
        return template

    async def get_detail(self, *, db: AsyncSession, template_id: int) -> GetLearningPlanTemplateDetail:
        return await self._build_template_detail(db=db, template=await self.get(db=db, template_id=template_id))

    async def get_all(
        self,
        *,
        db: AsyncSession,
        status: str | None = None,
        exam_type: str | None = None,
    ) -> list[GetLearningPlanTemplateDetail]:
        stmt = await learning_template_dao.get_select(status=status, exam_type=exam_type)
        result = await db.execute(stmt.limit(500))
        return [await self._build_template_detail(db=db, template=item) for item in result.scalars().all()]

    async def create(
        self,
        *,
        db: AsyncSession,
        obj: CreateLearningPlanTemplateParam,
        created_by: int,
    ) -> GetLearningPlanTemplateDetail:
        await self._ensure_code_unique(db=db, code=obj.code)
        template = LearningPlanTemplate(**obj.model_dump(mode='python'), created_by=created_by)
        db.add(template)
        await db.flush()
        await db.refresh(template)
        return await self._build_template_detail(db=db, template=template)

    async def update(
        self,
        *,
        db: AsyncSession,
        template_id: int,
        obj: UpdateLearningPlanTemplateParam,
        updated_by: int,
    ) -> GetLearningPlanTemplateDetail:
        template = await self.get(db=db, template_id=template_id)
        fields = obj.model_dump(mode='python', exclude_unset=True)
        if 'code' in fields:
            await self._ensure_code_unique(db=db, code=fields['code'], exclude_id=template_id)
        duration_days = fields.get('duration_days', template.duration_days)
        max_day_result = await db.execute(
            select(func.max(LearningPlanTemplateTask.relative_day)).where(
                LearningPlanTemplateTask.template_id == template_id,
                LearningPlanTemplateTask.deleted == 0,
            )
        )
        max_day = int(max_day_result.scalar() or 0)
        if max_day > duration_days:
            raise errors.RequestError(msg=f'模板已有第 {max_day} 天任务，周期不能缩短到 {duration_days} 天')
        if fields:
            fields['updated_by'] = updated_by
            await learning_template_dao.update_model(db, template_id, fields)
        return await self.get_detail(db=db, template_id=template_id)

    async def delete(self, *, db: AsyncSession, template_id: int) -> None:
        await self.get(db=db, template_id=template_id)
        await learning_template_dao.delete_model(db, template_id)

    async def get_stages(
        self,
        *,
        db: AsyncSession,
        template_id: int,
    ) -> list[GetLearningPlanTemplateStageDetail]:
        await self.get(db=db, template_id=template_id)
        stages = await learning_template_stage_dao.list_by_template(db, template_id)
        return [GetLearningPlanTemplateStageDetail.model_validate(item) for item in stages]

    async def create_stage(
        self,
        *,
        db: AsyncSession,
        obj: CreateLearningPlanTemplateStageParam,
    ) -> GetLearningPlanTemplateStageDetail:
        template = await self.get(db=db, template_id=obj.template_id)
        self._validate_stage_range(template=template, start_day=obj.start_day, end_day=obj.end_day)
        stage = LearningPlanTemplateStage(**obj.model_dump(mode='python'))
        db.add(stage)
        await db.flush()
        await db.refresh(stage)
        return GetLearningPlanTemplateStageDetail.model_validate(stage)

    async def update_stage(
        self,
        *,
        db: AsyncSession,
        stage_id: int,
        obj: UpdateLearningPlanTemplateStageParam,
    ) -> GetLearningPlanTemplateStageDetail:
        stage = await self._get_stage(db=db, stage_id=stage_id)
        template = await self.get(db=db, template_id=stage.template_id)
        fields = obj.model_dump(mode='python', exclude_unset=True)
        start_day = fields.get('start_day', stage.start_day)
        end_day = fields.get('end_day', stage.end_day)
        self._validate_stage_range(template=template, start_day=start_day, end_day=end_day)
        if fields:
            await learning_template_stage_dao.update_model(db, stage_id, fields)
        refreshed = await self._get_stage(db=db, stage_id=stage_id)
        return GetLearningPlanTemplateStageDetail.model_validate(refreshed)

    async def delete_stage(self, *, db: AsyncSession, stage_id: int) -> None:
        stage = await self._get_stage(db=db, stage_id=stage_id)
        await db.execute(
            update(LearningPlanTemplateTask)
            .where(LearningPlanTemplateTask.stage_id == stage.id)
            .values(stage_id=None)
        )
        await learning_template_stage_dao.delete_model(db, stage_id)

    async def get_tasks(
        self,
        *,
        db: AsyncSession,
        template_id: int,
    ) -> list[GetLearningPlanTemplateTaskDetail]:
        await self.get(db=db, template_id=template_id)
        tasks = await learning_template_task_dao.list_by_template(db, template_id)
        return [await self._build_task_detail(db=db, task=item) for item in tasks]

    async def create_task(
        self,
        *,
        db: AsyncSession,
        obj: CreateLearningPlanTemplateTaskParam,
    ) -> GetLearningPlanTemplateTaskDetail:
        template = await self.get(db=db, template_id=obj.template_id)
        await self._validate_task(
            db=db,
            template=template,
            stage_id=obj.stage_id,
            relative_day=obj.relative_day,
            data=obj.model_dump(mode='python'),
            knowledge_points=[item.model_dump(mode='python') for item in obj.knowledge_points],
        )
        data = obj.model_dump(mode='python', exclude={'knowledge_points', 'goals'})
        task = LearningPlanTemplateTask(**data)
        db.add(task)
        await db.flush()
        await learning_template_task_dao.replace_relations(
            db,
            task_id=task.id,
            knowledge_points=[item.model_dump(mode='python') for item in obj.knowledge_points],
            goals=[item.model_dump(mode='python') for item in obj.goals],
        )
        await db.refresh(task)
        return await self._build_task_detail(db=db, task=task)

    async def update_task(
        self,
        *,
        db: AsyncSession,
        task_id: int,
        obj: UpdateLearningPlanTemplateTaskParam,
    ) -> GetLearningPlanTemplateTaskDetail:
        task = await self._get_task(db=db, task_id=task_id)
        template = await self.get(db=db, template_id=task.template_id)
        fields = obj.model_dump(mode='python', exclude_unset=True)
        knowledge_points = fields.pop('knowledge_points', None) if 'knowledge_points' in fields else None
        goals = fields.pop('goals', None) if 'goals' in fields else None
        merged = {
            'resource_type': fields.get('resource_type', task.resource_type),
            'resource_id': fields.get('resource_id', task.resource_id),
            'resource_key': fields.get('resource_key', task.resource_key),
            'resource_version_id': fields.get('resource_version_id', task.resource_version_id),
            'resource_config': fields.get('resource_config', task.resource_config),
        }
        await self._validate_task(
            db=db,
            template=template,
            stage_id=fields.get('stage_id', task.stage_id),
            relative_day=fields.get('relative_day', task.relative_day),
            data=merged,
            knowledge_points=knowledge_points,
        )
        if fields:
            await learning_template_task_dao.update_model(db, task_id, fields)
        await learning_template_task_dao.replace_relations(
            db,
            task_id=task_id,
            knowledge_points=knowledge_points,
            goals=goals,
        )
        return await self._build_task_detail(db=db, task=await self._get_task(db=db, task_id=task_id))

    async def delete_task(self, *, db: AsyncSession, task_id: int) -> None:
        await self._get_task(db=db, task_id=task_id)
        await learning_template_task_dao.delete_model(db, task_id)

    async def instantiate(
        self,
        *,
        db: AsyncSession,
        template_id: int,
        obj: InstantiateLearningPlanParam,
        created_by: int,
    ) -> GetLearningPlanDetail:
        template = await self.get(db=db, template_id=template_id)
        if template.status == LearningTemplateStatus.archived.value:
            raise errors.RequestError(msg='已归档模板不能生成计划')
        await self._ensure_user(db=db, user_id=obj.user_id)
        if obj.delivery_id is not None:
            delivery = await learning_delivery_dao.get(db, obj.delivery_id)
            if delivery is None:
                raise errors.NotFoundError(msg='交付单不存在')
            if delivery.user_id is not None and delivery.user_id != obj.user_id:
                raise errors.RequestError(msg='交付单用户与计划用户不一致')
            exists_result = await db.execute(
                select(LearningPlan.id).where(
                    LearningPlan.delivery_id == obj.delivery_id,
                    LearningPlan.deleted == 0,
                )
            )
            if exists_result.scalar_one_or_none() is not None:
                raise errors.ConflictError(msg='该交付单已经生成过计划')

        template_stages = await learning_template_stage_dao.list_by_template(db, template.id)

        plan = LearningPlan(
            user_id=obj.user_id,
            title=obj.title or template.name,
            start_date=obj.start_date,
            end_date=obj.start_date + timedelta(days=template.duration_days - 1),
            source_type=LearningPlanSource.admin_custom.value,
            status=LearningPlanStatus.draft.value,
            delivery_id=obj.delivery_id,
            template_id=template.id,
            description=obj.description or template.description,
            settings={
                'template_code': template.code,
                'template_version': template.version,
                'default_daily_minutes': template.default_daily_minutes,
                'template_stages': [
                    {
                        'name': item.name,
                        'start_day': item.start_day,
                        'end_day': item.end_day,
                        'order_index': item.order_index,
                        'description': item.description,
                    }
                    for item in template_stages
                ],
            },
            created_by=created_by,
        )
        db.add(plan)
        await db.flush()

        template_tasks = await learning_template_task_dao.list_by_template(db, template.id)
        for template_task in template_tasks:
            task = LearningTask(
                plan_id=plan.id,
                user_id=obj.user_id,
                plan_date=obj.start_date + timedelta(days=template_task.relative_day - 1),
                title=template_task.title,
                order_index=template_task.order_index,
                action_type=template_task.action_type,
                resource_type=template_task.resource_type,
                resource_id=template_task.resource_id,
                resource_key=template_task.resource_key,
                resource_version_id=template_task.resource_version_id,
                resource_config=template_task.resource_config,
                expected_minutes=template_task.expected_minutes,
                delivery_id=obj.delivery_id,
                description=template_task.description,
                created_by=created_by,
            )
            db.add(task)
            await db.flush()
            await self._copy_task_relations(db=db, template_task_id=template_task.id, task_id=task.id)

        from backend.app.learning.service.plan_service import learning_plan_service

        return await learning_plan_service.get_detail(db=db, plan_id=plan.id)

    async def _build_template_detail(
        self,
        *,
        db: AsyncSession,
        template: LearningPlanTemplate,
    ) -> GetLearningPlanTemplateDetail:
        count_result = await db.execute(
            select(
                select(func.count(LearningPlanTemplateStage.id))
                .where(
                    LearningPlanTemplateStage.template_id == template.id,
                    LearningPlanTemplateStage.deleted == 0,
                )
                .scalar_subquery(),
                select(func.count(LearningPlanTemplateTask.id))
                .where(
                    LearningPlanTemplateTask.template_id == template.id,
                    LearningPlanTemplateTask.deleted == 0,
                )
                .scalar_subquery(),
            )
        )
        stage_count, task_count = count_result.one()
        detail = GetLearningPlanTemplateDetail.model_validate(template)
        detail.stage_count = int(stage_count or 0)
        detail.task_count = int(task_count or 0)
        return detail

    async def _build_task_detail(
        self,
        *,
        db: AsyncSession,
        task: LearningPlanTemplateTask,
    ) -> GetLearningPlanTemplateTaskDetail:
        stage_name = None
        if task.stage_id is not None:
            stage_result = await db.execute(
                select(LearningPlanTemplateStage.name).where(
                    LearningPlanTemplateStage.id == task.stage_id,
                    LearningPlanTemplateStage.deleted == 0,
                )
            )
            stage_name = stage_result.scalar_one_or_none()
        knowledge_result = await db.execute(
            select(
                LearningPlanTemplateTaskKnowledgePoint,
                QbKnowledgePoint.code,
                QbKnowledgePoint.name,
                QbKnowledgePoint.path,
                QbKnowledgeSystem.name,
            )
            .join(
                QbKnowledgePoint,
                QbKnowledgePoint.id == LearningPlanTemplateTaskKnowledgePoint.knowledge_point_id,
            )
            .join(QbKnowledgeSystem, QbKnowledgeSystem.id == LearningPlanTemplateTaskKnowledgePoint.knowledge_system_id)
            .where(
                LearningPlanTemplateTaskKnowledgePoint.template_task_id == task.id,
                LearningPlanTemplateTaskKnowledgePoint.deleted == 0,
            )
            .order_by(
                LearningPlanTemplateTaskKnowledgePoint.role.asc(),
                LearningPlanTemplateTaskKnowledgePoint.id.asc(),
            )
        )
        knowledge_points = [
            GetLearningPlanTemplateTaskKnowledgePointDetail(
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
            for link, point_code, point_name, point_path, system_name in knowledge_result.all()
        ]
        goal_result = await db.execute(
            select(LearningPlanTemplateTaskGoal)
            .where(
                LearningPlanTemplateTaskGoal.template_task_id == task.id,
                LearningPlanTemplateTaskGoal.deleted == 0,
            )
            .order_by(LearningPlanTemplateTaskGoal.id.asc())
        )
        detail = GetLearningPlanTemplateTaskDetail.model_validate(task)
        detail.stage_name = stage_name
        detail.knowledge_points = knowledge_points
        detail.goals = [
            GetLearningPlanTemplateTaskGoalDetail.model_validate(item) for item in goal_result.scalars().all()
        ]
        return detail

    async def _validate_task(
        self,
        *,
        db: AsyncSession,
        template: LearningPlanTemplate,
        stage_id: int | None,
        relative_day: int,
        data: dict,
        knowledge_points: list[dict] | None,
    ) -> None:
        if relative_day > template.duration_days:
            raise errors.RequestError(msg=f'任务天数不能超过模板周期 {template.duration_days} 天')
        if stage_id is not None:
            stage = await self._get_stage(db=db, stage_id=stage_id)
            if stage.template_id != template.id:
                raise errors.RequestError(msg='阶段不属于当前模板')
            if not stage.start_day <= relative_day <= stage.end_day:
                raise errors.RequestError(msg='任务天数不在所选阶段范围内')
        await self._validate_resource(db=db, data=data)
        if knowledge_points is not None:
            await self._validate_knowledge_points(db=db, items=knowledge_points)

    @staticmethod
    async def _validate_resource(*, db: AsyncSession, data: dict) -> None:
        resource_type = str(data.get('resource_type') or 'none')
        resource_id = data.get('resource_id')
        resource_key = data.get('resource_key')
        version_id = data.get('resource_version_id')
        if resource_type == 'content':
            await LearningTemplateService._validate_content_resource(db=db, resource_id=resource_id)
        elif resource_type == 'question_bank':
            if resource_id is None:
                raise errors.RequestError(msg='刷题任务必须选择题库')
            result = await db.execute(
                select(QbBank.id, QbBank.current_revision_id).where(
                    QbBank.id == resource_id,
                    QbBank.deleted == 0,
                )
            )
            bank = result.one_or_none()
            if bank is None:
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
            revision_id = version_id or bank.current_revision_id
            if revision_id is None:
                raise errors.RequestError(msg='所选题库没有可用的当前版本')
            await LearningTemplateService._validate_question_bank_config(
                db=db,
                revision_id=revision_id,
                config=data.get('resource_config') or {},
            )
        elif resource_type == 'ability' and not resource_key:
            raise errors.RequestError(msg='能力练习必须填写能力标识')

    @staticmethod
    async def _validate_content_resource(*, db: AsyncSession, resource_id: int | None) -> None:
        if resource_id is None:
            raise errors.RequestError(msg='内容任务必须选择内容资源')
        result = await db.execute(select(Content.id).where(Content.id == resource_id, Content.deleted == 0))
        if result.scalar_one_or_none() is None:
            raise errors.NotFoundError(msg='内容资源不存在')

    @staticmethod
    async def _validate_question_bank_config(*, db: AsyncSession, revision_id: int, config: dict) -> None:
        if not isinstance(config, dict):
            raise errors.RequestError(msg='题库执行配置格式错误')
        default_mode = 'manual' if config.get('source_type') == 'custom' else 'system'
        selection_mode = config.get('selection_mode', default_mode)
        if selection_mode not in {'manual', 'system'}:
            raise errors.RequestError(msg='题库选题方式无效')

        question_type = config.get('question_type')
        valid_question_types = {
            'single_choice',
            'multiple_choice',
            'true_false',
            'fill_blank',
            'short_answer',
            'composite',
            'interactive',
        }
        if question_type is not None and question_type not in valid_question_types:
            raise errors.RequestError(msg='题型筛选条件无效')
        difficulty = config.get('difficulty')
        if difficulty is not None and (
            isinstance(difficulty, bool) or not isinstance(difficulty, int) or not 1 <= difficulty <= 5
        ):
            raise errors.RequestError(msg='题目难度必须是 1 到 5')

        knowledge_point_ids = config.get('knowledge_point_ids') or []
        if not isinstance(knowledge_point_ids, list) or any(
            isinstance(item, bool) or not isinstance(item, int) or item <= 0 for item in knowledge_point_ids
        ):
            raise errors.RequestError(msg='知识点筛选条件格式错误')
        if selection_mode == 'manual':
            await LearningTemplateService._validate_manual_questions(
                db=db,
                revision_id=revision_id,
                question_ids=config.get('question_ids') or [],
            )
            return
        question_count = config.get('question_count', config.get('count'))
        if (
            isinstance(question_count, bool)
            or not isinstance(question_count, int)
            or not 1 <= question_count <= 500
        ):
            raise errors.RequestError(msg='系统抽题数量必须是 1 到 500')

    @staticmethod
    async def _validate_manual_questions(*, db: AsyncSession, revision_id: int, question_ids: list) -> None:
        normalized_ids = list(dict.fromkeys(question_ids))
        if not normalized_ids:
            raise errors.RequestError(msg='手动选题至少需要选择一道题')
        if len(normalized_ids) > 500 or any(
            isinstance(item, bool) or not isinstance(item, int) or item <= 0 for item in normalized_ids
        ):
            raise errors.RequestError(msg='手动选择的题目格式错误或超过 500 题')
        selected_result = await db.execute(
            select(func.count(QbBankItem.id)).where(
                QbBankItem.bank_revision_id == revision_id,
                QbBankItem.question_id.in_(normalized_ids),
                QbBankItem.is_active.is_(True),
                QbBankItem.deleted == 0,
            )
        )
        if int(selected_result.scalar() or 0) != len(normalized_ids):
            raise errors.RequestError(msg='手动选择的题目不属于当前题库版本')

    @staticmethod
    async def _validate_knowledge_points(*, db: AsyncSession, items: list[dict]) -> None:
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
    async def _copy_task_relations(*, db: AsyncSession, template_task_id: int, task_id: int) -> None:
        knowledge_result = await db.execute(
            select(LearningPlanTemplateTaskKnowledgePoint).where(
                LearningPlanTemplateTaskKnowledgePoint.template_task_id == template_task_id,
                LearningPlanTemplateTaskKnowledgePoint.deleted == 0,
            )
        )
        db.add_all(
            [
                LearningTaskKnowledgePoint(
                    task_id=task_id,
                    knowledge_system_id=item.knowledge_system_id,
                    knowledge_point_id=item.knowledge_point_id,
                    role=item.role,
                    include_descendants=item.include_descendants,
                    weight=item.weight,
                )
                for item in knowledge_result.scalars().all()
            ]
        )
        goal_result = await db.execute(
            select(LearningPlanTemplateTaskGoal).where(
                LearningPlanTemplateTaskGoal.template_task_id == template_task_id,
                LearningPlanTemplateTaskGoal.deleted == 0,
            )
        )
        db.add_all(
            [
                LearningTaskGoal(
                    task_id=task_id,
                    metric=item.metric,
                    operator=item.operator,
                    target_value=item.target_value,
                    unit=item.unit,
                    is_required=item.is_required,
                    config=item.config,
                )
                for item in goal_result.scalars().all()
            ]
        )
        await db.flush()

    async def _get_stage(self, *, db: AsyncSession, stage_id: int) -> LearningPlanTemplateStage:
        stage = await learning_template_stage_dao.get(db, stage_id)
        if stage is None:
            raise errors.NotFoundError(msg='模板阶段不存在')
        return stage

    async def _get_task(self, *, db: AsyncSession, task_id: int) -> LearningPlanTemplateTask:
        task = await learning_template_task_dao.get(db, task_id)
        if task is None:
            raise errors.NotFoundError(msg='模板任务不存在')
        return task

    @staticmethod
    def _validate_stage_range(*, template: LearningPlanTemplate, start_day: int, end_day: int) -> None:
        if end_day < start_day:
            raise errors.RequestError(msg='阶段结束天数不能早于开始天数')
        if end_day > template.duration_days:
            raise errors.RequestError(msg=f'阶段结束天数不能超过模板周期 {template.duration_days} 天')

    @staticmethod
    async def _ensure_user(*, db: AsyncSession, user_id: int) -> None:
        result = await db.execute(select(User.id).where(User.id == user_id, User.deleted == 0))
        if result.scalar_one_or_none() is None:
            raise errors.NotFoundError(msg='用户不存在')

    @staticmethod
    async def _ensure_code_unique(
        *,
        db: AsyncSession,
        code: str,
        exclude_id: int | None = None,
    ) -> None:
        stmt = select(LearningPlanTemplate.id).where(
            LearningPlanTemplate.code == code,
            LearningPlanTemplate.deleted == 0,
        )
        if exclude_id is not None:
            stmt = stmt.where(LearningPlanTemplate.id != exclude_id)
        result = await db.execute(stmt)
        if result.scalar_one_or_none() is not None:
            raise errors.ConflictError(msg='模板编码已存在')


learning_template_service = LearningTemplateService()
