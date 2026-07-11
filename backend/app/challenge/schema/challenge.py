#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import Field

from backend.common.schema import SchemaBase

ChallengeStage = Literal['easy', 'normal', 'hard']
ChallengeLevelStatus = Literal['draft', 'published', 'disabled']
ChallengeMapLevelStatus = Literal['cleared', 'active', 'locked']
ChallengeSourceType = Literal['fixed', 'pool', 'manual', 'generator']
ChallengeQuestionType = Literal['single', 'multiple', 'judgement', 'fill', 'shortAnswer', 'matching', 'connection']
ChallengeCompletionMode = Literal['single_attempt', 'consecutive_attempts']


class ChallengeCompletionRuleParam(SchemaBase):
    """关卡通关规则参数"""

    mode: ChallengeCompletionMode = Field(default='single_attempt', description='通关模式')
    required_attempts: int = Field(default=1, ge=1, le=100, description='要求达标次数')
    min_accuracy_rate: Decimal | None = Field(
        None,
        ge=Decimal('0'),
        le=Decimal('100'),
        description='最低正确率，为空时使用关卡通关正确率',
    )
    max_total_time: int | None = Field(None, gt=0, le=86400, description='单次最高用时（秒）')


class ChallengeSectionParam(SchemaBase):
    """关卡题目分组参数"""

    seq_no: int = Field(ge=1, le=100, description='分组顺序')
    name: str | None = Field(None, max_length=128, description='分组名称')
    source_type: ChallengeSourceType = Field(description='题目来源')
    question_count: int = Field(ge=1, le=100, description='抽题数量')
    source_config: dict[str, Any] = Field(default_factory=dict, description='题源配置')
    required_correct_count: int | None = Field(None, ge=0, le=100, description='分组最低答对数量')
    enabled: bool = Field(default=True, description='是否启用')


class ChallengeLevelParam(SchemaBase):
    """关卡配置参数"""

    challenge_key: str = Field(min_length=1, max_length=64, description='闯关标识')
    stage: ChallengeStage = Field(description='难度阶段')
    level_no: int = Field(ge=1, le=100, description='阶段内关卡号')
    global_no: int = Field(ge=1, le=1000, description='全局关卡序号')
    title: str = Field(min_length=1, max_length=128, description='关卡名称')
    description: str | None = Field(None, description='关卡描述')
    previous_level_id: int | None = Field(None, gt=0, description='前置关卡 ID')
    question_count: int = Field(default=5, ge=1, le=100, description='题目数量')
    time_limit: int = Field(default=0, ge=0, le=7200, description='建议用时（秒）')
    pass_rate: Decimal = Field(default=Decimal('80'), ge=Decimal('0'), le=Decimal('100'), description='通关正确率')
    star_two_rate: Decimal = Field(
        default=Decimal('90'), ge=Decimal('0'), le=Decimal('100'), description='二星正确率'
    )
    star_three_rate: Decimal = Field(
        default=Decimal('100'), ge=Decimal('0'), le=Decimal('100'), description='三星正确率'
    )
    required_section_pass: bool = Field(default=False, description='是否要求所有分组达标')
    completion_rule: ChallengeCompletionRuleParam | None = Field(None, description='通关规则')
    display_config: dict[str, Any] | None = Field(None, description='前端展示配置')
    sort_order: int = Field(default=0, ge=0, description='排序')
    sections: list[ChallengeSectionParam] = Field(min_length=1, max_length=50, description='题目分组')


class CreateChallengeLevelParam(ChallengeLevelParam):
    """创建关卡参数"""


class UpdateChallengeLevelParam(SchemaBase):
    """更新关卡参数"""

    title: str | None = Field(None, min_length=1, max_length=128, description='关卡名称')
    description: str | None = Field(None, description='关卡描述')
    previous_level_id: int | None = Field(None, gt=0, description='前置关卡 ID')
    question_count: int | None = Field(None, ge=1, le=100, description='题目数量')
    time_limit: int | None = Field(None, ge=0, le=7200, description='建议用时（秒）')
    pass_rate: Decimal | None = Field(None, ge=Decimal('0'), le=Decimal('100'), description='通关正确率')
    star_two_rate: Decimal | None = Field(None, ge=Decimal('0'), le=Decimal('100'), description='二星正确率')
    star_three_rate: Decimal | None = Field(None, ge=Decimal('0'), le=Decimal('100'), description='三星正确率')
    required_section_pass: bool | None = Field(None, description='是否要求所有分组达标')
    completion_rule: ChallengeCompletionRuleParam | None = Field(None, description='通关规则')
    display_config: dict[str, Any] | None = Field(None, description='前端展示配置')
    sort_order: int | None = Field(None, ge=0, description='排序')
    status: ChallengeLevelStatus | None = Field(None, description='关卡状态')
    sections: list[ChallengeSectionParam] | None = Field(None, min_length=1, max_length=50, description='题目分组')


class GetChallengeSectionDetail(ChallengeSectionParam):
    """关卡题目分组详情"""

    id: int = Field(description='分组 ID')


class GetChallengeLevelDetail(SchemaBase):
    """关卡配置详情"""

    id: int = Field(description='关卡 ID')
    challenge_key: str = Field(description='闯关标识')
    stage: ChallengeStage = Field(description='难度阶段')
    level_no: int = Field(description='阶段内关卡号')
    global_no: int = Field(description='全局关卡序号')
    title: str = Field(description='关卡名称')
    description: str | None = Field(None, description='关卡描述')
    previous_level_id: int | None = Field(None, description='前置关卡 ID')
    question_count: int = Field(description='题目数量')
    time_limit: int = Field(description='建议用时（秒）')
    pass_rate: Decimal = Field(description='通关正确率')
    star_two_rate: Decimal = Field(description='二星正确率')
    star_three_rate: Decimal = Field(description='三星正确率')
    required_section_pass: bool = Field(description='是否要求所有分组达标')
    completion_rule: ChallengeCompletionRuleParam = Field(description='通关规则')
    display_config: dict[str, Any] | None = Field(None, description='前端展示配置')
    status: ChallengeLevelStatus = Field(description='关卡状态')
    config_version: int = Field(description='配置版本')
    sort_order: int = Field(description='排序')
    sections: list[GetChallengeSectionDetail] = Field(default_factory=list, description='题目分组')


class GetChallengeMapLevel(SchemaBase):
    """用户关卡地图项"""

    id: int = Field(description='关卡 ID')
    stage: ChallengeStage = Field(description='难度阶段')
    level_no: int = Field(description='阶段内关卡号')
    global_no: int = Field(description='全局关卡序号')
    title: str = Field(description='关卡名称')
    description: str | None = Field(None, description='关卡描述')
    question_count: int = Field(description='题目数量')
    time_limit: int = Field(description='建议用时（秒）')
    pass_rate: Decimal = Field(description='通关正确率')
    completion_rule: ChallengeCompletionRuleParam = Field(description='通关规则')
    status: ChallengeMapLevelStatus = Field(description='用户关卡状态')
    stars: int = Field(ge=0, le=3, description='最佳星级')
    best_accuracy: Decimal = Field(description='最佳正确率')
    attempt_count: int = Field(ge=0, description='挑战次数')


class GetChallengeMapStage(SchemaBase):
    """用户阶段地图"""

    stage: ChallengeStage = Field(description='难度阶段')
    unlocked: bool = Field(description='阶段是否解锁')
    cleared_count: int = Field(ge=0, description='已通关数量')
    total_count: int = Field(ge=0, description='关卡总数')
    stars: int = Field(ge=0, description='累计星级')
    levels: list[GetChallengeMapLevel] = Field(default_factory=list, description='关卡列表')


class GetChallengeMapResponse(SchemaBase):
    """用户闯关地图"""

    challenge_key: str = Field(description='闯关标识')
    stages: list[GetChallengeMapStage] = Field(default_factory=list, description='阶段列表')


class ChallengeQuestionOption(SchemaBase):
    """挑战题目选项"""

    option_code: str = Field(description='选项编码')
    content: str = Field(description='选项内容')


class ChallengeQuestionItem(SchemaBase):
    """挑战题目"""

    seq_no: int = Field(ge=1, description='题目顺序')
    section_seq: int = Field(ge=1, description='分组顺序')
    type: ChallengeQuestionType = Field(description='题型')
    stem: str = Field(description='题干')
    material: str | None = Field(None, description='题目材料')
    options: list[ChallengeQuestionOption] = Field(default_factory=list, description='选项')
    interaction_config: dict[str, Any] | None = Field(None, description='交互题配置')
    difficulty: Decimal | None = Field(None, description='题目难度')


class GetChallengeAttemptResponse(SchemaBase):
    """挑战会话详情"""

    attempt_key: str = Field(description='挑战唯一标识')
    level_id: int = Field(description='关卡 ID')
    level_title: str = Field(description='关卡名称')
    stage: ChallengeStage = Field(description='难度阶段')
    level_no: int = Field(description='阶段内关卡号')
    question_count: int = Field(description='题目数量')
    time_limit: int = Field(description='建议用时（秒）')
    completion_rule: ChallengeCompletionRuleParam = Field(description='通关规则')
    expires_in: int = Field(ge=0, description='临时题目剩余有效期（秒）')
    questions: list[ChallengeQuestionItem] = Field(default_factory=list, description='即时题目')


class ChallengeAnswerItem(SchemaBase):
    """挑战答案项"""

    seq_no: int = Field(ge=1, description='题目顺序')
    user_answer: str | list[str] | dict[str, Any] | list[dict[str, Any]] = Field(description='用户答案')
    answer_time: int = Field(default=0, ge=0, le=7200, description='答题用时（秒）')


class SubmitChallengeAttemptParam(SchemaBase):
    """提交挑战参数"""

    answers: list[ChallengeAnswerItem] = Field(min_length=1, max_length=100, description='答案列表')
    total_time: int = Field(default=0, ge=0, le=86400, description='总用时（秒）')


class ChallengeAnswerResult(SchemaBase):
    """挑战题目结果"""

    seq_no: int = Field(description='题目顺序')
    is_correct: bool = Field(description='是否正确')
    correct_answer: str | list[str] | dict[str, Any] = Field(description='正确答案')
    analysis: str | None = Field(None, description='题目解析')


class SubmitChallengeAttemptResult(SchemaBase):
    """提交挑战结果"""

    attempt_key: str = Field(description='挑战唯一标识')
    passed: bool = Field(description='是否通关')
    current_attempt_qualified: bool = Field(description='本次挑战是否达标')
    qualified_attempts: int = Field(ge=0, description='当前连续达标次数')
    required_attempts: int = Field(ge=1, description='要求达标次数')
    completion_rule: ChallengeCompletionRuleParam = Field(description='通关规则')
    stars: int = Field(ge=0, le=3, description='本次星级')
    completed_count: int = Field(ge=0, description='完成题数')
    correct_count: int = Field(ge=0, description='答对题数')
    wrong_count: int = Field(ge=0, description='答错题数')
    accuracy_rate: Decimal = Field(description='正确率')
    next_level_id: int | None = Field(None, description='下一关 ID')
    next_level_unlocked: bool = Field(description='是否解锁下一关')
    completed_at: datetime = Field(description='完成时间')
    results: list[ChallengeAnswerResult] = Field(default_factory=list, description='逐题结果')
