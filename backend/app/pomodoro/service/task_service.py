#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import date, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.pomodoro.crud.crud_task import pomodoro_task_dao
from backend.app.pomodoro.enums import PomodoroRepeatType, PomodoroTaskStatus
from backend.app.pomodoro.model.task import PomodoroTask
from backend.app.pomodoro.schema.task import (
    CreatePomodoroTaskInternal,
    CreatePomodoroTaskParam,
    GetPomodoroRepeatTaskGenerateResult,
    GetPomodoroTaskListItem,
    UpdatePomodoroTaskParam,
)
from backend.common.exception import errors
from backend.common.pagination import paging_data
from backend.utils.timezone import timezone


class PomodoroTaskService:
    """番茄任务服务类"""

    @staticmethod
    async def get(*, db: AsyncSession, user_id: int, task_id: int) -> PomodoroTask:
        """
        获取用户任务

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param task_id: 任务 ID
        :return:
        """
        task = await pomodoro_task_dao.get_by_user(db, user_id, task_id)
        if not task:
            raise errors.NotFoundError(msg='任务不存在或无权访问')
        return task

    @staticmethod
    async def get_list(
        *,
        db: AsyncSession,
        user_id: int,
        status: PomodoroTaskStatus | None = None,
        keyword: str | None = None,
    ) -> dict:
        """
        获取任务分页列表

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param status: 任务状态
        :param keyword: 标题关键词
        :return:
        """
        stmt = await pomodoro_task_dao.get_select_by_user(user_id=user_id, status=status, keyword=keyword)
        return await paging_data(db, stmt, schema_cls=GetPomodoroTaskListItem)

    @staticmethod
    async def create(*, db: AsyncSession, user_id: int, obj: CreatePomodoroTaskParam) -> PomodoroTask:
        """
        创建任务

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param obj: 创建参数
        :return:
        """
        data = CreatePomodoroTaskInternal(user_id=user_id, **obj.model_dump(mode='python'))
        task = await pomodoro_task_dao.create_model(db, data, commit=False)
        await db.flush()
        await db.refresh(task)
        return task

    @staticmethod
    async def update(
        *,
        db: AsyncSession,
        user_id: int,
        task_id: int,
        obj: UpdatePomodoroTaskParam,
    ) -> PomodoroTask:
        """
        更新任务

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param task_id: 任务 ID
        :param obj: 更新参数
        :return:
        """
        task = await PomodoroTaskService.get(db=db, user_id=user_id, task_id=task_id)
        update_data = obj.model_dump(mode='python', exclude_unset=True)
        if not update_data:
            return task

        if update_data.get('status') == PomodoroTaskStatus.completed.value:
            update_data['completed_at'] = timezone.now()
        elif update_data.get('status') in {PomodoroTaskStatus.pending.value, PomodoroTaskStatus.doing.value}:
            update_data['completed_at'] = None

        await pomodoro_task_dao.update_model(db, task.id, update_data, commit=False)
        await db.flush()
        await db.refresh(task)
        return task

    @staticmethod
    async def complete(*, db: AsyncSession, user_id: int, task_id: int) -> PomodoroTask:
        """
        完成任务

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param task_id: 任务 ID
        :return:
        """
        task = await PomodoroTaskService.get(db=db, user_id=user_id, task_id=task_id)
        if task.status == PomodoroTaskStatus.completed.value:
            return task

        await pomodoro_task_dao.update_model(
            db,
            task.id,
            {
                'status': PomodoroTaskStatus.completed.value,
                'completed_at': timezone.now(),
            },
            commit=False,
        )
        await db.flush()
        await db.refresh(task)
        return task

    @staticmethod
    async def delete(*, db: AsyncSession, user_id: int, task_id: int) -> None:
        """
        删除任务

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param task_id: 任务 ID
        :return:
        """
        task = await PomodoroTaskService.get(db=db, user_id=user_id, task_id=task_id)
        await pomodoro_task_dao.delete_model(db, task.id)

    @staticmethod
    async def generate_repeat_tasks(
        *,
        db: AsyncSession,
        user_id: int,
        target_date: date | None = None,
    ) -> GetPomodoroRepeatTaskGenerateResult:
        """
        生成重复任务

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param target_date: 目标日期
        :return:
        """
        schedule_date = target_date or timezone.now().date()
        templates = await pomodoro_task_dao.get_repeat_templates(db, user_id)
        created_ids: list[int] = []

        for template in templates:
            if not PomodoroTaskService._should_generate(template=template, target_date=schedule_date):
                continue

            existing = await pomodoro_task_dao.get_existing_schedule(
                db,
                user_id=user_id,
                source_task_id=template.id,
                schedule_date=schedule_date,
            )
            if existing:
                continue

            repeat_key = f'{template.id}:{schedule_date.isoformat()}'
            task = await pomodoro_task_dao.create_model(
                db,
                CreatePomodoroTaskInternal(
                    user_id=user_id,
                    title=template.title,
                    description=template.description,
                    priority=template.priority,
                    estimated_minutes=template.estimated_minutes,
                    due_at=PomodoroTaskService._build_repeat_due_at(template=template, target_date=schedule_date),
                    repeat_type=PomodoroRepeatType.none,
                    source_task_id=template.id,
                    schedule_date=schedule_date,
                    repeat_key=repeat_key,
                ),
                commit=False,
            )
            await db.flush()
            created_ids.append(task.id)

        await db.flush()
        return GetPomodoroRepeatTaskGenerateResult(
            target_date=schedule_date,
            created_count=len(created_ids),
            task_ids=created_ids,
        )

    @staticmethod
    def _should_generate(*, template: PomodoroTask, target_date: date) -> bool:
        """
        判断是否需要生成重复任务

        :param template: 任务模板
        :param target_date: 目标日期
        :return:
        """
        repeat_type = template.repeat_type
        if repeat_type == PomodoroRepeatType.daily.value:
            return True

        if repeat_type == PomodoroRepeatType.weekly.value:
            if template.repeat_days:
                return str(target_date.weekday()) in template.repeat_days.split(',')
            return template.due_at is not None and template.due_at.weekday() == target_date.weekday()

        if repeat_type == PomodoroRepeatType.monthly.value:
            if template.due_at is None:
                return True
            return template.due_at.day == target_date.day

        return False

    @staticmethod
    def _build_repeat_due_at(*, template: PomodoroTask, target_date: date) -> datetime | None:
        """
        构建重复任务截止时间

        :param template: 任务模板
        :param target_date: 目标日期
        :return:
        """
        if template.due_at is None:
            return None

        return template.due_at.replace(
            year=target_date.year,
            month=target_date.month,
            day=target_date.day,
        )


pomodoro_task_service: PomodoroTaskService = PomodoroTaskService()
