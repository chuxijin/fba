#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json

from collections.abc import Sequence
from decimal import Decimal
from typing import Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.challenge.crud.crud_challenge import (
    challenge_attempt_dao,
    challenge_level_dao,
    challenge_question_source_dao,
    user_challenge_progress_dao,
)
from backend.app.challenge.model import ChallengeAttempt, ChallengeLevel, UserChallengeProgress
from backend.app.challenge.schema.challenge import (
    ChallengeAnswerResult,
    ChallengeAttemptRequirementParam,
    ChallengeCompletionRuleParam,
    ChallengeLevelParam,
    ChallengeQuestionItem,
    ChallengeQuestionOption,
    CreateChallengeLevelParam,
    GetChallengeAttemptResponse,
    GetChallengeLevelDetail,
    GetChallengeMapLevel,
    GetChallengeMapResponse,
    GetChallengeMapStage,
    GetChallengeSectionDetail,
    SubmitChallengeAttemptParam,
    SubmitChallengeAttemptResult,
    UpdateChallengeLevelParam,
)
from backend.app.challenge.service.generator import generate_challenge_question
from backend.app.question_bank.crud.crud_interaction import material_anchor_dao
from backend.app.question_bank.crud.crud_question import question_dao
from backend.app.question_bank.model import (
    MaterialAnchor,
    Question,
    QuestionInteractionAnnotation,
    QuestionMaterial,
)
from backend.app.question_bank.service.interaction_service import interaction_annotation_service
from backend.app.question_bank.service.question_service import question_service
from backend.common.exception import errors
from backend.database.redis import redis_client
from backend.utils.timezone import timezone

CHALLENGE_ATTEMPT_TTL = 7200
CHALLENGE_REDIS_PREFIX = 'challenge:attempt'
COMPLETION_RULE_CONFIG_KEY = 'completion_rule'
STAGE_ORDER = ['stage_1', 'stage_2', 'stage_3', 'stage_4']
DATA_ANALYSIS_ANCHOR_ROLE_NAMES = {
    'current_value': '现期',
    'base_value': '基期',
    'growth_rate': '增长率',
    'growth_amount': '增长量',
    'yoy': '同比',
    'mom': '环比',
    'change_amount': '变化量',
    'change_rate': '变化幅度',
}
ANCHOR_DISPLAY_SCOPES = {'sentence', 'block', 'material'}


class ChallengeService:
    """闯关服务类"""

    @staticmethod
    def _redis_key(attempt_key: str) -> str:
        """
        构建挑战 Redis Key

        :param attempt_key: 挑战标识
        :return:
        """
        return f'{CHALLENGE_REDIS_PREFIX}:{attempt_key}'

    @staticmethod
    def _decimal(value: Any, default: str = '0') -> Decimal:
        """
        转换 Decimal

        :param value: 原始值
        :param default: 默认值
        :return:
        """
        try:
            return Decimal(str(value))
        except (ValueError, TypeError):
            return Decimal(default)

    @staticmethod
    def _completion_rule_payload(
        completion_rule: ChallengeCompletionRuleParam | dict[str, Any] | None,
        pass_rate: Decimal,
    ) -> dict[str, Any]:
        """
        构建有效通关规则

        :param completion_rule: 通关规则配置
        :param pass_rate: 默认通关正确率
        :return:
        """
        data: dict[str, Any] = {}
        if isinstance(completion_rule, ChallengeCompletionRuleParam):
            data = completion_rule.model_dump()
        elif isinstance(completion_rule, dict):
            data = completion_rule

        mode = str(data.get('mode') or 'single_attempt')
        if mode not in {'single_attempt', 'consecutive_attempts'}:
            mode = 'single_attempt'

        try:
            required_attempts = int(data.get('required_attempts') or 1)
        except (TypeError, ValueError):
            required_attempts = 1
        if required_attempts < 1:
            required_attempts = 1
        if required_attempts > 100:
            required_attempts = 100
        if mode == 'single_attempt':
            required_attempts = 1

        min_accuracy_rate = data.get('min_accuracy_rate')
        if min_accuracy_rate is None:
            min_accuracy_rate = pass_rate

        max_total_time = None
        raw_max_total_time = data.get('max_total_time')
        if raw_max_total_time is not None:
            try:
                max_total_time = int(raw_max_total_time)
            except (TypeError, ValueError):
                max_total_time = None
            if max_total_time is not None and max_total_time <= 0:
                max_total_time = None

        attempt_requirements = ChallengeService._attempt_requirements_payload(
            data.get('attempt_requirements'),
            required_attempts,
        )

        return {
            'mode': mode,
            'required_attempts': required_attempts,
            'min_accuracy_rate': str(ChallengeService._decimal(min_accuracy_rate, str(pass_rate))),
            'max_total_time': max_total_time,
            'attempt_requirements': attempt_requirements,
        }

    @staticmethod
    def _attempt_requirements_payload(
        raw_requirements: Any,
        required_attempts: int,
    ) -> list[dict[str, Any]]:
        """
        构建连续达标分次要求

        :param raw_requirements: 原始分次要求
        :param required_attempts: 要求达标次数
        :return:
        """
        if not isinstance(raw_requirements, list):
            return []

        requirements: list[dict[str, Any]] = []
        for index, item in enumerate(raw_requirements[:required_attempts], start=1):
            if isinstance(item, ChallengeAttemptRequirementParam):
                data = item.model_dump()
            elif isinstance(item, dict):
                data = item
            else:
                continue

            max_total_time = None
            raw_max_total_time = data.get('max_total_time')
            if raw_max_total_time is not None:
                try:
                    max_total_time = int(raw_max_total_time)
                except (TypeError, ValueError):
                    max_total_time = None
                if max_total_time is not None and max_total_time <= 0:
                    max_total_time = None

            requirement = {
                'seq_no': index,
                'title': data.get('title'),
                'description': data.get('description'),
                'min_accuracy_rate': (
                    str(ChallengeService._decimal(data.get('min_accuracy_rate')))
                    if data.get('min_accuracy_rate') is not None
                    else None
                ),
                'max_total_time': max_total_time,
            }
            requirements.append(requirement)
        return requirements

    @staticmethod
    def _completion_rule_schema(
        completion_rule: ChallengeCompletionRuleParam | dict[str, Any] | None,
        pass_rate: Decimal,
    ) -> ChallengeCompletionRuleParam:
        """
        构建通关规则响应模型

        :param completion_rule: 通关规则配置
        :param pass_rate: 默认通关正确率
        :return:
        """
        return ChallengeCompletionRuleParam.model_validate(
            ChallengeService._completion_rule_payload(completion_rule, pass_rate)
        )

    @staticmethod
    def _completion_rule_from_display_config(display_config: dict[str, Any] | None) -> dict[str, Any] | None:
        """
        从展示配置读取通关规则

        :param display_config: 展示配置
        :return:
        """
        if not isinstance(display_config, dict):
            return None
        rule = display_config.get(COMPLETION_RULE_CONFIG_KEY)
        if not isinstance(rule, dict):
            return None
        return rule

    @staticmethod
    def _level_completion_rule(level: ChallengeLevel) -> dict[str, Any] | None:
        """
        读取关卡通关规则

        :param level: 关卡模型
        :return:
        """
        direct_rule = getattr(level, 'completion_rule', None)
        if isinstance(direct_rule, dict):
            return direct_rule
        return ChallengeService._completion_rule_from_display_config(level.display_config)

    @staticmethod
    def _public_display_config(display_config: dict[str, Any] | None) -> dict[str, Any] | None:
        """
        构建对外展示配置

        :param display_config: 数据库存储展示配置
        :return:
        """
        if not isinstance(display_config, dict):
            return display_config
        data = dict(display_config)
        data.pop(COMPLETION_RULE_CONFIG_KEY, None)
        return data or None

    @staticmethod
    def _display_config_with_completion_rule(
        display_config: dict[str, Any] | None,
        completion_rule: ChallengeCompletionRuleParam | dict[str, Any] | None,
        pass_rate: Decimal,
    ) -> dict[str, Any] | None:
        """
        合并展示配置和通关规则

        :param display_config: 对外展示配置
        :param completion_rule: 通关规则配置
        :param pass_rate: 默认通关正确率
        :return:
        """
        data = dict(display_config) if isinstance(display_config, dict) else {}
        data.pop(COMPLETION_RULE_CONFIG_KEY, None)
        if completion_rule is not None:
            data[COMPLETION_RULE_CONFIG_KEY] = ChallengeService._completion_rule_payload(
                completion_rule,
                pass_rate,
            )
        return data or None

    @staticmethod
    def _completion_rule_from_snapshot(rules: dict[str, Any]) -> dict[str, Any]:
        """
        从挑战快照读取通关规则

        :param rules: 通关规则快照
        :return:
        """
        pass_rate = ChallengeService._decimal(rules.get('pass_rate'), '80')
        return ChallengeService._completion_rule_payload(rules.get('completion_rule'), pass_rate)

    @staticmethod
    def _attempt_requirement_for_index(
        completion_rule: dict[str, Any],
        attempt_index: int | None,
    ) -> dict[str, Any] | None:
        """
        读取指定连续次数的单次要求

        :param completion_rule: 通关规则
        :param attempt_index: 连续达标序号
        :return:
        """
        if attempt_index is None or attempt_index <= 0:
            return None
        requirements = completion_rule.get('attempt_requirements')
        if not isinstance(requirements, list):
            return None
        for item in requirements:
            if not isinstance(item, dict):
                continue
            if int(item.get('seq_no') or 0) == attempt_index:
                return item
        return None

    @staticmethod
    def _requirement_schema(requirement: dict[str, Any] | None) -> ChallengeAttemptRequirementParam | None:
        """
        构建单次要求响应模型

        :param requirement: 单次要求
        :return:
        """
        if not isinstance(requirement, dict):
            return None
        return ChallengeAttemptRequirementParam.model_validate(requirement)

    @staticmethod
    def _completion_rule_with_attempt_requirement(
        completion_rule: dict[str, Any],
        attempt_requirement: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """
        合并本次达标要求

        :param completion_rule: 基础通关规则
        :param attempt_requirement: 本次达标要求
        :return:
        """
        if not isinstance(attempt_requirement, dict):
            return completion_rule

        data = dict(completion_rule)
        if attempt_requirement.get('min_accuracy_rate') is not None:
            data['min_accuracy_rate'] = attempt_requirement['min_accuracy_rate']
        if attempt_requirement.get('max_total_time') is not None:
            data['max_total_time'] = attempt_requirement['max_total_time']
        return data

    @staticmethod
    def _validate_completion_rule(obj: ChallengeLevelParam) -> None:
        """
        校验通关规则

        :param obj: 关卡配置
        :return:
        """
        if obj.completion_rule is None:
            return
        if obj.completion_rule.mode == 'single_attempt' and obj.completion_rule.required_attempts != 1:
            raise errors.RequestError(msg='单次通关模式的要求达标次数必须为 1')
        if obj.completion_rule.mode == 'consecutive_attempts' and obj.completion_rule.required_attempts < 2:
            raise errors.RequestError(msg='连续达标模式的要求达标次数不能小于 2')
        if (
            obj.completion_rule.mode == 'single_attempt'
            and obj.completion_rule.attempt_requirements
        ):
            raise errors.RequestError(msg='单次通关模式不能配置分次达标要求')
        if len(obj.completion_rule.attempt_requirements) > obj.completion_rule.required_attempts:
            raise errors.RequestError(msg='分次达标要求数量不能超过要求达标次数')

    @staticmethod
    def _validate_level_config(obj: ChallengeLevelParam) -> None:
        """
        校验关卡配置

        :param obj: 关卡配置
        :return:
        """
        if obj.star_two_rate < obj.pass_rate:
            raise errors.RequestError(msg='二星正确率不能低于通关正确率')
        if obj.star_three_rate < obj.star_two_rate:
            raise errors.RequestError(msg='三星正确率不能低于二星正确率')
        ChallengeService._validate_completion_rule(obj)

        enabled_sections = [item for item in obj.sections if item.enabled]
        total_count = sum(item.question_count for item in enabled_sections)
        if total_count != obj.question_count:
            raise errors.RequestError(msg=f'启用分组题量合计为 {total_count}，必须等于关卡题量 {obj.question_count}')

        seen_seq: set[int] = set()
        for section in obj.sections:
            if section.seq_no in seen_seq:
                raise errors.RequestError(msg=f'分组顺序 {section.seq_no} 重复')
            seen_seq.add(section.seq_no)
            if section.required_correct_count is not None and section.required_correct_count > section.question_count:
                raise errors.RequestError(msg=f'分组 {section.seq_no} 最低答对数不能超过分组题量')
            ChallengeService._validate_source_config(section.source_type, section.source_config, section.question_count)

    @staticmethod
    def _validate_source_config(source_type: str, config: dict[str, Any], question_count: int) -> None:
        """
        校验题源配置

        :param source_type: 题源类型
        :param config: 题源配置
        :param question_count: 抽题数量
        :return:
        """
        if source_type == 'fixed':
            question_ids = config.get('question_ids')
            if not isinstance(question_ids, list) or len(question_ids) < question_count:
                raise errors.RequestError(msg='固定题源的 question_ids 数量不足')
            return
        if source_type == 'manual':
            questions = config.get('questions')
            if not isinstance(questions, list) or len(questions) < question_count:
                raise errors.RequestError(msg='手工题源的 questions 数量不足')
            for question in questions:
                if not isinstance(question, dict) or not question.get('stem') or 'correct_answer' not in question:
                    raise errors.RequestError(msg='手工题目必须包含 stem 和 correct_answer')
            return
        if source_type == 'generator':
            if not config.get('generator_key'):
                raise errors.RequestError(msg='生成题源必须配置 generator_key')
            return
        if source_type == 'pool':
            if str(config.get('mode') or '') == 'anchor_role_pool':
                raw_roles = config.get('anchor_roles') or config.get('roles') or config.get('concept_ids')
                if not isinstance(raw_roles, list) or not any(str(item).strip() for item in raw_roles):
                    raise errors.RequestError(msg='锚点题源必须配置 anchor_roles')
                return
            if not any(config.get(key) for key in ('bank_id', 'chapter_id', 'question_types', 'knowledge_points')):
                raise errors.RequestError(msg='题库池至少需要配置一个筛选条件')
            return
        raise errors.RequestError(msg=f'不支持的题源类型: {source_type}')

    @staticmethod
    def _section_dict(section: Any) -> dict[str, Any]:
        """
        序列化关卡分组

        :param section: 分组模型
        :return:
        """
        return {
            'id': section.id,
            'seq_no': section.seq_no,
            'name': section.name,
            'source_type': section.source_type,
            'question_count': section.question_count,
            'source_config': section.source_config or {},
            'required_correct_count': section.required_correct_count,
            'enabled': section.enabled,
        }

    @staticmethod
    def _interaction_config_from_answer_data(answer_data: dict[str, Any]) -> dict[str, Any] | None:
        """
        从答案数据提取公开交互配置

        :param answer_data: 答案数据
        :return:
        """
        config: dict[str, Any] = {}
        for key in ('left_items', 'right_items', 'left_title', 'right_title', 'nodes', 'groups', 'layout'):
            if key in answer_data:
                config[key] = answer_data[key]
        return config or None

    @staticmethod
    def _interaction_config_from_options(options: list[dict[str, Any]]) -> dict[str, Any] | None:
        """
        从选项数据提取交互配置

        :param options: 选项列表
        :return:
        """
        left_items: list[dict[str, Any]] = []
        right_items: list[dict[str, Any]] = []
        for option in options:
            if not isinstance(option, dict):
                continue
            side = str(option.get('side') or option.get('group') or '').lower()
            if side not in {'left', 'right'}:
                continue
            item = {
                'id': str(option.get('id') or option.get('option_code') or option.get('code') or ''),
                'content': str(option.get('content') or option.get('label') or ''),
            }
            if side == 'left':
                left_items.append(item)
                continue
            right_items.append(item)

        if not left_items and not right_items:
            return None
        return {
            'left_items': left_items,
            'right_items': right_items,
        }

    @staticmethod
    def _level_detail(level: ChallengeLevel) -> GetChallengeLevelDetail:
        """
        构建关卡配置详情

        :param level: 关卡模型
        :return:
        """
        return GetChallengeLevelDetail(
            id=level.id,
            challenge_key=level.challenge_key,
            stage=level.stage,
            level_no=level.level_no,
            global_no=level.global_no,
            title=level.title,
            description=level.description,
            previous_level_id=level.previous_level_id,
            question_count=level.question_count,
            time_limit=level.time_limit,
            pass_rate=level.pass_rate,
            star_two_rate=level.star_two_rate,
            star_three_rate=level.star_three_rate,
            required_section_pass=level.required_section_pass,
            completion_rule=ChallengeService._completion_rule_schema(
                ChallengeService._level_completion_rule(level),
                level.pass_rate,
            ),
            display_config=ChallengeService._public_display_config(level.display_config),
            status=level.status,
            config_version=level.config_version,
            sort_order=level.sort_order,
            sections=[GetChallengeSectionDetail(**ChallengeService._section_dict(item)) for item in level.sections],
        )

    async def get_admin_levels(
        self,
        *,
        db: AsyncSession,
        challenge_key: str | None = None,
        status: str | None = None,
    ) -> list[GetChallengeLevelDetail]:
        """
        获取管理员关卡列表

        :param db: 数据库会话
        :param challenge_key: 闯关标识
        :param status: 关卡状态
        :return:
        """
        levels = await challenge_level_dao.get_all(db, challenge_key=challenge_key, status=status)
        return [self._level_detail(item) for item in levels]

    async def get_admin_level(self, *, db: AsyncSession, level_id: int) -> GetChallengeLevelDetail:
        """
        获取管理员关卡详情

        :param db: 数据库会话
        :param level_id: 关卡 ID
        :return:
        """
        level = await challenge_level_dao.get_with_sections(db, level_id)
        if level is None:
            raise errors.NotFoundError(msg='关卡不存在')
        return self._level_detail(level)

    async def create_level(
        self,
        *,
        db: AsyncSession,
        obj: CreateChallengeLevelParam,
        user_id: int,
    ) -> GetChallengeLevelDetail:
        """
        创建关卡

        :param db: 数据库会话
        :param obj: 创建参数
        :param user_id: 管理员用户 ID
        :return:
        """
        self._validate_level_config(obj)
        existing = await challenge_level_dao.get_by_identity(db, obj.challenge_key, obj.stage, obj.level_no)
        if existing:
            raise errors.ConflictError(msg='同阶段关卡序号已存在')
        global_existing = await challenge_level_dao.get_by_global_no(db, obj.challenge_key, obj.global_no)
        if global_existing:
            raise errors.ConflictError(msg='全局关卡序号已存在')
        if obj.previous_level_id:
            previous = await challenge_level_dao.get(db, obj.previous_level_id)
            if previous is None or previous.challenge_key != obj.challenge_key:
                raise errors.RequestError(msg='前置关卡不存在或不属于同一闯关')

        data = obj.model_dump(exclude={'sections', 'completion_rule'})
        data['display_config'] = self._display_config_with_completion_rule(
            obj.display_config,
            obj.completion_rule,
            obj.pass_rate,
        )
        data.update({'status': 'draft', 'config_version': 1, 'created_by': user_id, 'updated_by': user_id})
        level = await challenge_level_dao.create(db, data)
        await challenge_level_dao.replace_sections(
            db,
            level.id,
            [item.model_dump() for item in obj.sections],
        )
        detail = await challenge_level_dao.get_with_sections(db, level.id)
        if detail is None:
            raise errors.ServerError(msg='创建关卡后读取失败')
        return self._level_detail(detail)

    async def update_level(
        self,
        *,
        db: AsyncSession,
        level_id: int,
        obj: UpdateChallengeLevelParam,
        user_id: int,
    ) -> GetChallengeLevelDetail:
        """
        更新关卡

        :param db: 数据库会话
        :param level_id: 关卡 ID
        :param obj: 更新参数
        :param user_id: 管理员用户 ID
        :return:
        """
        level = await challenge_level_dao.get_with_sections(db, level_id)
        if level is None:
            raise errors.NotFoundError(msg='关卡不存在')

        fields_set = set(obj.model_fields_set)

        def pick_value(field_name: str, current_value: Any) -> Any:
            """
            读取更新值，支持显式清空可空字段

            :param field_name: 字段名
            :param current_value: 当前值
            :return:
            """
            if field_name in fields_set:
                return getattr(obj, field_name)
            return current_value

        merged_data = {
            'challenge_key': level.challenge_key,
            'stage': level.stage,
            'level_no': level.level_no,
            'global_no': level.global_no,
            'title': pick_value('title', level.title),
            'description': pick_value('description', level.description),
            'previous_level_id': pick_value('previous_level_id', level.previous_level_id),
            'question_count': pick_value('question_count', level.question_count),
            'time_limit': pick_value('time_limit', level.time_limit),
            'pass_rate': pick_value('pass_rate', level.pass_rate),
            'star_two_rate': pick_value('star_two_rate', level.star_two_rate),
            'star_three_rate': pick_value('star_three_rate', level.star_three_rate),
            'required_section_pass': pick_value('required_section_pass', level.required_section_pass),
            'completion_rule': pick_value('completion_rule', self._level_completion_rule(level)),
            'display_config': pick_value(
                'display_config',
                self._public_display_config(level.display_config),
            ),
            'sort_order': pick_value('sort_order', level.sort_order),
            'sections': (
                obj.sections
                if obj.sections is not None
                else [
                    {
                        'seq_no': item.seq_no,
                        'name': item.name,
                        'source_type': item.source_type,
                        'question_count': item.question_count,
                        'source_config': item.source_config,
                        'required_correct_count': item.required_correct_count,
                        'enabled': item.enabled,
                    }
                    for item in level.sections
                ]
            ),
        }
        merged = ChallengeLevelParam.model_validate(merged_data)
        self._validate_level_config(merged)

        update_fields = (
            'title',
            'description',
            'previous_level_id',
            'question_count',
            'time_limit',
            'pass_rate',
            'star_two_rate',
            'star_three_rate',
            'required_section_pass',
            'display_config',
            'sort_order',
            'status',
        )
        update_data = {field: getattr(obj, field) for field in update_fields if field in fields_set}
        if 'display_config' in fields_set or 'completion_rule' in fields_set or 'pass_rate' in fields_set:
            public_display_config = pick_value(
                'display_config',
                self._public_display_config(level.display_config),
            )
            completion_rule = pick_value('completion_rule', self._level_completion_rule(level))
            update_data['display_config'] = self._display_config_with_completion_rule(
                public_display_config,
                completion_rule,
                merged.pass_rate,
            )
        update_data['updated_by'] = user_id
        update_data['config_version'] = level.config_version + 1
        if level.status == 'published' and 'status' not in update_data:
            update_data['status'] = 'draft'
        await challenge_level_dao.update(db, level_id, update_data)
        if obj.sections is not None:
            await challenge_level_dao.replace_sections(
                db,
                level_id,
                [item.model_dump() for item in obj.sections],
            )

        detail = await challenge_level_dao.get_with_sections(db, level_id)
        if detail is None:
            raise errors.ServerError(msg='更新关卡后读取失败')
        return self._level_detail(detail)

    async def publish_level(
        self,
        *,
        db: AsyncSession,
        level_id: int,
        user_id: int,
    ) -> GetChallengeLevelDetail:
        """
        发布关卡

        :param db: 数据库会话
        :param level_id: 关卡 ID
        :param user_id: 管理员用户 ID
        :return:
        """
        level = await challenge_level_dao.get_with_sections(db, level_id)
        if level is None:
            raise errors.NotFoundError(msg='关卡不存在')
        validation_data = self._level_detail(level).model_dump(exclude={'id', 'status', 'config_version'})
        validation_data['sections'] = [
            {key: value for key, value in item.items() if key != 'id'} for item in validation_data['sections']
        ]
        self._validate_level_config(ChallengeLevelParam.model_validate(validation_data))
        await challenge_level_dao.update(db, level_id, {'status': 'published', 'updated_by': user_id})
        detail = await challenge_level_dao.get_with_sections(db, level_id)
        if detail is None:
            raise errors.ServerError(msg='发布关卡后读取失败')
        return self._level_detail(detail)

    async def get_map(
        self,
        *,
        db: AsyncSession,
        user_id: int,
        challenge_key: str,
    ) -> GetChallengeMapResponse:
        """
        获取用户闯关地图

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param challenge_key: 闯关标识
        :return:
        """
        levels = await challenge_level_dao.get_all(db, challenge_key=challenge_key, status='published')
        progress_map = await user_challenge_progress_dao.get_by_levels(db, user_id, [item.id for item in levels])
        stage_items: dict[str, list[GetChallengeMapLevel]] = {stage: [] for stage in STAGE_ORDER}

        for level in levels:
            progress = progress_map.get(level.id)
            previous_passed = level.previous_level_id is None
            if level.previous_level_id is not None:
                previous_progress = progress_map.get(level.previous_level_id)
                previous_passed = bool(previous_progress and previous_progress.passed)

            status = 'locked'
            if progress and progress.passed:
                status = 'cleared'
            elif previous_passed:
                status = 'active'

            stage_items.setdefault(level.stage, []).append(
                GetChallengeMapLevel(
                    id=level.id,
                    stage=level.stage,
                    level_no=level.level_no,
                    global_no=level.global_no,
                    title=level.title,
                    description=level.description,
                    question_count=level.question_count,
                    time_limit=level.time_limit,
                    pass_rate=level.pass_rate,
                    completion_rule=self._completion_rule_schema(
                        self._level_completion_rule(level),
                        level.pass_rate,
                    ),
                    status=status,
                    stars=progress.best_stars if progress else 0,
                    best_accuracy=progress.best_accuracy if progress else Decimal('0'),
                    attempt_count=progress.attempt_count if progress else 0,
                )
            )

        stages: list[GetChallengeMapStage] = []
        for stage in STAGE_ORDER:
            items = stage_items.get(stage, [])
            stages.append(
                GetChallengeMapStage(
                    stage=stage,
                    unlocked=any(item.status != 'locked' for item in items),
                    cleared_count=sum(1 for item in items if item.status == 'cleared'),
                    total_count=len(items),
                    stars=sum(item.stars for item in items),
                    levels=items,
                )
            )
        return GetChallengeMapResponse(challenge_key=challenge_key, stages=stages)

    @staticmethod
    def _question_from_database(
        question: Question,
        source_type: str,
        section_seq: int,
        interaction_override: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        转换题库题目为临时挑战题目

        :param question: 题库题目
        :param source_type: 题源类型
        :param section_seq: 分组顺序
        :param interaction_override: 交互标注覆盖
        :return:
        """
        data = question_service.serialize_question(
            question=question,
            include_analysis=True,
            include_materials=True,
        )
        options = data.get('options_data') or []
        if isinstance(options, dict):
            options = options.get('items') or []
        materials = data.get('materials') or []
        material = '\n'.join(str(item.get('content') or '') for item in materials if item.get('content')) or None
        answer_data = data.get('answer_data')
        if not isinstance(answer_data, dict):
            raise errors.RequestError(msg=f'题目 {question.id} 缺少可用答案')
        interaction_config = data.get('interaction_config')
        if not isinstance(interaction_config, dict):
            interaction_config = ChallengeService._interaction_config_from_answer_data(answer_data)
        if not isinstance(interaction_config, dict):
            interaction_config = ChallengeService._interaction_config_from_options(options)

        question_type = question.type
        stem = question.stem
        analysis = data.get('analysis_content')
        if interaction_override:
            annotation = interaction_override['annotation']
            override_config = interaction_override['interaction_config']
            answer_data = interaction_override['answer_data']
            question_type = str(annotation.interaction_type)
            stem = str(override_config.get('instruction') or question.stem)
            interaction_config = {
                **override_config,
                'source_question': {
                    'id': question.id,
                    'type': question.type,
                    'stem': question.stem,
                },
            }
            options = []
            config_analysis = annotation.config.get('analysis') if isinstance(annotation.config, dict) else None
            analysis = str(config_analysis) if config_analysis else analysis

        return {
            'section_seq': section_seq,
            'source_type': source_type,
            'source_ref_id': question.id,
            'type': question_type,
            'stem': stem,
            'material': material,
            'options': [
                {
                    'option_code': str(item.get('option_code') or item.get('code') or ''),
                    'content': str(item.get('content') or ''),
                }
                for item in options
                if isinstance(item, dict)
            ],
            'interaction_config': interaction_config,
            'difficulty': str(question.difficulty) if question.difficulty is not None else None,
            'full_score': str(question.default_score),
            'answer_data': answer_data,
            'analysis': analysis,
        }

    async def _questions_from_database(
        self,
        *,
        db: AsyncSession,
        questions: Sequence[Question],
        source_type: str,
        section_seq: int,
        interaction_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        转换题库题目为临时挑战题目列表

        :param db: 数据库会话
        :param questions: 题库题目列表
        :param source_type: 题源类型
        :param section_seq: 分组顺序
        :param interaction_type: 交互类型
        :return:
        """
        overrides: dict[int, dict[str, Any]] = {}
        if interaction_type:
            question_ids = [question.id for question in questions]
            overrides = await interaction_annotation_service.get_default_runtime_configs(
                db=db,
                question_ids=question_ids,
                interaction_type=interaction_type,
            )
            missing_ids = [question.id for question in questions if question.id not in overrides]
            if missing_ids:
                raise errors.RequestError(msg=f'题目缺少 {interaction_type} 交互标注: {missing_ids}')

        return [
            self._question_from_database(
                question,
                source_type,
                section_seq,
                interaction_override=overrides.get(question.id),
            )
            for question in questions
        ]

    @staticmethod
    def _question_from_manual(question: dict[str, Any], section_seq: int) -> dict[str, Any]:
        """
        转换管理员手工题目

        :param question: 手工题目配置
        :param section_seq: 分组顺序
        :return:
        """
        question_type = str(question.get('type') or 'single')
        correct_answer = question.get('correct_answer')
        answer_data = correct_answer if isinstance(correct_answer, dict) else {'correct': correct_answer}
        raw_options = question.get('options') or []
        interaction_config = question.get('interaction_config')
        if not isinstance(interaction_config, dict):
            interaction_config = ChallengeService._interaction_config_from_answer_data(answer_data)
        options = []
        for index, item in enumerate(raw_options):
            if isinstance(item, dict):
                options.append(
                    {
                        'option_code': str(item.get('option_code') or item.get('code') or chr(65 + index)),
                        'content': str(item.get('content') or item.get('label') or ''),
                    }
                )
            else:
                options.append({'option_code': chr(65 + index), 'content': str(item)})
        return {
            'section_seq': section_seq,
            'source_type': 'manual',
            'source_ref_id': None,
            'type': question_type,
            'stem': str(question.get('stem') or ''),
            'material': str(question.get('material')) if question.get('material') else None,
            'options': options,
            'interaction_config': interaction_config,
            'difficulty': str(question.get('difficulty')) if question.get('difficulty') is not None else None,
            'full_score': str(question.get('full_score') or '1'),
            'answer_data': answer_data,
            'analysis': str(question.get('analysis')) if question.get('analysis') else None,
        }

    @staticmethod
    def _anchor_role_display_name(role: str) -> str:
        """
        获取锚点角色展示名

        :param role: 锚点角色
        :return:
        """
        return DATA_ANALYSIS_ANCHOR_ROLE_NAMES.get(role, role)

    @staticmethod
    def _normalize_anchor_display_scope(value: Any) -> str:
        """
        规范化锚点题展示范围

        :param value: 原始范围
        :return:
        """
        scope = str(value or 'block').strip()
        if scope in ANCHOR_DISPLAY_SCOPES:
            return scope
        return 'block'

    @staticmethod
    def _get_block_id(block: dict[str, Any]) -> str:
        """
        获取材料块 ID

        :param block: 材料块
        :return:
        """
        return str(block.get('block_id') or block.get('id') or block.get('key') or '').strip()

    @classmethod
    def _find_anchor_block(
        cls,
        *,
        blocks: list[dict[str, Any]],
        anchor: MaterialAnchor,
    ) -> dict[str, Any] | None:
        """
        查找锚点所在材料块

        :param blocks: 材料块列表
        :param anchor: 材料锚点
        :return:
        """
        anchor_block_id = str(anchor.block_id or '').strip()
        if not anchor_block_id:
            return None
        for block in blocks:
            if cls._get_block_id(block) == anchor_block_id:
                return block
        return None

    @staticmethod
    def _sentence_range_for_anchor(
        *,
        content: str,
        anchor: MaterialAnchor,
    ) -> tuple[int, int] | None:
        """
        获取锚点所在句子范围

        :param content: 文本块内容
        :param anchor: 材料锚点
        :return:
        """
        if anchor.start_offset is None or anchor.end_offset is None:
            return None
        if anchor.start_offset < 0 or anchor.end_offset <= anchor.start_offset:
            return None
        if anchor.start_offset >= len(content):
            return None

        sentence_marks = '。！？；.!?;\n'
        start = 0
        for index in range(anchor.start_offset - 1, -1, -1):
            if content[index] in sentence_marks:
                start = index + 1
                break

        end = len(content)
        for index in range(anchor.end_offset, len(content)):
            if content[index] in sentence_marks:
                end = index + 1
                break

        while start < end and content[start].isspace():
            start += 1
        while end > start and content[end - 1].isspace():
            end -= 1
        if end <= start:
            return None
        return start, end

    @staticmethod
    def _anchor_in_text_range(anchor: MaterialAnchor, *, block_id: str, start: int, end: int) -> bool:
        """
        判断锚点是否在文本范围内

        :param anchor: 材料锚点
        :param block_id: 材料块 ID
        :param start: 起始偏移
        :param end: 结束偏移
        :return:
        """
        if str(anchor.block_id or '').strip() != block_id:
            return False
        if anchor.start_offset is None or anchor.end_offset is None:
            return False
        return anchor.start_offset >= start and anchor.end_offset <= end

    @classmethod
    def _scope_anchor_candidates(
        cls,
        *,
        target_anchor: MaterialAnchor,
        anchors: Sequence[MaterialAnchor],
        target_block: dict[str, Any] | None,
        display_scope: str,
    ) -> Sequence[MaterialAnchor]:
        """
        按展示范围过滤候选锚点

        :param target_anchor: 正确锚点
        :param anchors: 候选锚点
        :param target_block: 正确锚点所在块
        :param display_scope: 展示范围
        :return:
        """
        if display_scope == 'material' or target_block is None:
            return anchors

        block_id = cls._get_block_id(target_block)
        if not block_id:
            return anchors

        if display_scope == 'block':
            return [item for item in anchors if str(item.block_id or '').strip() == block_id]

        content = str(target_block.get('content') or target_block.get('text') or '')
        sentence_range = cls._sentence_range_for_anchor(content=content, anchor=target_anchor)
        if sentence_range is None:
            return [item for item in anchors if str(item.block_id or '').strip() == block_id]

        start, end = sentence_range
        return [
            item
            for item in anchors
            if cls._anchor_in_text_range(item, block_id=block_id, start=start, end=end)
        ]

    @classmethod
    def _build_anchor_scope_blocks(
        cls,
        *,
        blocks: list[dict[str, Any]],
        target_anchor: MaterialAnchor,
        target_block: dict[str, Any] | None,
        display_scope: str,
    ) -> list[dict[str, Any]]:
        """
        构建锚点题展示块

        :param blocks: 原始材料块
        :param target_anchor: 正确锚点
        :param target_block: 正确锚点所在块
        :param display_scope: 展示范围
        :return:
        """
        if display_scope == 'material' or target_block is None:
            return blocks

        block = dict(target_block)
        if display_scope == 'block':
            return [block]

        content = str(block.get('content') or block.get('text') or '')
        sentence_range = cls._sentence_range_for_anchor(content=content, anchor=target_anchor)
        if sentence_range is None:
            return [block]

        start, end = sentence_range
        block['content'] = content[start:end]
        block['start_offset'] = start
        block['title'] = '题干句子'
        return [block]

    @staticmethod
    def _anchor_scope_material_text(
        *,
        material: QuestionMaterial,
        blocks: list[dict[str, Any]],
        display_scope: str,
    ) -> str:
        """
        构建锚点题材料文本

        :param material: 材料
        :param blocks: 展示块
        :param display_scope: 展示范围
        :return:
        """
        if display_scope == 'material':
            return material.content

        texts = [
            str(block.get('content') or block.get('text') or block.get('title') or '').strip()
            for block in blocks
        ]
        return '\n'.join(item for item in texts if item) or material.content

    @staticmethod
    def _annotation_anchor_roles(annotation: QuestionInteractionAnnotation) -> dict[str, str]:
        """
        读取题目标注中的锚点角色映射

        :param annotation: 题目交互标注
        :return:
        """
        config = annotation.config if isinstance(annotation.config, dict) else {}
        raw_roles = config.get('anchor_roles')
        if not isinstance(raw_roles, dict):
            return {}
        return {
            str(anchor_id): str(role)
            for anchor_id, role in raw_roles.items()
            if str(anchor_id).isdigit() and str(role).strip()
        }

    @staticmethod
    def _annotation_answer_anchor_ids(annotation: QuestionInteractionAnnotation) -> set[int]:
        """
        读取题目标注的正确锚点 ID

        :param annotation: 题目交互标注
        :return:
        """
        answer_data = annotation.answer_data if isinstance(annotation.answer_data, dict) else {}
        return interaction_annotation_service._extract_anchor_ids(answer_data.get('correct'))

    async def _question_from_annotation_role(
        self,
        *,
        db: AsyncSession,
        annotation: QuestionInteractionAnnotation,
        material: QuestionMaterial,
        role: str,
        section_seq: int,
        min_candidates: int,
        display_scope: str,
    ) -> dict[str, Any] | None:
        """
        使用题目标注中的角色映射构建定位题

        :param db: 数据库会话
        :param annotation: 题目交互标注
        :param material: 材料
        :param role: 目标角色
        :param section_seq: 分组顺序
        :param min_candidates: 最少候选锚点数量
        :param display_scope: 展示范围
        :return:
        """
        anchor_roles = self._annotation_anchor_roles(annotation)
        answer_anchor_ids = self._annotation_answer_anchor_ids(annotation)
        target_ids = [
            int(anchor_id)
            for anchor_id, mapped_role in anchor_roles.items()
            if mapped_role == role and int(anchor_id) in answer_anchor_ids
        ]
        if not target_ids:
            target_ids = [int(anchor_id) for anchor_id, mapped_role in anchor_roles.items() if mapped_role == role]
        if not target_ids:
            return None

        candidate_ids = [int(item) for item in annotation.candidate_anchor_ids if str(item).isdigit()]
        if not candidate_ids:
            candidates = await challenge_question_source_dao.get_material_anchor_candidates(
                db=db,
                material_id=material.id,
                roles=[],
            )
        else:
            candidates = await material_anchor_dao.get_by_ids(db, candidate_ids)
        candidate_map = {item.id: item for item in candidates if item.material_id == material.id and item.status == 10}
        target_anchor = next((candidate_map.get(anchor_id) for anchor_id in target_ids), None)
        if target_anchor is None:
            return None

        ordered_candidates = [candidate_map[anchor_id] for anchor_id in candidate_ids if anchor_id in candidate_map]
        if not ordered_candidates:
            ordered_candidates = list(candidate_map.values())

        blocks = interaction_annotation_service.build_material_blocks(material.content, title=material.title)
        target_block = self._find_anchor_block(blocks=blocks, anchor=target_anchor)
        scoped_candidates = self._scope_anchor_candidates(
            target_anchor=target_anchor,
            anchors=ordered_candidates,
            target_block=target_block,
            display_scope=display_scope,
        )
        selected_anchors = list(scoped_candidates)
        if target_anchor.id not in {item.id for item in selected_anchors}:
            selected_anchors.insert(0, target_anchor)
        if len(selected_anchors) < min_candidates:
            return None

        role_name = self._anchor_role_display_name(role)
        content_hash = annotation.content_hash or interaction_annotation_service.build_content_hash(material.content)
        scoped_blocks = self._build_anchor_scope_blocks(
            blocks=blocks,
            target_anchor=target_anchor,
            target_block=target_block,
            display_scope=display_scope,
        )
        material_text = self._anchor_scope_material_text(
            material=material,
            blocks=scoped_blocks,
            display_scope=display_scope,
        )
        anchors_payload = []
        for item in selected_anchors:
            payload = interaction_annotation_service._anchor_to_dict(item)
            payload['role'] = anchor_roles.get(str(item.id))
            anchors_payload.append(payload)

        instruction = annotation.instruction or f'请在题干中选出“{role_name}”对应的数据。'
        interaction_config = dict(annotation.config or {})
        interaction_config.update(
            {
                'concept_id': role,
                'concept_name': role_name,
                'display_scope': display_scope,
                'source': 'question_annotation_anchor_role_pool',
            }
        )
        return {
            'section_seq': section_seq,
            'source_type': 'pool',
            'source_ref_id': annotation.id,
            'type': 'anchorLocate',
            'stem': instruction,
            'material': material_text,
            'options': [],
            'interaction_config': {
                'annotation_id': annotation.id,
                'annotation_key': annotation.annotation_key,
                'interaction_type': annotation.interaction_type,
                'title': annotation.title or role_name,
                'instruction': instruction,
                'selection_mode': annotation.selection_mode,
                'material_id': material.id,
                'material': {
                    'id': material.id,
                    'title': material.title,
                    'content': material_text,
                    'content_hash': content_hash,
                    'blocks': scoped_blocks,
                },
                'anchors': anchors_payload,
                'candidate_anchor_ids': [item.id for item in selected_anchors],
                'config': interaction_config,
            },
            'difficulty': None,
            'full_score': '1',
            'answer_data': {'correct': str(target_anchor.id)},
            'analysis': f'{role_name}对应本题标注的锚点。',
        }

    async def _questions_from_anchor_role_pool(
        self,
        *,
        db: AsyncSession,
        section: Any,
        config: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """
        从材料锚点角色池构建题目

        :param db: 数据库会话
        :param section: 题目分组
        :param config: 题源配置
        :return:
        """
        raw_roles = config.get('anchor_roles') or config.get('roles') or config.get('concept_ids') or []
        roles = [str(item).strip() for item in raw_roles if str(item).strip()]
        if not roles:
            raise errors.RequestError(msg='锚点题源必须配置 anchor_roles')

        material_ids = [int(item) for item in config.get('material_ids') or [] if str(item).isdigit()]
        bank_id = int(config['bank_id']) if config.get('bank_id') else None
        min_candidates = int(config.get('min_candidates') or min(len(roles), 2))
        display_scope = self._normalize_anchor_display_scope(config.get('display_scope'))
        questions: list[dict[str, Any]] = []
        used_annotation_ids: list[int] = []

        for question_index in range(section.question_count):
            role = roles[question_index % len(roles)]
            rejected_annotation_ids: list[int] = []
            question = None
            for _ in range(20):
                result = await challenge_question_source_dao.get_random_annotation_by_anchor_role(
                    db=db,
                    role=role,
                    bank_id=bank_id,
                    material_ids=material_ids,
                    exclude_annotation_ids=[*used_annotation_ids, *rejected_annotation_ids],
                )
                if result is None:
                    break

                annotation, material = result
                question = await self._question_from_annotation_role(
                    db=db,
                    annotation=annotation,
                    material=material,
                    role=role,
                    section_seq=section.seq_no,
                    min_candidates=min_candidates,
                    display_scope=display_scope,
                )
                if question:
                    used_annotation_ids.append(annotation.id)
                    break
                rejected_annotation_ids.append(annotation.id)

            if question is None:
                role_name = self._anchor_role_display_name(role)
                raise errors.RequestError(msg=f'锚点题源中“{role_name}”可用题目不足')

            questions.append(question)

        return questions

    async def _build_section_questions(
        self,
        *,
        db: AsyncSession,
        level: ChallengeLevel,
        section: Any,
        used_question_ids: list[int],
    ) -> list[dict[str, Any]]:
        """
        构建单个题目分组

        :param db: 数据库会话
        :param level: 关卡配置
        :param section: 题目分组
        :param used_question_ids: 已使用题目 ID
        :return:
        """
        config = section.source_config or {}
        if section.source_type == 'generator':
            generator_key = str(config.get('generator_key') or '')
            params = config.get('params') if isinstance(config.get('params'), dict) else {}
            questions: list[dict[str, Any]] = []
            for question_index in range(section.question_count):
                generator_params = {
                    **params,
                    'question_index': question_index,
                    'question_count': section.question_count,
                }
                questions.append(
                    {
                        'section_seq': section.seq_no,
                        'source_type': 'generator',
                        'source_ref_id': None,
                        **generate_challenge_question(
                            generator_key=generator_key,
                            stage=level.stage,
                            params=generator_params,
                        ),
                    }
                )
            return questions

        if section.source_type == 'manual':
            questions = config.get('questions') or []
            return [self._question_from_manual(item, section.seq_no) for item in questions[: section.question_count]]

        if section.source_type == 'fixed':
            raw_ids = config.get('question_ids') or []
            interaction_type = str(config.get('interaction_type') or '').strip() or None
            question_ids = [int(item) for item in raw_ids if str(item).isdigit()][: section.question_count]
            questions = await question_dao.get_by_ids(
                db,
                question_ids,
                include_analysis=True,
                include_materials=True,
            )
            if len(questions) != section.question_count:
                raise errors.RequestError(msg=f'关卡 {level.title} 的固定题目数量不足')
            used_question_ids.extend(question.id for question in questions)
            return await self._questions_from_database(
                db=db,
                questions=questions,
                source_type='fixed',
                section_seq=section.seq_no,
                interaction_type=interaction_type,
            )

        if section.source_type == 'pool':
            if str(config.get('mode') or '') == 'anchor_role_pool':
                return await self._questions_from_anchor_role_pool(
                    db=db,
                    section=section,
                    config=config,
                )

            interaction_type = str(config.get('interaction_type') or '').strip() or None
            difficulty_min = (
                self._decimal(config.get('difficulty_min'))
                if config.get('difficulty_min') is not None
                else None
            )
            difficulty_max = (
                self._decimal(config.get('difficulty_max'))
                if config.get('difficulty_max') is not None
                else None
            )
            questions = await challenge_question_source_dao.get_pool_questions(
                db=db,
                count=section.question_count,
                bank_id=int(config['bank_id']) if config.get('bank_id') else None,
                chapter_id=int(config['chapter_id']) if config.get('chapter_id') else None,
                question_types=[str(item) for item in config.get('question_types') or []] or None,
                difficulty_min=difficulty_min,
                difficulty_max=difficulty_max,
                knowledge_points=[str(item) for item in config.get('knowledge_points') or []] or None,
                exclude_ids=used_question_ids,
            )
            if len(questions) != section.question_count:
                raise errors.RequestError(msg=f'关卡 {level.title} 的题库候选题数量不足')
            used_question_ids.extend(question.id for question in questions)
            return await self._questions_from_database(
                db=db,
                questions=questions,
                source_type='pool',
                section_seq=section.seq_no,
                interaction_type=interaction_type,
            )

        raise errors.RequestError(msg=f'不支持的题源类型: {section.source_type}')

    async def _build_attempt_questions(
        self,
        *,
        db: AsyncSession,
        level: ChallengeLevel,
    ) -> list[dict[str, Any]]:
        """
        即时生成关卡题目

        :param db: 数据库会话
        :param level: 关卡配置
        :return:
        """
        questions: list[dict[str, Any]] = []
        used_question_ids: list[int] = []
        enabled_sections = [item for item in level.sections if item.enabled]
        for section in enabled_sections:
            section_questions = await self._build_section_questions(
                db=db,
                level=level,
                section=section,
                used_question_ids=used_question_ids,
            )
            questions.extend(section_questions)
        if len(questions) != level.question_count:
            raise errors.RequestError(
                msg=f'关卡实际生成 {len(questions)} 题，与配置的 {level.question_count} 题不一致'
            )
        for index, item in enumerate(questions, start=1):
            item['seq_no'] = index
        return questions

    @staticmethod
    def _public_question(item: dict[str, Any]) -> ChallengeQuestionItem:
        """
        构建不含答案的题目响应

        :param item: Redis 临时题目
        :return:
        """
        return ChallengeQuestionItem(
            seq_no=int(item['seq_no']),
            section_seq=int(item['section_seq']),
            type=item['type'],
            stem=item['stem'],
            material=item.get('material'),
            options=[ChallengeQuestionOption(**option) for option in item.get('options') or []],
            interaction_config=(
                item.get('interaction_config') if isinstance(item.get('interaction_config'), dict) else None
            ),
            difficulty=(
                ChallengeService._decimal(item.get('difficulty')) if item.get('difficulty') is not None else None
            ),
        )

    async def _load_runtime(self, attempt_key: str) -> tuple[dict[str, Any], int]:
        """
        加载 Redis 临时挑战内容

        :param attempt_key: 挑战标识
        :return:
        """
        redis_key = self._redis_key(attempt_key)
        raw = await redis_client.get(redis_key)
        if not raw:
            raise errors.RequestError(msg='本次挑战题目已过期，请重新开始')
        try:
            runtime = json.loads(raw)
        except (json.JSONDecodeError, TypeError) as exc:
            raise errors.ServerError(msg='挑战临时数据损坏') from exc
        ttl = max(0, int(await redis_client.ttl(redis_key)))
        return runtime, ttl

    async def _attempt_response(
        self,
        *,
        attempt: ChallengeAttempt,
        level: ChallengeLevel,
    ) -> GetChallengeAttemptResponse:
        """
        构建挑战会话响应

        :param attempt: 挑战记录
        :param level: 关卡配置
        :return:
        """
        runtime, ttl = await self._load_runtime(attempt.attempt_key)
        rules = attempt.rule_snapshot or {}
        completion_rule_source = rules.get('completion_rule') if rules else self._level_completion_rule(level)
        completion_rule_pass_rate = (
            self._decimal(rules.get('pass_rate'), str(level.pass_rate)) if rules else level.pass_rate
        )
        return GetChallengeAttemptResponse(
            attempt_key=attempt.attempt_key,
            level_id=level.id,
            level_title=level.title,
            stage=level.stage,
            level_no=level.level_no,
            question_count=attempt.question_count,
            time_limit=level.time_limit,
            completion_rule=self._completion_rule_schema(completion_rule_source, completion_rule_pass_rate),
            current_attempt_index=rules.get('current_attempt_index') if rules else None,
            current_attempt_requirement=self._requirement_schema(
                rules.get('current_attempt_requirement') if rules else None
            ),
            expires_in=ttl,
            questions=[self._public_question(item) for item in runtime.get('questions') or []],
        )

    async def start_attempt(
        self,
        *,
        db: AsyncSession,
        user_id: int,
        challenge_key: str,
        level_id: int,
    ) -> GetChallengeAttemptResponse:
        """
        开始关卡挑战

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param challenge_key: 闯关标识
        :param level_id: 关卡 ID
        :return:
        """
        level = await challenge_level_dao.get_with_sections(db, level_id)
        if level is None or level.challenge_key != challenge_key or level.status != 'published':
            raise errors.NotFoundError(msg='关卡不存在或尚未发布')
        if level.previous_level_id is not None:
            previous_progress = await user_challenge_progress_dao.get_by_level(db, user_id, level.previous_level_id)
            if previous_progress is None or not previous_progress.passed:
                raise errors.ForbiddenError(msg='请先通过前置关卡')

        existing = await challenge_attempt_dao.get_in_progress(db, user_id, level_id)
        if existing is not None:
            try:
                return await self._attempt_response(attempt=existing, level=level)
            except errors.RequestError:
                await challenge_attempt_dao.update(db, existing.id, {'status': 'abandoned'})

        questions = await self._build_attempt_questions(db=db, level=level)
        attempt_key = uuid4().hex
        completion_rule = self._completion_rule_payload(self._level_completion_rule(level), level.pass_rate)
        current_attempt_index = await self._next_attempt_index(
            db=db,
            user_id=user_id,
            level_id=level.id,
            completion_rule=completion_rule,
        )
        current_attempt_requirement = self._attempt_requirement_for_index(
            completion_rule,
            current_attempt_index,
        )
        rule_snapshot = {
            'pass_rate': str(level.pass_rate),
            'star_two_rate': str(level.star_two_rate),
            'star_three_rate': str(level.star_three_rate),
            'required_section_pass': level.required_section_pass,
            'completion_rule': completion_rule,
            'current_attempt_index': current_attempt_index,
            'current_attempt_requirement': current_attempt_requirement,
            'sections': [
                {
                    'seq_no': item.seq_no,
                    'required_correct_count': item.required_correct_count,
                }
                for item in level.sections
                if item.enabled
            ],
        }
        attempt = await challenge_attempt_dao.create(
            db,
            {
                'attempt_key': attempt_key,
                'user_id': user_id,
                'level_id': level.id,
                'level_version': level.config_version,
                'question_count': len(questions),
                'rule_snapshot': rule_snapshot,
            },
        )
        runtime = {
            'attempt_key': attempt_key,
            'user_id': user_id,
            'level_id': level.id,
            'level_version': level.config_version,
            'questions': questions,
        }
        await redis_client.set(
            self._redis_key(attempt_key),
            json.dumps(runtime, ensure_ascii=False, default=str),
            ex=CHALLENGE_ATTEMPT_TTL,
        )
        return await self._attempt_response(attempt=attempt, level=level)

    async def get_attempt(
        self,
        *,
        db: AsyncSession,
        user_id: int,
        attempt_key: str,
    ) -> GetChallengeAttemptResponse:
        """
        获取挑战会话

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param attempt_key: 挑战标识
        :return:
        """
        attempt = await challenge_attempt_dao.get_by_key(db, attempt_key)
        if attempt is None or attempt.user_id != user_id:
            raise errors.NotFoundError(msg='挑战会话不存在')
        if attempt.status != 'in_progress':
            raise errors.RequestError(msg='挑战会话已结束')
        level = await challenge_level_dao.get(db, attempt.level_id)
        if level is None:
            raise errors.NotFoundError(msg='关卡不存在')
        return await self._attempt_response(attempt=attempt, level=level)

    @staticmethod
    def _calculate_stars(accuracy: Decimal, rules: dict[str, Any], qualified: bool) -> int:
        """
        计算挑战星级

        :param accuracy: 正确率
        :param rules: 通关规则
        :param qualified: 本次是否达标
        :return:
        """
        if not qualified:
            return 0
        if accuracy >= ChallengeService._decimal(rules.get('star_three_rate'), '100'):
            return 3
        if accuracy >= ChallengeService._decimal(rules.get('star_two_rate'), '90'):
            return 2
        return 1

    @staticmethod
    def _section_passed(
        section_correct: dict[int, int],
        rules: dict[str, Any],
    ) -> bool:
        """
        判断题目分组是否达标

        :param section_correct: 分组答对数量
        :param rules: 通关规则
        :return:
        """
        if not rules.get('required_section_pass'):
            return True
        for section in rules.get('sections') or []:
            required = section.get('required_correct_count')
            if required is None:
                continue
            if section_correct.get(int(section['seq_no']), 0) < int(required):
                return False
        return True

    @staticmethod
    def _current_attempt_qualified(
        *,
        accuracy: Decimal,
        total_time: int,
        section_correct: dict[int, int],
        rules: dict[str, Any],
        current_attempt_requirement: dict[str, Any] | None = None,
    ) -> bool:
        """
        判断本次挑战是否达标

        :param accuracy: 正确率
        :param total_time: 总用时
        :param section_correct: 分组答对数量
        :param rules: 通关规则快照
        :param current_attempt_requirement: 本次单独达标要求
        :return:
        """
        completion_rule = ChallengeService._completion_rule_from_snapshot(rules)
        completion_rule = ChallengeService._completion_rule_with_attempt_requirement(
            completion_rule,
            current_attempt_requirement,
        )
        if accuracy < ChallengeService._decimal(completion_rule.get('min_accuracy_rate'), '80'):
            return False

        max_total_time = completion_rule.get('max_total_time')
        if max_total_time is not None and total_time > int(max_total_time):
            return False

        return ChallengeService._section_passed(section_correct, rules)

    @staticmethod
    def _qualified_streak(attempts: list[ChallengeAttempt]) -> int:
        """
        统计最近连续达标次数

        :param attempts: 最近完成记录
        :return:
        """
        qualified_count = 0
        for attempt in attempts:
            if not getattr(attempt, 'passed', False):
                break
            qualified_count += 1
        return qualified_count

    async def _next_attempt_index(
        self,
        *,
        db: AsyncSession,
        user_id: int,
        level_id: int,
        completion_rule: dict[str, Any],
    ) -> int | None:
        """
        计算下一次连续达标序号

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param level_id: 关卡 ID
        :param completion_rule: 通关规则
        :return:
        """
        if completion_rule.get('mode') != 'consecutive_attempts':
            return None

        required_attempts = int(completion_rule.get('required_attempts') or 1)
        previous_attempts = await challenge_attempt_dao.get_recent_completed(
            db,
            user_id,
            level_id,
            max(required_attempts - 1, 0),
        )
        previous_qualified_attempts = self._qualified_streak(previous_attempts)
        if previous_qualified_attempts >= required_attempts:
            return required_attempts
        return previous_qualified_attempts + 1

    async def _evaluate_level_passed(
        self,
        *,
        db: AsyncSession,
        attempt: ChallengeAttempt,
        current_attempt_qualified: bool,
        completion_rule: dict[str, Any],
    ) -> tuple[bool, int, int]:
        """
        评估关卡是否最终通过

        :param db: 数据库会话
        :param attempt: 挑战记录
        :param current_attempt_qualified: 本次是否达标
        :param completion_rule: 通关规则
        :return:
        """
        required_attempts = int(completion_rule['required_attempts'])
        if completion_rule['mode'] == 'single_attempt':
            qualified_attempts = 1 if current_attempt_qualified else 0
            return current_attempt_qualified, qualified_attempts, required_attempts

        if not current_attempt_qualified:
            return False, 0, required_attempts

        recent_attempts = await challenge_attempt_dao.get_recent_completed(
            db,
            attempt.user_id,
            attempt.level_id,
            required_attempts,
        )
        qualified_attempts = self._qualified_streak(recent_attempts)
        return qualified_attempts >= required_attempts, qualified_attempts, required_attempts

    async def _update_progress(
        self,
        *,
        db: AsyncSession,
        attempt: ChallengeAttempt,
        passed: bool,
        current_attempt_qualified: bool,
        stars: int,
        accuracy: Decimal,
        total_time: int,
    ) -> UserChallengeProgress:
        """
        更新用户关卡最佳进度

        :param db: 数据库会话
        :param attempt: 挑战记录
        :param passed: 是否通关
        :param current_attempt_qualified: 本次挑战是否达标
        :param stars: 星级
        :param accuracy: 正确率
        :param total_time: 总用时
        :return:
        """
        progress = await user_challenge_progress_dao.get_by_level(
            db,
            attempt.user_id,
            attempt.level_id,
            for_update=True,
        )
        now = timezone.now()
        if progress is None:
            return await user_challenge_progress_dao.create(
                db,
                {
                    'user_id': attempt.user_id,
                    'level_id': attempt.level_id,
                    'passed': passed,
                    'best_stars': stars,
                    'best_accuracy': accuracy,
                    'best_time': total_time if current_attempt_qualified else None,
                    'attempt_count': 1,
                    'last_attempt_id': attempt.id,
                    'passed_at': now if passed else None,
                },
            )

        best_time = progress.best_time
        if current_attempt_qualified and (best_time is None or total_time < best_time):
            best_time = total_time
        update_data = {
            'passed': progress.passed or passed,
            'best_stars': max(progress.best_stars, stars),
            'best_accuracy': max(progress.best_accuracy, accuracy),
            'best_time': best_time,
            'attempt_count': progress.attempt_count + 1,
            'last_attempt_id': attempt.id,
            'passed_at': progress.passed_at or (now if passed else None),
        }
        await user_challenge_progress_dao.update(db, progress.id, update_data)
        for key, value in update_data.items():
            setattr(progress, key, value)
        return progress

    async def submit_attempt(
        self,
        *,
        db: AsyncSession,
        user_id: int,
        attempt_key: str,
        obj: SubmitChallengeAttemptParam,
    ) -> SubmitChallengeAttemptResult:
        """
        提交关卡挑战

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param attempt_key: 挑战标识
        :param obj: 提交参数
        :return:
        """
        attempt = await challenge_attempt_dao.get_by_key(db, attempt_key, for_update=True)
        if attempt is None or attempt.user_id != user_id:
            raise errors.NotFoundError(msg='挑战会话不存在')
        if attempt.status == 'completed':
            return await self._completed_result(db=db, attempt=attempt)
        if attempt.status != 'in_progress':
            raise errors.RequestError(msg='挑战会话已失效')

        runtime, _ = await self._load_runtime(attempt_key)
        questions = runtime.get('questions') or []
        answers = {item.seq_no: item for item in obj.answers}
        if len(answers) != len(obj.answers):
            raise errors.RequestError(msg='题目序号重复')
        expected_seq = {int(item['seq_no']) for item in questions}
        if set(answers) != expected_seq:
            raise errors.RequestError(msg='请完成全部题目后再提交')

        correct_count = 0
        section_correct: dict[int, int] = {}
        results: list[ChallengeAnswerResult] = []
        for question in questions:
            seq_no = int(question['seq_no'])
            answer = answers[seq_no]
            answer_data = question.get('answer_data') or {}
            is_correct = question_service.check_answer(question['type'], answer.user_answer, answer_data)
            if is_correct:
                correct_count += 1
                section_seq = int(question['section_seq'])
                section_correct[section_seq] = section_correct.get(section_seq, 0) + 1
            results.append(
                ChallengeAnswerResult(
                    seq_no=seq_no,
                    is_correct=is_correct,
                    correct_answer=answer_data.get('correct', ''),
                    analysis=question.get('analysis'),
                )
            )

        completed_count = len(questions)
        wrong_count = completed_count - correct_count
        accuracy = (
            Decimal(str(round(correct_count / completed_count * 100, 2))) if completed_count else Decimal('0')
        )
        rules = attempt.rule_snapshot or {}
        completion_rule = self._completion_rule_from_snapshot(rules)
        current_attempt_requirement = rules.get('current_attempt_requirement')
        if not isinstance(current_attempt_requirement, dict):
            current_attempt_requirement = self._attempt_requirement_for_index(
                completion_rule,
                int(rules.get('current_attempt_index') or 0) or None,
            )
        current_attempt_qualified = self._current_attempt_qualified(
            accuracy=accuracy,
            total_time=obj.total_time,
            section_correct=section_correct,
            rules=rules,
            current_attempt_requirement=current_attempt_requirement,
        )
        stars = self._calculate_stars(accuracy, rules, current_attempt_qualified)
        completed_at = timezone.now()

        update_data = {
            'status': 'completed',
            'completed_count': completed_count,
            'correct_count': correct_count,
            'wrong_count': wrong_count,
            'accuracy_rate': accuracy,
            'stars': stars,
            'passed': current_attempt_qualified,
            'total_time': obj.total_time,
            'completed_at': completed_at,
        }
        await challenge_attempt_dao.update(db, attempt.id, update_data)
        for key, value in update_data.items():
            setattr(attempt, key, value)

        level_passed, qualified_attempts, required_attempts = await self._evaluate_level_passed(
            db=db,
            attempt=attempt,
            current_attempt_qualified=current_attempt_qualified,
            completion_rule=completion_rule,
        )

        progress = await self._update_progress(
            db=db,
            attempt=attempt,
            passed=level_passed,
            current_attempt_qualified=current_attempt_qualified,
            stars=stars,
            accuracy=accuracy,
            total_time=obj.total_time,
        )
        level_has_passed = bool(progress.passed) if progress is not None else level_passed

        level = await challenge_level_dao.get(db, attempt.level_id)
        next_level = None
        if level is not None:
            next_level = await challenge_level_dao.get_by_global_no(db, level.challenge_key, level.global_no + 1)
        await redis_client.delete(self._redis_key(attempt_key))

        return SubmitChallengeAttemptResult(
            attempt_key=attempt_key,
            passed=level_has_passed,
            current_attempt_qualified=current_attempt_qualified,
            qualified_attempts=qualified_attempts,
            required_attempts=required_attempts,
            completion_rule=ChallengeCompletionRuleParam.model_validate(completion_rule),
            current_attempt_index=rules.get('current_attempt_index'),
            current_attempt_requirement=self._requirement_schema(current_attempt_requirement),
            stars=stars,
            completed_count=completed_count,
            correct_count=correct_count,
            wrong_count=wrong_count,
            accuracy_rate=accuracy,
            next_level_id=next_level.id if next_level else None,
            next_level_unlocked=bool(level_has_passed and next_level),
            completed_at=completed_at,
            results=results,
        )

    async def _completed_result(
        self,
        *,
        db: AsyncSession,
        attempt: ChallengeAttempt,
    ) -> SubmitChallengeAttemptResult:
        """
        构建已完成挑战的幂等响应

        :param db: 数据库会话
        :param attempt: 挑战记录
        :return:
        """
        rules = attempt.rule_snapshot or {}
        completion_rule = self._completion_rule_from_snapshot(rules)
        current_attempt_requirement = rules.get('current_attempt_requirement')
        if not isinstance(current_attempt_requirement, dict):
            current_attempt_requirement = self._attempt_requirement_for_index(
                completion_rule,
                int(rules.get('current_attempt_index') or 0) or None,
            )
        current_attempt_qualified = bool(attempt.passed)
        level_passed = bool(attempt.passed)
        required_attempts = int(completion_rule['required_attempts'])
        if completion_rule['mode'] == 'consecutive_attempts':
            recent_attempts = await challenge_attempt_dao.get_recent_completed(
                db,
                attempt.user_id,
                attempt.level_id,
                required_attempts,
            )
            qualified_attempts = self._qualified_streak(recent_attempts)
        else:
            qualified_attempts = 1 if current_attempt_qualified else 0

        progress = await user_challenge_progress_dao.get_by_level(db, attempt.user_id, attempt.level_id)
        if progress is not None and progress.passed:
            level_passed = True

        level = await challenge_level_dao.get(db, attempt.level_id)
        next_level = None
        if level is not None:
            next_level = await challenge_level_dao.get_by_global_no(db, level.challenge_key, level.global_no + 1)
        return SubmitChallengeAttemptResult(
            attempt_key=attempt.attempt_key,
            passed=level_passed,
            current_attempt_qualified=current_attempt_qualified,
            qualified_attempts=qualified_attempts,
            required_attempts=required_attempts,
            completion_rule=ChallengeCompletionRuleParam.model_validate(completion_rule),
            current_attempt_index=rules.get('current_attempt_index'),
            current_attempt_requirement=self._requirement_schema(current_attempt_requirement),
            stars=attempt.stars,
            completed_count=attempt.completed_count,
            correct_count=attempt.correct_count,
            wrong_count=attempt.wrong_count,
            accuracy_rate=attempt.accuracy_rate,
            next_level_id=next_level.id if next_level else None,
            next_level_unlocked=bool(level_passed and next_level),
            completed_at=attempt.completed_at or timezone.now(),
            results=[],
        )


challenge_service = ChallengeService()
