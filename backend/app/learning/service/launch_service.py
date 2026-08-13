from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.learning.crud import learning_task_dao
from backend.app.learning.enums import LearningActionType, LearningResourceType, LearningTaskStatus
from backend.app.learning.model.task import LearningTask, LearningTaskGoal, LearningTaskKnowledgePoint
from backend.app.learning.schema.task import StartLearningTaskResult
from backend.app.question_bank_v2.crud.crud_practice import practice_session_dao
from backend.app.question_bank_v2.schema.practice import CreatePracticeSessionParam
from backend.app.question_bank_v2.service.practice_service import practice_service
from backend.app.question_bank_v2.service.wrong_review_service import wrong_review_service
from backend.common.exception import errors

# 强化练习标识到小程序页面的兜底映射，后台可用 resource_config.ability_url 覆盖
ABILITY_PAGE_BY_KEY: dict[str, str] = {
    'basic_calculation': '/pkg/ability/basic-calculation/index',
    'adv_calc': '/pkg/ability/adv-calc/index',
    'data_analysis': '/pkg/ability/data-analysis/index',
    'data_analysis_practice': '/pkg/ability/data-analysis/practice/index',
    'data_analysis_fill_blank': '/pkg/ability/data-analysis/fill-blank/index',
    'data_analysis_challenge': '/pkg/ability/data-analysis/challenge/index',
    'essay_terms': '/pkg/ability/essay-terms/index',
    'number_reasoning': '/pkg/ability/number-reasoning/index',
    'formula_ref': '/pkg/ability/formula-ref/index',
    'hanyu_assistant': '/pkg/ability/hanyu-assistant/index',
    'quick_calc_sop': '/pkg/ability/quick-calc-sop/index',
    'spatial': '/pkg/ability/spatial/index',
    'thinking_training': '/pkg/ability/thinking-training/index',
}

_ALLOWED_PRACTICE_MODES = {'practice', 'exam', 'mock', 'memorize', 'review'}
_ALLOWED_QUESTION_TYPES = {'single', 'multiple', 'judgement', 'fill', 'shortAnswer'}
_ACTIVE_SESSION_STATUS = {'created', 'in_progress'}
_CONTENT_RESOURCE_TYPES = {
    LearningResourceType.content.value,
    LearningResourceType.course.value,
    LearningResourceType.course_lesson.value,
}


class LearningLaunchService:
    """学习任务启动编排：把任务的资源配置翻译成客户端能直接跳转的入口。

    只有后台交付单发放的任务才带资源配置，因此只有它们会分发到刷题 / 强化 / 资源页；
    用户自建任务没有可执行资源，统一回落到专注计时。
    """

    async def start_task(
        self,
        *,
        db: AsyncSession,
        task_id: int,
        user_id: int,
    ) -> StartLearningTaskResult:
        task = await learning_task_dao.get(db, task_id)
        if task is None:
            raise errors.NotFoundError(msg='学习任务不存在')
        if task.user_id != user_id:
            raise errors.ForbiddenError(msg='无权操作该学习任务')
        if task.status == LearningTaskStatus.completed.value:
            raise errors.RequestError(msg='该任务已完成')
        if task.status == LearningTaskStatus.canceled.value:
            raise errors.RequestError(msg='该任务已取消')

        launch_type, payload, hint = await self._resolve_launch(db=db, task=task)
        # 只有真的进入了学习动作才推进状态，缺配置回落专注时保持原状态
        if launch_type != 'focus' and task.status == LearningTaskStatus.pending.value:
            await learning_task_dao.update_model(
                db,
                task_id,
                {'status': LearningTaskStatus.in_progress.value},
            )
            task.status = LearningTaskStatus.in_progress.value

        return StartLearningTaskResult(
            task_id=task.id,
            status=LearningTaskStatus(task.status),
            launch_type=launch_type,
            payload=payload,
            hint=hint,
        )

    async def _resolve_launch(
        self,
        *,
        db: AsyncSession,
        task: LearningTask,
    ) -> tuple[str, dict[str, Any] | None, str | None]:
        if task.delivery_id is None:
            return 'focus', None, None

        config = dict(task.resource_config or {})

        if task.action_type == LearningActionType.wrong_review.value:
            return await self._resolve_wrong_review(db=db, task=task, config=config)

        if task.resource_type == LearningResourceType.question_bank.value:
            session_key = await self._ensure_practice_session(db=db, task=task, config=config)
            return 'practice', {'session_key': session_key, 'mode': self._practice_mode(config)}, None

        if task.resource_type == LearningResourceType.ability.value:
            ability_key = (task.resource_key or '').strip()
            ability_url = self._text(config.get('ability_url')) or ABILITY_PAGE_BY_KEY.get(ability_key)
            if not ability_url:
                return 'focus', None, '该强化练习尚未配置入口，可先用专注计时完成'
            return 'ability', {'ability_key': ability_key, 'ability_url': ability_url}, None

        if task.resource_type in _CONTENT_RESOURCE_TYPES:
            if task.resource_id is None:
                return 'focus', None, '该资源任务尚未配置内容，可先用专注计时完成'
            return (
                'content',
                {
                    'resource_type': task.resource_type,
                    'resource_id': task.resource_id,
                    'resource_version_id': task.resource_version_id,
                },
                None,
            )

        if task.resource_type == LearningResourceType.external.value:
            links = config.get('cloud_links') if isinstance(config.get('cloud_links'), list) else []
            external_url = self._text(config.get('external_url'))
            if not links and not external_url:
                return 'focus', None, None
            return 'content', {'resource_type': 'external', 'cloud_links': links, 'external_url': external_url}, None

        return 'focus', None, None

    async def _resolve_wrong_review(
        self,
        *,
        db: AsyncSession,
        task: LearningTask,
        config: dict[str, Any],
    ) -> tuple[str, dict[str, Any] | None, str | None]:
        """错题复盘每次都按当前到期队列取题，队列为空是正常业务结果。"""
        limit = await self._question_limit(db=db, task=task, config=config) or 10
        result = await wrong_review_service.get_due(db=db, user_id=task.user_id, limit=limit)
        question_ids = [item.question_id for item in result.items]
        if not question_ids:
            return 'focus', None, '暂时没有到期需要重练的错题，先做点新题吧'
        session_key = await self._ensure_practice_session(
            db=db,
            task=task,
            config=config,
            override_question_ids=question_ids,
        )
        return 'practice', {'session_key': session_key, 'mode': 'memorize'}, None

    async def _ensure_practice_session(
        self,
        *,
        db: AsyncSession,
        task: LearningTask,
        config: dict[str, Any],
        override_question_ids: list[int] | None = None,
    ) -> str:
        """复用未结束的练习会话，避免做一半退出再进来题目全换。"""
        existing = self._text(config.get('session_key'))
        if existing is not None:
            session = await practice_session_dao.get_by_key(db, existing, user_id=task.user_id)
            if session is not None and session.status in _ACTIVE_SESSION_STATUS:
                return existing
            config.pop('session_key', None)

        param = await self._build_session_param(
            db=db,
            task=task,
            config=config,
            override_question_ids=override_question_ids,
        )
        session = await practice_service.create(db=db, user_id=task.user_id, obj=param)
        config['session_key'] = session.session_key
        await learning_task_dao.update_model(db, task.id, {'resource_config': config})
        task.resource_config = config
        return session.session_key

    async def _build_session_param(
        self,
        *,
        db: AsyncSession,
        task: LearningTask,
        config: dict[str, Any],
        override_question_ids: list[int] | None,
    ) -> CreatePracticeSessionParam:
        question_ids = override_question_ids or self._positive_int_list(config.get('question_ids'), limit=500)
        shared: dict[str, Any] = {
            'mode': 'memorize' if override_question_ids else self._practice_mode(config),
            'duration_minutes': self._duration_minutes(config),
            'title': task.title,
            'question_types': self._question_types(config.get('question_types')),
            'shuffle': bool(config.get('shuffle')),
            'limit': await self._question_limit(db=db, task=task, config=config),
        }

        # 指定题目优先：错题重练和后台点选的题目都走这条路，不再按条件抽题
        if question_ids:
            return CreatePracticeSessionParam(source_type='custom', question_ids=question_ids, **shared)

        if task.resource_id is None:
            raise errors.RequestError(msg='该刷题任务未配置题库或题目，请联系导师')

        system_id, point_ids, include_descendants = await self._knowledge_scope(db=db, task_id=task.id)
        return CreatePracticeSessionParam(
            source_type='bank',
            bank_id=task.resource_id,
            section_id=self._positive_int(config.get('section_id') or config.get('chapter_id')),
            knowledge_system_id=system_id,
            knowledge_point_ids=point_ids,
            include_knowledge_descendants=include_descendants,
            year_start=self._year(config.get('year_start')),
            year_end=self._year(config.get('year_end')),
            region=self._text(config.get('region')),
            **shared,
        )

    @staticmethod
    async def _knowledge_scope(*, db: AsyncSession, task_id: int) -> tuple[int | None, list[int], bool]:
        result = await db.execute(
            select(
                LearningTaskKnowledgePoint.knowledge_system_id,
                LearningTaskKnowledgePoint.knowledge_point_id,
                LearningTaskKnowledgePoint.include_descendants,
            )
            .where(
                LearningTaskKnowledgePoint.task_id == task_id,
                LearningTaskKnowledgePoint.deleted == 0,
            )
            .order_by(LearningTaskKnowledgePoint.id.asc())
        )
        rows = result.all()
        if not rows:
            return None, [], True
        # 题库 v2 要求同场知识点同属一个体系，跨体系时只保留首个体系的知识点
        system_id = int(rows[0][0])
        scoped = [row for row in rows if int(row[0]) == system_id]
        point_ids = sorted({int(row[1]) for row in scoped})[:100]
        include_descendants = any(bool(row[2]) for row in scoped)
        return system_id, point_ids, include_descendants

    async def _question_limit(
        self,
        *,
        db: AsyncSession,
        task: LearningTask,
        config: dict[str, Any],
    ) -> int | None:
        """题量优先取资源配置，其次沿用任务目标里的题数要求。"""
        limit = self._positive_int(config.get('question_count'))
        if limit is None:
            result = await db.execute(
                select(LearningTaskGoal.target_value).where(
                    LearningTaskGoal.task_id == task.id,
                    LearningTaskGoal.metric == 'question_count',
                    LearningTaskGoal.target_value.is_not(None),
                    LearningTaskGoal.deleted == 0,
                )
            )
            target = result.scalars().first()
            limit = self._positive_int(int(target)) if target is not None else None
        return min(limit, 500) if limit is not None else None

    @staticmethod
    def _practice_mode(config: dict[str, Any]) -> str:
        mode = config.get('practice_mode')
        return mode if isinstance(mode, str) and mode in _ALLOWED_PRACTICE_MODES else 'practice'

    @classmethod
    def _duration_minutes(cls, config: dict[str, Any]) -> int | None:
        """限时只在考试类模式下由后台显式配置，普通练习不设倒计时。"""
        if cls._practice_mode(config) not in {'exam', 'mock'}:
            return None
        minutes = cls._positive_int(config.get('duration_minutes'))
        if minutes is None:
            seconds = cls._positive_int(config.get('time_limit'))
            minutes = max(1, round(seconds / 60)) if seconds is not None else None
        return min(minutes, 600) if minutes is not None else None

    @classmethod
    def _question_types(cls, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [item for item in value if isinstance(item, str) and item in _ALLOWED_QUESTION_TYPES]

    @staticmethod
    def _positive_int(value: Any) -> int | None:
        if isinstance(value, bool):
            return None
        if isinstance(value, int) and value > 0:
            return value
        if isinstance(value, str) and value.strip().isdigit() and int(value.strip()) > 0:
            return int(value.strip())
        return None

    @classmethod
    def _positive_int_list(cls, value: Any, limit: int) -> list[int]:
        if not isinstance(value, list):
            return []
        result: list[int] = []
        seen: set[int] = set()
        for item in value:
            parsed = cls._positive_int(item)
            if parsed is None or parsed in seen:
                continue
            seen.add(parsed)
            result.append(parsed)
            if len(result) >= limit:
                break
        return result

    @classmethod
    def _year(cls, value: Any) -> int | None:
        parsed = cls._positive_int(value)
        return parsed if parsed is not None and 1900 <= parsed <= 2100 else None

    @staticmethod
    def _text(value: Any) -> str | None:
        if not isinstance(value, str):
            return None
        text = value.strip()
        return text or None


learning_launch_service = LearningLaunchService()
