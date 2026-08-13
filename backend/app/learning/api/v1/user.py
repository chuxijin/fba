from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Path, Query, Request

from backend.app.learning.crud import learning_plan_dao, learning_task_dao
from backend.app.learning.enums import LearningPlanSource, LearningTaskStatus
from backend.app.learning.schema.execution import (
    AttachLearningFocusTaskParam,
    CompleteLearningTaskParam,
    FinishLearningFocusParam,
    GetLearningCompletionRecordDetail,
    GetLearningFocusSessionDetail,
    StartLearningFocusParam,
)
from backend.app.learning.schema.plan import (
    CreateLearningPlanParam,
    CreateMyLearningPlanParam,
    GetLearningPlanDetail,
    UpdateLearningPlanParam,
)
from backend.app.learning.schema.statistics import GetLearningSummaryStatistic
from backend.app.learning.schema.task import (
    CreateLearningTaskParam,
    GetLearningTaskDetail,
    StartLearningTaskResult,
    UpdateLearningTaskParam,
)
from backend.app.learning.service import (
    learning_execution_service,
    learning_launch_service,
    learning_plan_service,
    learning_statistics_service,
    learning_task_service,
)
from backend.common.exception import errors
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction
from backend.utils.timezone import timezone

router = APIRouter(dependencies=[DependsJwtAuth])


@router.get('/statistics/summary', summary='获取学习专注汇总统计')
async def get_learning_statistics_summary(
    request: Request,
    db: CurrentSession,
    start_date: Annotated[date, Query(description='开始日期')],
    end_date: Annotated[date, Query(description='结束日期')],
    granularity: Annotated[str, Query(description='统计粒度(day 或 month)')] = 'day',
    distribution: Annotated[
        Literal['task_type', 'knowledge_point'],
        Query(description='分布维度(task_type 或 knowledge_point)'),
    ] = 'task_type',
) -> ResponseSchemaModel[GetLearningSummaryStatistic]:
    data = await learning_statistics_service.get_summary(
        db=db,
        user_id=request.user.id,
        start_date=start_date,
        end_date=end_date,
        granularity=granularity,
        distribution=distribution,
    )
    return response_base.success(data=data)


@router.get('/plans', summary='获取我的学习计划')
async def get_my_learning_plans(
    request: Request,
    db: CurrentSession,
) -> ResponseSchemaModel[list[GetLearningPlanDetail]]:
    data = await learning_plan_service.get_all(db=db, user_id=request.user.id)
    return response_base.success(data=data)


@router.post('/plans', summary='创建我的学习计划')
async def create_my_learning_plan(
    request: Request,
    db: CurrentSessionTransaction,
    obj: CreateMyLearningPlanParam,
) -> ResponseSchemaModel[GetLearningPlanDetail]:
    create_obj = CreateLearningPlanParam(
        **obj.model_dump(mode='python', exclude={'source_type'}),
        user_id=request.user.id,
        source_type=LearningPlanSource.user,
        delivery_id=None,
    )
    data = await learning_plan_service.create(db=db, obj=create_obj, created_by=request.user.id)
    return response_base.success(data=data)


@router.put('/plans/{plan_id}', summary='更新我的学习计划')
async def update_my_learning_plan(
    request: Request,
    db: CurrentSessionTransaction,
    obj: UpdateLearningPlanParam,
    plan_id: Annotated[int, Path(description='计划 ID')],
) -> ResponseSchemaModel[GetLearningPlanDetail]:
    plan = await learning_plan_service.get(db=db, plan_id=plan_id)
    if plan.user_id != request.user.id:
        raise errors.ForbiddenError(msg='无权操作该学习计划')
    safe_obj = UpdateLearningPlanParam.model_validate(
        obj.model_dump(mode='python', exclude_unset=True, exclude={'source_type', 'delivery_id'})
    )
    data = await learning_plan_service.update(
        db=db,
        plan_id=plan_id,
        obj=safe_obj,
        updated_by=request.user.id,
    )
    return response_base.success(data=data)


@router.get('/plans/{plan_id}/tasks', summary='获取我的计划任务')
async def get_my_learning_tasks(
    request: Request,
    db: CurrentSession,
    plan_id: Annotated[int, Path(description='计划 ID')],
) -> ResponseSchemaModel[list[GetLearningTaskDetail]]:
    plan = await learning_plan_service.get(db=db, plan_id=plan_id)
    if plan.user_id != request.user.id:
        raise errors.ForbiddenError(msg='无权查看该学习计划')
    return response_base.success(data=await learning_task_service.list_by_plan(db=db, plan_id=plan_id))


@router.get('/tasks/today', summary='获取今日学习任务')
async def get_today_learning_tasks(
    request: Request,
    db: CurrentSession,
) -> ResponseSchemaModel[list[GetLearningTaskDetail]]:
    tasks = await learning_task_dao.list_by_user_date(db, request.user.id, timezone.now().date())
    return response_base.success(
        data=[await learning_task_service.get_detail(db=db, task_id=task.id) for task in tasks]
    )


@router.post('/tasks', summary='创建我的学习任务')
async def create_my_learning_task(
    request: Request,
    db: CurrentSessionTransaction,
    obj: CreateLearningTaskParam,
) -> ResponseSchemaModel[GetLearningTaskDetail]:
    plan = await learning_plan_dao.get(db, obj.plan_id)
    if plan is None or plan.user_id != request.user.id:
        raise errors.ForbiddenError(msg='无权向该计划添加任务')
    obj.delivery_id = None
    return response_base.success(data=await learning_task_service.create(db=db, obj=obj, created_by=request.user.id))


@router.put('/tasks/{task_id}', summary='更新我的学习任务')
async def update_my_learning_task(
    request: Request,
    db: CurrentSessionTransaction,
    obj: UpdateLearningTaskParam,
    task_id: Annotated[int, Path(description='任务 ID')],
) -> ResponseSchemaModel[GetLearningTaskDetail]:
    task = await learning_task_service.get(db=db, task_id=task_id)
    if task.user_id != request.user.id:
        raise errors.ForbiddenError(msg='无权操作该学习任务')
    if obj.status == LearningTaskStatus.completed:
        raise errors.RequestError(msg='请通过任务完成接口提交完成指标')
    safe_obj = UpdateLearningTaskParam.model_validate(
        obj.model_dump(mode='python', exclude_unset=True, exclude={'delivery_id'})
    )
    return response_base.success(
        data=await learning_task_service.update(
            db=db,
            task_id=task_id,
            obj=safe_obj,
            updated_by=request.user.id,
        )
    )


@router.delete('/tasks/{task_id}', summary='删除我的学习任务')
async def delete_my_learning_task(
    request: Request,
    db: CurrentSessionTransaction,
    task_id: Annotated[int, Path(description='任务 ID')],
) -> ResponseSchemaModel[None]:
    task = await learning_task_service.get(db=db, task_id=task_id)
    if task.user_id != request.user.id:
        raise errors.ForbiddenError(msg='无权操作该学习任务')
    if task.delivery_id is not None:
        raise errors.RequestError(msg='官方发放的任务不能删除')
    await learning_task_service.delete(db=db, task_id=task_id)
    return response_base.success(data=None)


@router.post('/tasks/{task_id}/start', summary='启动学习任务')
async def start_my_learning_task(
    request: Request,
    db: CurrentSessionTransaction,
    task_id: Annotated[int, Path(description='任务 ID')],
) -> ResponseSchemaModel[StartLearningTaskResult]:
    return response_base.success(
        data=await learning_launch_service.start_task(
            db=db,
            task_id=task_id,
            user_id=request.user.id,
        )
    )


@router.post('/tasks/{task_id}/focus/start', summary='开始任务专注')
async def start_learning_focus(
    request: Request,
    db: CurrentSessionTransaction,
    obj: StartLearningFocusParam,
    task_id: Annotated[int, Path(description='任务 ID')],
) -> ResponseSchemaModel[GetLearningFocusSessionDetail]:
    return response_base.success(
        data=await learning_execution_service.start_focus(
            db=db,
            task_id=task_id,
            user_id=request.user.id,
            obj=obj,
        )
    )


@router.post('/focus/start', summary='开始自由专注')
async def start_free_learning_focus(
    request: Request,
    db: CurrentSessionTransaction,
    obj: StartLearningFocusParam,
) -> ResponseSchemaModel[GetLearningFocusSessionDetail]:
    """不关联任务的专注，时长同样计入专注统计。"""
    return response_base.success(
        data=await learning_execution_service.start_focus(
            db=db,
            task_id=None,
            user_id=request.user.id,
            obj=obj,
        )
    )


@router.post('/focus/{session_id}/attach-task', summary='关联专注任务')
async def attach_learning_focus_task(
    request: Request,
    db: CurrentSessionTransaction,
    obj: AttachLearningFocusTaskParam,
    session_id: Annotated[int, Path(description='专注记录 ID')],
) -> ResponseSchemaModel[GetLearningFocusSessionDetail]:
    return response_base.success(
        data=await learning_execution_service.attach_task(
            db=db,
            session_id=session_id,
            user_id=request.user.id,
            task_id=obj.task_id,
        )
    )


@router.get('/focus/current', summary='获取当前学习专注')
async def get_current_learning_focus(
    request: Request,
    db: CurrentSession,
) -> ResponseSchemaModel[GetLearningFocusSessionDetail | None]:
    return response_base.success(
        data=await learning_execution_service.get_current_focus(
            db=db,
            user_id=request.user.id,
        )
    )


@router.post('/focus/{session_id}/pause', summary='暂停学习专注')
async def pause_learning_focus(
    request: Request,
    db: CurrentSessionTransaction,
    session_id: Annotated[int, Path(description='专注记录 ID')],
) -> ResponseSchemaModel[GetLearningFocusSessionDetail]:
    return response_base.success(
        data=await learning_execution_service.pause_focus(
            db=db,
            session_id=session_id,
            user_id=request.user.id,
        )
    )


@router.post('/focus/{session_id}/resume', summary='继续学习专注')
async def resume_learning_focus(
    request: Request,
    db: CurrentSessionTransaction,
    session_id: Annotated[int, Path(description='专注记录 ID')],
) -> ResponseSchemaModel[GetLearningFocusSessionDetail]:
    return response_base.success(
        data=await learning_execution_service.resume_focus(
            db=db,
            session_id=session_id,
            user_id=request.user.id,
        )
    )


@router.post('/focus/{session_id}/finish', summary='结束学习专注')
async def finish_learning_focus(
    request: Request,
    db: CurrentSessionTransaction,
    obj: FinishLearningFocusParam,
    session_id: Annotated[int, Path(description='专注记录 ID')],
) -> ResponseSchemaModel[GetLearningFocusSessionDetail]:
    return response_base.success(
        data=await learning_execution_service.finish_focus(
            db=db,
            session_id=session_id,
            user_id=request.user.id,
            obj=obj,
        )
    )


@router.post('/focus/{session_id}/cancel', summary='取消学习专注')
async def cancel_learning_focus(
    request: Request,
    db: CurrentSessionTransaction,
    session_id: Annotated[int, Path(description='专注记录 ID')],
) -> ResponseSchemaModel[GetLearningFocusSessionDetail]:
    return response_base.success(
        data=await learning_execution_service.cancel_focus(
            db=db,
            session_id=session_id,
            user_id=request.user.id,
        )
    )


@router.post('/tasks/{task_id}/complete', summary='提交学习任务完成')
async def complete_learning_task(
    request: Request,
    db: CurrentSessionTransaction,
    obj: CompleteLearningTaskParam,
    task_id: Annotated[int, Path(description='任务 ID')],
) -> ResponseSchemaModel[GetLearningCompletionRecordDetail]:
    return response_base.success(
        data=await learning_execution_service.complete_task(
            db=db,
            task_id=task_id,
            user_id=request.user.id,
            obj=obj,
        )
    )
