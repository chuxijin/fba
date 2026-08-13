from datetime import datetime
from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.learning.crud import learning_completion_dao, learning_focus_dao, learning_task_dao
from backend.app.learning.enums import LearningFocusStatus, LearningTaskStatus
from backend.app.learning.model.execution import LearningCompletionRecord, LearningFocusSession
from backend.app.learning.model.task import LearningTask, LearningTaskGoal
from backend.app.learning.schema.execution import (
    CompleteLearningTaskParam,
    FinishLearningFocusParam,
    GetLearningCompletionRecordDetail,
    GetLearningFocusSessionDetail,
    StartLearningFocusParam,
)
from backend.app.question_bank_v2.crud.crud_practice import practice_session_dao
from backend.common.exception import errors
from backend.utils.timezone import timezone


class LearningExecutionService:
    async def get_current_focus(
        self,
        *,
        db: AsyncSession,
        user_id: int,
    ) -> GetLearningFocusSessionDetail | None:
        session = await learning_focus_dao.get_current(db, user_id)
        return await self._to_detail(db=db, session=session) if session is not None else None

    async def start_focus(
        self,
        *,
        db: AsyncSession,
        task_id: int | None,
        user_id: int,
        obj: StartLearningFocusParam,
    ) -> GetLearningFocusSessionDetail:
        if task_id is not None:
            task = await self._get_user_task(db=db, task_id=task_id, user_id=user_id)
            if task.status in {LearningTaskStatus.completed.value, LearningTaskStatus.canceled.value}:
                raise errors.RequestError(msg='当前任务不能开始专注')
        if await learning_focus_dao.get_current(db, user_id) is not None:
            raise errors.ConflictError(msg='请先结束当前专注')
        session = LearningFocusSession(
            task_id=task_id,
            user_id=user_id,
            planned_minutes=obj.planned_minutes,
            mode=str(obj.mode),  # pydantic v2 把 StrEnum 按 str 校验，obj.mode 可能是纯字符串
        )
        db.add(session)
        if task_id is not None:
            await self._mark_task_in_progress(db=db, task_id=task_id)
        await db.flush()
        await db.refresh(session)
        return await self._to_detail(db=db, session=session)

    async def attach_task(
        self,
        *,
        db: AsyncSession,
        session_id: int,
        user_id: int,
        task_id: int,
    ) -> GetLearningFocusSessionDetail:
        """把进行中的自由专注归属到某个任务，整段专注时长都计入该任务。"""
        session = await self._get_session(db=db, session_id=session_id, user_id=user_id)
        if session.status not in {LearningFocusStatus.running.value, LearningFocusStatus.paused.value}:
            raise errors.RequestError(msg='当前专注已结束，无法关联任务')
        task = await self._get_user_task(db=db, task_id=task_id, user_id=user_id)
        if task.status in {LearningTaskStatus.completed.value, LearningTaskStatus.canceled.value}:
            raise errors.RequestError(msg='该任务已结束，不能作为专注目标')
        await learning_focus_dao.update_model(db, session_id, {'task_id': task_id})
        await self._mark_task_in_progress(db=db, task_id=task_id)
        return await self._to_detail(
            db=db,
            session=await self._get_session(db=db, session_id=session_id, user_id=user_id),
        )

    async def pause_focus(
        self,
        *,
        db: AsyncSession,
        session_id: int,
        user_id: int,
    ) -> GetLearningFocusSessionDetail:
        session = await self._get_session(db=db, session_id=session_id, user_id=user_id)
        if session.status != LearningFocusStatus.running.value:
            raise errors.RequestError(msg='当前专注不能暂停')
        now = timezone.now()
        await learning_focus_dao.update_model(
            db,
            session_id,
            {
                'status': LearningFocusStatus.paused.value,
                'paused_at': now,
                # 暂停即结算已专注秒数，客户端下次进来才能接着剩余时间继续
                'focused_seconds': self._elapsed_focused_seconds(session, now),
                'interrupt_count': session.interrupt_count + 1,
            },
        )
        return await self._to_detail(
            db=db,
            session=await self._get_session(db=db, session_id=session_id, user_id=user_id),
        )

    async def resume_focus(
        self,
        *,
        db: AsyncSession,
        session_id: int,
        user_id: int,
    ) -> GetLearningFocusSessionDetail:
        session = await self._get_session(db=db, session_id=session_id, user_id=user_id)
        if session.status != LearningFocusStatus.paused.value:
            raise errors.RequestError(msg='当前专注不能继续')
        now = timezone.now()
        paused_seconds = session.paused_seconds
        if session.paused_at is not None:
            paused_seconds += max(0, int((now - session.paused_at).total_seconds()))
        await learning_focus_dao.update_model(
            db,
            session_id,
            {
                'status': LearningFocusStatus.running.value,
                'paused_seconds': paused_seconds,
                'paused_at': None,
            },
        )
        return await self._to_detail(
            db=db,
            session=await self._get_session(db=db, session_id=session_id, user_id=user_id),
        )

    async def finish_focus(
        self,
        *,
        db: AsyncSession,
        session_id: int,
        user_id: int,
        obj: FinishLearningFocusParam,
    ) -> GetLearningFocusSessionDetail:
        session = await self._get_session(db=db, session_id=session_id, user_id=user_id)
        if session.status not in {LearningFocusStatus.running.value, LearningFocusStatus.paused.value}:
            raise errors.RequestError(msg='当前专注不能结束')
        now = timezone.now()
        paused_seconds = max(session.paused_seconds, obj.paused_seconds)
        if session.status == LearningFocusStatus.paused.value and session.paused_at is not None:
            paused_seconds += max(0, int((now - session.paused_at).total_seconds()))
        elapsed = max(0, int((now - session.started_at).total_seconds()))
        server_focused = max(0, elapsed - paused_seconds)
        # 客户端上报值只用来收紧，不能夸大；没上报时以服务端推算为准
        focused_seconds = min(obj.focused_seconds, server_focused) if obj.focused_seconds > 0 else server_focused
        await learning_focus_dao.update_model(
            db,
            session_id,
            {
                'status': LearningFocusStatus.completed.value,
                'focused_seconds': focused_seconds,
                'paused_seconds': paused_seconds,
                'interrupt_count': max(session.interrupt_count, obj.interrupt_count),
                'ended_at': now,
                'paused_at': None,
                'remark': obj.remark,
            },
        )
        return await self._to_detail(
            db=db,
            session=await self._get_session(db=db, session_id=session_id, user_id=user_id),
        )

    async def cancel_focus(
        self,
        *,
        db: AsyncSession,
        session_id: int,
        user_id: int,
    ) -> GetLearningFocusSessionDetail:
        session = await self._get_session(db=db, session_id=session_id, user_id=user_id)
        if session.status not in {LearningFocusStatus.running.value, LearningFocusStatus.paused.value}:
            raise errors.RequestError(msg='当前专注不能取消')
        await learning_focus_dao.update_model(
            db,
            session_id,
            {
                'status': LearningFocusStatus.canceled.value,
                'ended_at': timezone.now(),
                'paused_at': None,
            },
        )
        return await self._to_detail(
            db=db,
            session=await self._get_session(db=db, session_id=session_id, user_id=user_id),
        )

    async def complete_task(
        self,
        *,
        db: AsyncSession,
        task_id: int,
        user_id: int,
        obj: CompleteLearningTaskParam,
    ) -> GetLearningCompletionRecordDetail:
        task = await self._get_user_task(db=db, task_id=task_id, user_id=user_id)
        if task.status == LearningTaskStatus.completed.value:
            existing = await learning_completion_dao.get_latest(db, task_id)
            if existing is not None:
                return GetLearningCompletionRecordDetail.model_validate(existing)

        focus_seconds = await learning_focus_dao.sum_task_focus_seconds(db, task_id)
        metrics = dict(obj.metrics)
        metrics['focus_seconds'] = max(focus_seconds, int(metrics.get('focus_seconds') or 0))
        # 自动回填：把该任务关联刷题会话的已答题数合并进指标，做题进度不必手动提交
        session_key = (task.resource_config or {}).get('session_key')
        if session_key:
            session = await practice_session_dao.get_by_key(db, str(session_key), user_id=user_id)
            if session is not None:
                answered = int(session.answered_items or 0)
                metrics['question_count'] = max(int(metrics.get('question_count') or 0), answered)
        # 自建任务的目标是用户给自己定的，手动勾完成不该被自己的目标卡住；
        # 后台发放的任务代表教学要求，必须真的达标才算完成。
        if task.delivery_id is not None:
            await self._check_goals(db=db, task_id=task_id, metrics=metrics)
        record = LearningCompletionRecord(
            task_id=task_id,
            user_id=user_id,
            completion_source=obj.completion_source,
            duration_seconds=int(metrics['focus_seconds']),
            actual_metrics=metrics,
            extra_data=obj.extra_data,
        )
        db.add(record)
        await learning_task_dao.update_model(
            db,
            task_id,
            {'status': LearningTaskStatus.completed.value},
        )
        await db.flush()
        await db.refresh(record)
        return GetLearningCompletionRecordDetail.model_validate(record)

    @staticmethod
    def _elapsed_focused_seconds(session: LearningFocusSession, now: datetime) -> int:
        """按 已流逝 - 累计暂停 推算当前有效专注秒数。"""
        elapsed = max(0, int((now - session.started_at).total_seconds()))
        return max(0, elapsed - session.paused_seconds)

    @staticmethod
    async def _mark_task_in_progress(*, db: AsyncSession, task_id: int) -> None:
        task = await learning_task_dao.get(db, task_id)
        if task is not None and task.status == LearningTaskStatus.pending.value:
            await learning_task_dao.update_model(
                db,
                task_id,
                {'status': LearningTaskStatus.in_progress.value},
            )

    @staticmethod
    async def _to_detail(
        *,
        db: AsyncSession,
        session: LearningFocusSession,
    ) -> GetLearningFocusSessionDetail:
        detail = GetLearningFocusSessionDetail.model_validate(session)
        if session.task_id is not None:
            task = await learning_task_dao.get(db, session.task_id)
            detail.task_title = task.title if task is not None else None
        return detail

    @staticmethod
    async def _check_goals(*, db: AsyncSession, task_id: int, metrics: dict) -> None:
        result = await db.execute(
            select(LearningTaskGoal).where(
                LearningTaskGoal.task_id == task_id,
                LearningTaskGoal.is_required.is_(True),
                LearningTaskGoal.deleted == 0,
            )
        )
        for goal in result.scalars().all():
            if goal.target_value is None:
                continue
            actual_raw = metrics.get(goal.metric)
            if actual_raw is None:
                raise errors.RequestError(msg=f'缺少完成指标: {goal.metric}')
            try:
                actual = Decimal(str(int(actual_raw) if isinstance(actual_raw, bool) else actual_raw))
            except (InvalidOperation, TypeError, ValueError) as exc:
                raise errors.RequestError(msg=f'完成指标 {goal.metric} 不是有效数值') from exc
            target = goal.target_value
            passed = (
                (goal.operator == 'gte' and actual >= target)
                or (goal.operator == 'lte' and actual <= target)
                or (goal.operator == 'eq' and actual == target)
            )
            if not passed:
                raise errors.RequestError(msg=f'完成指标 {goal.metric} 未达到目标 {target}')

    @staticmethod
    async def _get_user_task(*, db: AsyncSession, task_id: int, user_id: int) -> LearningTask:
        task = await learning_task_dao.get(db, task_id)
        if task is None:
            raise errors.NotFoundError(msg='学习任务不存在')
        if task.user_id != user_id:
            raise errors.ForbiddenError(msg='无权操作该学习任务')
        return task

    @staticmethod
    async def _get_session(
        *,
        db: AsyncSession,
        session_id: int,
        user_id: int,
    ) -> LearningFocusSession:
        session = await learning_focus_dao.get(db, session_id, user_id)
        if session is None:
            raise errors.NotFoundError(msg='专注记录不存在')
        return session


learning_execution_service = LearningExecutionService()
