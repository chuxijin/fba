import hashlib
import json
import re

from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.admin.model.category import Category
from backend.app.question_bank_v2.crud.crud_bank import bank_dao, bank_revision_dao
from backend.app.question_bank_v2.crud.crud_knowledge import knowledge_system_dao
from backend.app.question_bank_v2.crud.crud_practice import practice_session_dao
from backend.app.question_bank_v2.crud.crud_preference import practice_preference_dao
from backend.app.question_bank_v2.crud.crud_study_goal import study_goal_dao
from backend.app.question_bank_v2.schema.practice import CreatePracticeSessionParam, GetPracticeSessionDetail
from backend.app.question_bank_v2.schema.study_goal import (
    CreateGoalExamParam,
    ExamTargetConfig,
    GetExamTarget,
    StudyGoal,
)
from backend.app.question_bank_v2.schema.study_goal_state import current_study_goal
from backend.app.question_bank_v2.service.knowledge_service import knowledge_service
from backend.common.exception import errors


class StudyGoalService:
    """考试目录与模板复用字典，用户目标复用偏好；不新增业务表。"""

    @staticmethod
    async def domain_category_ids(*, db: AsyncSession, domain_code: str) -> dict[str, int | None]:
        rows = (
            await db.execute(
                select(Category.id, Category.type).where(
                    Category.app_code == 'youanshang',
                    ((Category.code == f'pc_{domain_code}') & (Category.type == 'product_catalog'))
                    | ((Category.code == f'kp_{domain_code}') & (Category.type == 'knowledge_point')),
                    Category.parent_id.is_(None),
                    Category.deleted == 0,
                    Category.status.is_(True),
                )
            )
        ).all()
        ids = {row.type: row.id for row in rows}
        if 'product_catalog' not in ids:
            raise errors.RequestError(msg='该备考方向尚未配置有效内容目录')
        return {
            'current_category_id': ids['product_catalog'],
            'current_knowledge_point_id': ids.get('knowledge_point'),
        }

    @staticmethod
    def parse_target(row: Any) -> GetExamTarget:
        try:
            config = ExamTargetConfig.model_validate(row.extra)
            if re.fullmatch(r'[a-z0-9_]{1,32}', row.value) is None:
                raise ValueError('目标编码无效')
        except (ValidationError, ValueError) as exc:
            raise errors.RequestError(msg=f'备考目标“{row.label}”配置无效，请联系管理员') from exc
        canonical = json.dumps(
            {'code': row.value, 'name': row.label, 'config': config.model_dump(mode='json')},
            sort_keys=True,
            ensure_ascii=False,
            separators=(',', ':'),
        )
        return GetExamTarget(
            code=row.value,
            name=row.label,
            config=config,
            config_revision=hashlib.sha256(canonical.encode()).hexdigest(),
        )

    @staticmethod
    async def get_targets(*, db: AsyncSession, domain_code: str | None = None) -> list[GetExamTarget]:
        rows = await study_goal_dao.get_targets(db)
        codes = [row.value for row in rows]
        if len(codes) != len(set(codes)):
            raise errors.RequestError(msg='备考目标编码重复，请联系管理员')
        targets = [StudyGoalService.parse_target(row) for row in rows]
        return [target for target in targets if domain_code is None or target.config.domain_code == domain_code]

    @staticmethod
    async def get_target(*, db: AsyncSession, code: str) -> GetExamTarget:
        rows = await study_goal_dao.get_targets(db, code)
        if len(rows) != 1:
            raise errors.RequestError(msg='备考目标不存在、已停用或编码重复，请重新选择')
        return StudyGoalService.parse_target(rows[0])

    @staticmethod
    async def validate_goal(*, db: AsyncSession, goal: StudyGoal) -> GetExamTarget:
        target = await StudyGoalService.get_target(db=db, code=goal.exam_target_code)
        if goal.exam_year not in target.config.years or any(
            subject not in target.config.subjects for subject in goal.subjects
        ):
            raise errors.RequestError(msg='报考年度或科目不适用于该目标，请重新选择')
        path = target.config.category_path(goal.category_code)
        if target.config.categories:
            if not path or path[-1].children:
                raise errors.RequestError(msg='请选择该目标的末级考试类别；旧目标需要补选类别')
        elif goal.category_code is not None:
            raise errors.RequestError(msg='该目标没有此考试类别，请重新选择')
        return target

    @staticmethod
    async def validate_config(*, db: AsyncSession, config: ExamTargetConfig) -> None:
        """显式绑定题池与知识体系，不通过地区名称模糊匹配兜底。"""
        for template in config.templates:
            system = await knowledge_system_dao.get(db, template.knowledge_system_id)
            if system is None:
                raise errors.RequestError(msg='模板知识体系不存在或未启用')
            domain_code = await db.scalar(
                select(Category.code).where(
                    Category.id == system.domain_category_id,
                    Category.type == 'product_catalog',
                    Category.deleted == 0,
                    Category.status.is_(True),
                )
            )
            if domain_code != f'pc_{config.domain_code}':
                raise errors.RequestError(msg='模板知识体系与备考领域不一致')
            bank = await bank_dao.get(db, template.bank_id)
            if bank is None or bank.status != 'active' or bank.visibility != 'public' or not bank.current_revision_id:
                raise errors.RequestError(msg='目标模板必须绑定已发布的公共题库')
            revision = await bank_revision_dao.get(db, bank.current_revision_id, bank_id=template.bank_id)
            if revision is None or revision.status != 'published':
                raise errors.RequestError(msg='目标模板题库当前发布版本不存在或尚未发布')
            await knowledge_service.resolve_point_ids(
                db=db,
                point_ids=[item.knowledge_point_id for item in template.modules],
                include_descendants=True,
                system_id=template.knowledge_system_id,
            )

    @staticmethod
    async def _current_goal(*, db: AsyncSession, user_id: int) -> StudyGoal:
        preference = await practice_preference_dao.get_by_user_id(db, user_id)
        raw_goal = current_study_goal(getattr(preference, 'study_goal', None))
        if not raw_goal:
            raise errors.RequestError(msg='请先设置备考目标')
        try:
            return StudyGoal.model_validate(raw_goal)
        except ValidationError as exc:
            raise errors.RequestError(msg='备考目标数据无效，请重新设置') from exc

    @staticmethod
    async def create_exam(*, db: AsyncSession, user_id: int, obj: CreateGoalExamParam) -> GetPracticeSessionDetail:
        # 本接口从登录用户偏好读取目标，不接收任意 user_id、题池、配额或时长。
        from backend.app.question_bank_v2.service.practice_service import practice_service

        if not obj.session_key.startswith('goal_'):
            raise errors.RequestError(msg='目标考试会话标识必须使用goal_前缀')
        request = obj.model_dump(exclude={'session_key'})
        existing = await practice_session_dao.get_by_key(db, obj.session_key, user_id=user_id)
        if existing is not None:
            saved_request = (existing.source_snapshot or {}).get('study_goal', {}).get('request')
            # 旧会话没有类别字段；仅把缺省视为 null，不放宽任何已有请求条件。
            if isinstance(saved_request, dict):
                saved_request = {'category_code': None, **saved_request}
            if saved_request != request:
                raise errors.ConflictError(msg='会话标识已被其他请求使用')
            return await practice_service.get(db=db, session_key=obj.session_key, user_id=user_id)
        goal = await StudyGoalService._current_goal(db=db, user_id=user_id)
        if (
            goal.exam_target_code != obj.exam_target_code
            or goal.exam_year != obj.exam_year
            or goal.category_code != obj.category_code
        ):
            raise errors.ConflictError(msg='备考目标已变更，请刷新后重试')
        target = await StudyGoalService.validate_goal(db=db, goal=goal)
        if target.config_revision != obj.config_revision:
            raise errors.ConflictError(msg='组卷配置已更新，请刷新模板后重试')
        template = next((item for item in target.config.templates if item.key == obj.template_key), None)
        if (
            template is None
            or template.subject not in goal.subjects
            or template.category_code != goal.category_code
            or (template.years and goal.exam_year not in template.years)
        ):
            raise errors.RequestError(msg='该目标或已选科目暂无此组卷模板')
        await StudyGoalService.validate_config(db=db, config=target.config)
        category_path = target.config.category_path(goal.category_code)
        category_name = ' / '.join(node.name for node in category_path)
        title_parts = [f'{goal.exam_year} {target.name}']
        if category_name:
            title_parts.append(category_name)
        title_parts.append(template.name)
        body = CreatePracticeSessionParam(
            source_type='custom',
            bank_id=template.bank_id,
            knowledge_system_id=template.knowledge_system_id,
            module_quotas=[
                {'knowledge_point_id': item.knowledge_point_id, 'count': item.count} for item in template.modules
            ],
            mode='exam',
            duration_minutes=template.duration_minutes,
            limit=template.total,
            shuffle=True,
            title=' · '.join(title_parts)[:255],
            session_key=obj.session_key,
        )
        context = {
            'request': request,
            'goal': goal.model_dump(mode='json'),
            'target_name': target.name,
            'category_path': [{'code': node.code, 'name': node.name} for node in category_path],
            'template': template.model_dump(mode='json'),
        }
        return await practice_service.create(db=db, user_id=user_id, obj=body, goal_context=context)


study_goal_service = StudyGoalService()
