from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request

from backend.app.learning.schema.plan import (
    CreateLearningDeliveryParam,
    CreateLearningPlanParam,
    GetLearningDeliveryDetail,
    GetLearningPlanDetail,
    UpdateLearningDeliveryParam,
    UpdateLearningPlanParam,
)
from backend.app.learning.schema.task import (
    CreateLearningTaskParam,
    GetLearningTaskDetail,
    UpdateLearningTaskParam,
)
from backend.app.learning.schema.template import (
    CreateLearningPlanTemplateParam,
    CreateLearningPlanTemplateStageParam,
    CreateLearningPlanTemplateTaskParam,
    GetLearningPlanTemplateDetail,
    GetLearningPlanTemplateStageDetail,
    GetLearningPlanTemplateTaskDetail,
    InstantiateLearningDeliveryPlanParam,
    InstantiateLearningPlanParam,
    UpdateLearningPlanTemplateParam,
    UpdateLearningPlanTemplateStageParam,
    UpdateLearningPlanTemplateTaskParam,
)
from backend.app.learning.service import (
    learning_delivery_service,
    learning_plan_service,
    learning_task_service,
    learning_template_service,
)
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.permission import RequestPermission
from backend.common.security.rbac import DependsRBAC
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get(
    '/templates',
    summary='获取学习计划模板列表',
    dependencies=[Depends(RequestPermission('learning:template:read')), DependsRBAC],
)
async def get_learning_templates(
    db: CurrentSession,
    status: Annotated[str | None, Query(description='模板状态')] = None,
    exam_type: Annotated[str | None, Query(description='考试类型')] = None,
) -> ResponseSchemaModel[list[GetLearningPlanTemplateDetail]]:
    data = await learning_template_service.get_all(db=db, status=status, exam_type=exam_type)
    return response_base.success(data=data)


@router.get(
    '/templates/{template_id}',
    summary='获取学习计划模板详情',
    dependencies=[Depends(RequestPermission('learning:template:read')), DependsRBAC],
)
async def get_learning_template(
    db: CurrentSession,
    template_id: Annotated[int, Path(description='模板 ID')],
) -> ResponseSchemaModel[GetLearningPlanTemplateDetail]:
    return response_base.success(data=await learning_template_service.get_detail(db=db, template_id=template_id))


@router.post(
    '/templates',
    summary='创建学习计划模板',
    dependencies=[Depends(RequestPermission('learning:template:write')), DependsRBAC],
)
async def create_learning_template(
    request: Request,
    db: CurrentSessionTransaction,
    obj: CreateLearningPlanTemplateParam,
) -> ResponseSchemaModel[GetLearningPlanTemplateDetail]:
    data = await learning_template_service.create(db=db, obj=obj, created_by=request.user.id)
    return response_base.success(data=data)


@router.put(
    '/templates/{template_id}',
    summary='更新学习计划模板',
    dependencies=[Depends(RequestPermission('learning:template:write')), DependsRBAC],
)
async def update_learning_template(
    request: Request,
    db: CurrentSessionTransaction,
    obj: UpdateLearningPlanTemplateParam,
    template_id: Annotated[int, Path(description='模板 ID')],
) -> ResponseSchemaModel[GetLearningPlanTemplateDetail]:
    data = await learning_template_service.update(
        db=db,
        template_id=template_id,
        obj=obj,
        updated_by=request.user.id,
    )
    return response_base.success(data=data)


@router.delete(
    '/templates/{template_id}',
    summary='删除学习计划模板',
    dependencies=[Depends(RequestPermission('learning:template:write')), DependsRBAC],
)
async def delete_learning_template(
    db: CurrentSessionTransaction,
    template_id: Annotated[int, Path(description='模板 ID')],
) -> ResponseModel:
    await learning_template_service.delete(db=db, template_id=template_id)
    return response_base.success()


@router.get(
    '/templates/{template_id}/stages',
    summary='获取模板阶段列表',
    dependencies=[Depends(RequestPermission('learning:template:read')), DependsRBAC],
)
async def get_learning_template_stages(
    db: CurrentSession,
    template_id: Annotated[int, Path(description='模板 ID')],
) -> ResponseSchemaModel[list[GetLearningPlanTemplateStageDetail]]:
    return response_base.success(data=await learning_template_service.get_stages(db=db, template_id=template_id))


@router.post(
    '/template-stages',
    summary='创建模板阶段',
    dependencies=[Depends(RequestPermission('learning:template:write')), DependsRBAC],
)
async def create_learning_template_stage(
    db: CurrentSessionTransaction,
    obj: CreateLearningPlanTemplateStageParam,
) -> ResponseSchemaModel[GetLearningPlanTemplateStageDetail]:
    return response_base.success(data=await learning_template_service.create_stage(db=db, obj=obj))


@router.put(
    '/template-stages/{stage_id}',
    summary='更新模板阶段',
    dependencies=[Depends(RequestPermission('learning:template:write')), DependsRBAC],
)
async def update_learning_template_stage(
    db: CurrentSessionTransaction,
    obj: UpdateLearningPlanTemplateStageParam,
    stage_id: Annotated[int, Path(description='模板阶段 ID')],
) -> ResponseSchemaModel[GetLearningPlanTemplateStageDetail]:
    return response_base.success(data=await learning_template_service.update_stage(db=db, stage_id=stage_id, obj=obj))


@router.delete(
    '/template-stages/{stage_id}',
    summary='删除模板阶段',
    dependencies=[Depends(RequestPermission('learning:template:write')), DependsRBAC],
)
async def delete_learning_template_stage(
    db: CurrentSessionTransaction,
    stage_id: Annotated[int, Path(description='模板阶段 ID')],
) -> ResponseModel:
    await learning_template_service.delete_stage(db=db, stage_id=stage_id)
    return response_base.success()


@router.get(
    '/templates/{template_id}/tasks',
    summary='获取模板任务列表',
    dependencies=[Depends(RequestPermission('learning:template:read')), DependsRBAC],
)
async def get_learning_template_tasks(
    db: CurrentSession,
    template_id: Annotated[int, Path(description='模板 ID')],
) -> ResponseSchemaModel[list[GetLearningPlanTemplateTaskDetail]]:
    return response_base.success(data=await learning_template_service.get_tasks(db=db, template_id=template_id))


@router.post(
    '/template-tasks',
    summary='创建模板任务',
    dependencies=[Depends(RequestPermission('learning:template:write')), DependsRBAC],
)
async def create_learning_template_task(
    db: CurrentSessionTransaction,
    obj: CreateLearningPlanTemplateTaskParam,
) -> ResponseSchemaModel[GetLearningPlanTemplateTaskDetail]:
    return response_base.success(data=await learning_template_service.create_task(db=db, obj=obj))


@router.put(
    '/template-tasks/{task_id}',
    summary='更新模板任务',
    dependencies=[Depends(RequestPermission('learning:template:write')), DependsRBAC],
)
async def update_learning_template_task(
    db: CurrentSessionTransaction,
    obj: UpdateLearningPlanTemplateTaskParam,
    task_id: Annotated[int, Path(description='模板任务 ID')],
) -> ResponseSchemaModel[GetLearningPlanTemplateTaskDetail]:
    return response_base.success(data=await learning_template_service.update_task(db=db, task_id=task_id, obj=obj))


@router.delete(
    '/template-tasks/{task_id}',
    summary='删除模板任务',
    dependencies=[Depends(RequestPermission('learning:template:write')), DependsRBAC],
)
async def delete_learning_template_task(
    db: CurrentSessionTransaction,
    task_id: Annotated[int, Path(description='模板任务 ID')],
) -> ResponseModel:
    await learning_template_service.delete_task(db=db, task_id=task_id)
    return response_base.success()


@router.post(
    '/templates/{template_id}/instantiate',
    summary='从模板生成用户学习计划',
    dependencies=[Depends(RequestPermission('learning:plan:write')), DependsRBAC],
)
async def instantiate_learning_template(
    request: Request,
    db: CurrentSessionTransaction,
    obj: InstantiateLearningPlanParam,
    template_id: Annotated[int, Path(description='模板 ID')],
) -> ResponseSchemaModel[GetLearningPlanDetail]:
    data = await learning_template_service.instantiate(
        db=db,
        template_id=template_id,
        obj=obj,
        created_by=request.user.id,
    )
    return response_base.success(data=data)


@router.get(
    '/plans',
    summary='获取学习计划列表',
    dependencies=[Depends(RequestPermission('learning:plan:read')), DependsRBAC],
)
async def get_learning_plans(
    db: CurrentSession,
    user_id: Annotated[int | None, Query(description='用户 ID')] = None,
    status: Annotated[str | None, Query(description='计划状态')] = None,
    source_type: Annotated[str | None, Query(description='计划来源')] = None,
) -> ResponseSchemaModel[list[GetLearningPlanDetail]]:
    data = await learning_plan_service.get_all(
        db=db,
        user_id=user_id,
        status=status,
        source_type=source_type,
    )
    return response_base.success(data=data)


@router.get(
    '/plans/{plan_id}',
    summary='获取学习计划详情',
    dependencies=[Depends(RequestPermission('learning:plan:read')), DependsRBAC],
)
async def get_learning_plan(
    db: CurrentSession,
    plan_id: Annotated[int, Path(description='计划 ID')],
) -> ResponseSchemaModel[GetLearningPlanDetail]:
    return response_base.success(data=await learning_plan_service.get_detail(db=db, plan_id=plan_id))


@router.post(
    '/plans',
    summary='创建学习计划',
    dependencies=[Depends(RequestPermission('learning:plan:write')), DependsRBAC],
)
async def create_learning_plan(
    request: Request,
    db: CurrentSessionTransaction,
    obj: CreateLearningPlanParam,
) -> ResponseSchemaModel[GetLearningPlanDetail]:
    data = await learning_plan_service.create(db=db, obj=obj, created_by=request.user.id)
    return response_base.success(data=data)


@router.put(
    '/plans/{plan_id}',
    summary='更新学习计划',
    dependencies=[Depends(RequestPermission('learning:plan:write')), DependsRBAC],
)
async def update_learning_plan(
    request: Request,
    db: CurrentSessionTransaction,
    obj: UpdateLearningPlanParam,
    plan_id: Annotated[int, Path(description='计划 ID')],
) -> ResponseSchemaModel[GetLearningPlanDetail]:
    data = await learning_plan_service.update(
        db=db,
        plan_id=plan_id,
        obj=obj,
        updated_by=request.user.id,
    )
    return response_base.success(data=data)


@router.delete(
    '/plans/{plan_id}',
    summary='删除学习计划',
    dependencies=[Depends(RequestPermission('learning:plan:write')), DependsRBAC],
)
async def delete_learning_plan(
    db: CurrentSessionTransaction,
    plan_id: Annotated[int, Path(description='计划 ID')],
) -> ResponseModel:
    await learning_plan_service.delete(db=db, plan_id=plan_id)
    return response_base.success()


@router.get(
    '/plans/{plan_id}/tasks',
    summary='获取计划任务列表',
    dependencies=[Depends(RequestPermission('learning:plan:read')), DependsRBAC],
)
async def get_learning_tasks(
    db: CurrentSession,
    plan_id: Annotated[int, Path(description='计划 ID')],
) -> ResponseSchemaModel[list[GetLearningTaskDetail]]:
    return response_base.success(data=await learning_task_service.list_by_plan(db=db, plan_id=plan_id))


@router.post(
    '/tasks',
    summary='创建学习任务',
    dependencies=[Depends(RequestPermission('learning:plan:write')), DependsRBAC],
)
async def create_learning_task(
    request: Request,
    db: CurrentSessionTransaction,
    obj: CreateLearningTaskParam,
) -> ResponseSchemaModel[GetLearningTaskDetail]:
    data = await learning_task_service.create(db=db, obj=obj, created_by=request.user.id)
    return response_base.success(data=data)


@router.put(
    '/tasks/{task_id}',
    summary='更新学习任务',
    dependencies=[Depends(RequestPermission('learning:plan:write')), DependsRBAC],
)
async def update_learning_task(
    request: Request,
    db: CurrentSessionTransaction,
    obj: UpdateLearningTaskParam,
    task_id: Annotated[int, Path(description='任务 ID')],
) -> ResponseSchemaModel[GetLearningTaskDetail]:
    data = await learning_task_service.update(
        db=db,
        task_id=task_id,
        obj=obj,
        updated_by=request.user.id,
    )
    return response_base.success(data=data)


@router.delete(
    '/tasks/{task_id}',
    summary='删除学习任务',
    dependencies=[Depends(RequestPermission('learning:plan:write')), DependsRBAC],
)
async def delete_learning_task(
    db: CurrentSessionTransaction,
    task_id: Annotated[int, Path(description='任务 ID')],
) -> ResponseModel:
    await learning_task_service.delete(db=db, task_id=task_id)
    return response_base.success()


@router.get(
    '/deliveries',
    summary='获取计划交付单列表',
    dependencies=[Depends(RequestPermission('learning:delivery:read')), DependsRBAC],
)
async def get_learning_deliveries(
    db: CurrentSession,
    user_id: Annotated[int | None, Query(description='用户 ID')] = None,
    status: Annotated[str | None, Query(description='交付状态')] = None,
    source_channel: Annotated[str | None, Query(description='来源渠道')] = None,
) -> ResponseSchemaModel[list[GetLearningDeliveryDetail]]:
    data = await learning_delivery_service.get_all(
        db=db,
        user_id=user_id,
        status=status,
        source_channel=source_channel,
    )
    return response_base.success(data=data)


@router.get(
    '/deliveries/{delivery_id}',
    summary='获取计划交付单详情',
    dependencies=[Depends(RequestPermission('learning:delivery:read')), DependsRBAC],
)
async def get_learning_delivery(
    db: CurrentSession,
    delivery_id: Annotated[int, Path(description='交付单 ID')],
) -> ResponseSchemaModel[GetLearningDeliveryDetail]:
    return response_base.success(data=await learning_delivery_service.get_detail(db=db, delivery_id=delivery_id))


@router.post(
    '/deliveries',
    summary='创建计划交付单',
    dependencies=[Depends(RequestPermission('learning:delivery:write')), DependsRBAC],
)
async def create_learning_delivery(
    request: Request,
    db: CurrentSessionTransaction,
    obj: CreateLearningDeliveryParam,
) -> ResponseSchemaModel[GetLearningDeliveryDetail]:
    data = await learning_delivery_service.create(db=db, obj=obj, created_by=request.user.id)
    return response_base.success(data=data)


@router.put(
    '/deliveries/{delivery_id}',
    summary='更新计划交付单',
    dependencies=[Depends(RequestPermission('learning:delivery:write')), DependsRBAC],
)
async def update_learning_delivery(
    request: Request,
    db: CurrentSessionTransaction,
    obj: UpdateLearningDeliveryParam,
    delivery_id: Annotated[int, Path(description='交付单 ID')],
) -> ResponseSchemaModel[GetLearningDeliveryDetail]:
    data = await learning_delivery_service.update(
        db=db,
        delivery_id=delivery_id,
        obj=obj,
        updated_by=request.user.id,
    )
    return response_base.success(data=data)


@router.post(
    '/deliveries/{delivery_id}/publish',
    summary='发布计划交付单',
    dependencies=[Depends(RequestPermission('learning:delivery:publish')), DependsRBAC],
)
async def publish_learning_delivery(
    request: Request,
    db: CurrentSessionTransaction,
    delivery_id: Annotated[int, Path(description='交付单 ID')],
) -> ResponseSchemaModel[GetLearningDeliveryDetail]:
    data = await learning_delivery_service.publish(
        db=db,
        delivery_id=delivery_id,
        delivered_by=request.user.id,
    )
    return response_base.success(data=data)


@router.post(
    '/deliveries/{delivery_id}/instantiate',
    summary='从模板生成交付计划',
    dependencies=[Depends(RequestPermission('learning:delivery:write')), DependsRBAC],
)
async def instantiate_learning_delivery_plan(
    request: Request,
    db: CurrentSessionTransaction,
    obj: InstantiateLearningDeliveryPlanParam,
    delivery_id: Annotated[int, Path(description='交付单 ID')],
) -> ResponseSchemaModel[GetLearningPlanDetail]:
    delivery = await learning_delivery_service.get(db=db, delivery_id=delivery_id)
    if delivery.user_id is None:
        from backend.common.exception import errors

        raise errors.RequestError(msg='生成计划前必须绑定接收用户')
    data = await learning_template_service.instantiate(
        db=db,
        template_id=obj.template_id,
        obj=InstantiateLearningPlanParam(
            user_id=delivery.user_id,
            start_date=obj.start_date,
            title=obj.title,
            delivery_id=delivery_id,
            description=obj.description,
        ),
        created_by=request.user.id,
    )
    return response_base.success(data=data)
