from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.question_bank_v2.crud.crud_preference import practice_preference_dao
from backend.app.question_bank_v2.schema.preference import GetPracticePreferenceDetail, UpdatePracticePreferenceParam
from backend.app.question_bank_v2.schema.study_goal import StudyGoal
from backend.app.question_bank_v2.schema.study_goal_state import (
    current_study_goal,
    pack_study_goals,
    saved_study_goals,
    study_goal_key,
    study_goals_revision,
)
from backend.common.exception import errors


class PreferenceService:
    """用户练习偏好服务类"""

    @staticmethod
    async def _check_timezone(*, data: dict) -> None:
        reminder_timezone = data.get('review_reminder_timezone')
        if reminder_timezone is not None:
            try:
                ZoneInfo(reminder_timezone)
            except ZoneInfoNotFoundError as exc:
                raise errors.RequestError(msg='提醒时区不是有效的 IANA 时区') from exc

    @staticmethod
    async def get(*, db: AsyncSession, user_id: int) -> GetPracticePreferenceDetail:
        """获取用户练习偏好，不存在时返回稳定默认值"""
        preference = await practice_preference_dao.get_by_user_id(db, user_id)
        if preference is None:
            return GetPracticePreferenceDetail()
        return await PreferenceService._detail(db=db, preference=preference)

    @staticmethod
    async def _detail(*, db: AsyncSession, preference: object) -> GetPracticePreferenceDetail:
        result = GetPracticePreferenceDetail.model_validate(preference)
        raw = getattr(preference, 'study_goal', None)
        result.saved_study_goals = saved_study_goals(raw)
        result.study_goals_revision = study_goals_revision(raw)
        if result.study_goal is not None:
            from backend.app.question_bank_v2.service.study_goal_service import study_goal_service

            try:
                target = await study_goal_service.get_target(db=db, code=result.study_goal.exam_target_code)
                linked = await study_goal_service.domain_category_ids(db=db, domain_code=target.config.domain_code)
            except errors.RequestError:
                # 停用或旧类别不妨碍读取历史偏好，也不猜测其他目标。
                return result
            result.current_category_id = linked['current_category_id']
            result.current_knowledge_point_id = linked['current_knowledge_point_id']
        return result

    @staticmethod
    async def update(
        *,
        db: AsyncSession,
        user_id: int,
        obj: UpdatePracticePreferenceParam,
    ) -> GetPracticePreferenceDetail:
        """创建或更新用户练习偏好"""
        data = obj.model_dump(exclude_unset=True)
        data.pop('browse_domain_code', None)
        requested_saved = data.pop('saved_study_goals', None)
        data.pop('study_goals_revision', None)
        if db is not None and db.bind is not None and db.bind.dialect.name == 'postgresql':
            # 同账号不同入口并发保存时，目标与兼容领域不能被旧请求拆开写入。
            await db.execute(
                text('SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))'),
                {'key': f'practice-preference:{user_id}'},
            )
        preference = await practice_preference_dao.get_by_user_id(db, user_id)
        raw_state = getattr(preference, 'study_goal', None)
        current_goal, saved = PreferenceService._organized_goals(raw_state=raw_state, obj=obj, data=data)
        await PreferenceService._goal_changes(
            db=db, obj=obj, data=data, current_goal=current_goal, preference=preference
        )
        if 'study_goal' in data:
            current_goal = data['study_goal'] or None
            if current_goal:
                selected = StudyGoal.model_validate(current_goal)
                index = next(
                    (i for i, item in enumerate(saved) if study_goal_key(item) == study_goal_key(selected)), None
                )
                if index is None:
                    saved.append(selected)
                else:
                    saved[index] = selected
        if len(saved) > 20:
            raise errors.RequestError(msg='最多保存20个备考目标，请先整理列表')
        if 'study_goal' in data or requested_saved is not None:
            data['study_goal'] = pack_study_goals(current_goal, saved)
        await PreferenceService._check_timezone(data=data)
        if preference is None:
            preference = await practice_preference_dao.create(db, user_id=user_id, data=data)
        elif data:
            await practice_preference_dao.update(db, preference.id, user_id=user_id, data=data)
            preference = await practice_preference_dao.get_by_user_id(db, user_id)
        return await PreferenceService._detail(db=db, preference=preference)

    @staticmethod
    def _organized_goals(
        *, raw_state: dict | None, obj: UpdatePracticePreferenceParam, data: dict
    ) -> tuple[dict | None, list[StudyGoal]]:
        current_goal = current_study_goal(raw_state)
        saved = saved_study_goals(raw_state)
        if obj.study_goals_revision is not None and obj.study_goals_revision != study_goals_revision(raw_state):
            raise errors.ConflictError(msg='备考目标列表已变更，请刷新后重试')
        if obj.saved_study_goals is None:
            return current_goal, saved
        if obj.study_goals_revision is None:
            raise errors.RequestError(msg='整理目标列表前请先刷新')
        saved = obj.saved_study_goals
        keys = [study_goal_key(item) for item in saved]
        if len(keys) != len(set(keys)):
            raise errors.RequestError(msg='相同年度和类别的备考目标不能重复添加')
        original = {study_goal_key(item): item for item in saved_study_goals(raw_state)}
        # 已停用目标也能整理，但不能借列表整理新增或修改目标内容。
        if any(original.get(study_goal_key(item)) != item for item in saved):
            raise errors.RequestError(msg='请通过添加或修改目标更新目标内容')
        if current_goal and study_goal_key(StudyGoal.model_validate(current_goal)) not in keys:
            current_goal = None
            data.setdefault('study_goal', {})
        return current_goal, saved

    @staticmethod
    async def _goal_changes(
        *,
        db: AsyncSession,
        obj: UpdatePracticePreferenceParam,
        data: dict,
        current_goal: dict | None,
        preference: object,
    ) -> None:
        from backend.app.question_bank_v2.service.study_goal_service import study_goal_service

        if obj.browse_domain_code is not None:
            if obj.study_goal is not None:
                raise errors.RequestError(msg='完整备考目标与仅浏览方向不能同时设置')
            data['study_goal'] = {}
            data.update(await study_goal_service.domain_category_ids(db=db, domain_code=obj.browse_domain_code))
        elif 'study_goal' in data:
            if obj.study_goal is not None:
                target = await study_goal_service.validate_goal(db=db, goal=obj.study_goal)
                data['study_goal'] = obj.study_goal.model_dump(mode='json')
                data.update(await study_goal_service.domain_category_ids(db=db, domain_code=target.config.domain_code))
            else:
                data['study_goal'] = {}
        elif {'current_category_id', 'current_knowledge_point_id'} & data.keys() and current_goal:
            await PreferenceService._link_current_domain(
                db=db, data=data, current_goal=current_goal, preference=preference
            )

    @staticmethod
    async def _link_current_domain(*, db: AsyncSession, data: dict, current_goal: dict, preference: object) -> None:
        """兼容旧客户端，不允许领域写入把完整目标拆开。"""
        from backend.app.question_bank_v2.service.study_goal_service import study_goal_service

        try:
            target = await study_goal_service.get_target(db=db, code=current_goal['exam_target_code'])
            linked = await study_goal_service.domain_category_ids(db=db, domain_code=target.config.domain_code)
        except errors.RequestError:
            # 停用目标不阻断原目录普通刷题，但不允许暗中切方向。
            if 'current_category_id' in data and data['current_category_id'] != preference.current_category_id:
                raise errors.RequestError(msg='请通过切换备考目标更换备考方向') from None
            data.pop('current_knowledge_point_id', None)
        else:
            if 'current_category_id' in data and data['current_category_id'] != linked['current_category_id']:
                raise errors.RequestError(msg='请通过切换备考目标更换备考方向')
            data.update(linked)


preference_service: PreferenceService = PreferenceService()
