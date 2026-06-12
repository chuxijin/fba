#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import Field, model_validator

from backend.common.schema import SchemaBase


class AgentType(StrEnum):
    """Agent 类型"""

    shenlun = 'shenlun'
    question_generation = 'question_generation'
    english_essay = 'english_essay'
    xingce = 'xingce'
    interview = 'interview'


class TaskStatus(StrEnum):
    """任务状态"""

    pending = 'pending'
    running = 'running'
    completed = 'completed'
    failed = 'failed'


class SectionName(StrEnum):
    """Section 标识"""

    score_card = 'score_card'
    key_points = 'key_points'
    issues = 'issues'
    suggestions = 'suggestions'
    rewritten_text = 'rewritten_text'
    explanations = 'explanations'
    option_analysis = 'option_analysis'
    dialogue_trace = 'dialogue_trace'
    qc = 'qc'


class GradeLevel(StrEnum):
    """档位 A 最高 D 最低"""

    a = 'A'
    b = 'B'
    c = 'C'
    d = 'D'


class Severity(StrEnum):
    """严重度"""

    critical = 'critical'
    major = 'major'
    minor = 'minor'


class Priority(StrEnum):
    """优先级"""

    high = 'high'
    medium = 'medium'
    low = 'low'


class PointSource(StrEnum):
    """要点来源"""

    material = 'material'
    reference = 'reference'
    answer = 'answer'


class ConsensusLevel(StrEnum):
    """共识度"""

    high = 'high'
    medium = 'medium'
    low = 'low'
    unique = 'unique'


class RubricScoreItem(SchemaBase):
    """单项评分"""

    name: str = Field(description='维度名')
    score: float = Field(description='得分')
    max_score: float = Field(description='满分')
    level: GradeLevel | None = Field(default=None, description='本维度档位')
    level_label: str = Field(default='', description='本维度档位的业务术语')
    comment: str = Field(default='', description='评分说明')


class KeyPointItem(SchemaBase):
    """要点"""

    text: str = Field(description='要点内容')
    source: PointSource = Field(description='来源')
    consensus_count: int = Field(default=1, description='出现在几份参考答案中, source=reference 才有意义')
    consensus_level: ConsensusLevel = Field(default=ConsensusLevel.unique, description='共识度')
    matched_user_text: str | None = Field(default=None, description='用户答案匹配片段')
    weight: float = Field(default=1.0, description='要点权重')


class IssueItem(SchemaBase):
    """问题"""

    category: str = Field(description='类别')
    severity: Severity = Field(description='严重度')
    description: str = Field(description='问题描述')
    location: str | None = Field(default=None, description='位置')
    related_section: SectionName | None = Field(default=None, description='相关 section')


class SuggestionItem(SchemaBase):
    """建议"""

    target_issue: str | None = Field(default=None, description='对应问题')
    action: str = Field(description='可执行建议')
    priority: Priority = Field(default=Priority.medium, description='优先级')


class ExplanationItem(SchemaBase):
    """单题解析"""

    question_id: str = Field(description='题目标识')
    correct_answer: str = Field(description='正确答案')
    user_answer: str | None = Field(default=None, description='用户答案')
    is_correct: bool = Field(description='是否正确')
    knowledge_points: list[str] = Field(default_factory=list, description='考点')
    explanation: str = Field(description='解析详情')


class OptionAnalysisItem(SchemaBase):
    """选项分析"""

    question_id: str = Field(description='题目标识')
    option_label: str = Field(description='选项标签')
    content: str = Field(description='选项内容')
    is_correct: bool = Field(description='是否是正确选项')
    why_correct_or_wrong: str = Field(description='对错原因')


class DialogueTurnItem(SchemaBase):
    """对话单轮"""

    role: str = Field(description='角色 interviewer / candidate')
    text: str = Field(description='发言内容')
    timestamp: datetime | None = Field(default=None, description='时间戳')
    feedback: str | None = Field(default=None, description='本轮反馈')


class ScoreCardSection(SchemaBase):
    """评分卡"""

    score: float = Field(description='总分')
    score_total: float = Field(description='满分')
    level: GradeLevel = Field(description='总档位')
    level_label: str = Field(default='', description='总档位业务术语')
    summary: str = Field(description='总评')
    rubric_scores: list[RubricScoreItem] = Field(default_factory=list, description='分项评分')
    system_notes: list[str] = Field(default_factory=list, description='系统级提示, 如代码层强制扣分原因')

    @model_validator(mode='after')
    def _check_rubric_sum_equals_score(self) -> 'ScoreCardSection':
        """交叉校验: rubric_scores 之和 ≈ score (允许 0.5 误差)"""
        if not self.rubric_scores:
            return self
        actual = round(sum(item.score for item in self.rubric_scores), 1)
        if abs(actual - self.score) > 0.5:
            raise ValueError(
                f'ScoreCardSection 内部矛盾: rubric_scores 之和 ({actual}) != score ({self.score})'
            )
        return self

    @model_validator(mode='after')
    def _check_score_within_total(self) -> 'ScoreCardSection':
        """交叉校验: 0 <= score <= score_total"""
        if self.score < 0 or self.score > self.score_total:
            raise ValueError(
                f'ScoreCardSection 内部矛盾: score ({self.score}) 越界 [0, {self.score_total}]'
            )
        return self


class KeyPointsSection(SchemaBase):
    """要点对比"""

    material_points: list[KeyPointItem] = Field(default_factory=list, description='材料核心要点')
    reference_points: list[KeyPointItem] = Field(default_factory=list, description='参考答案共识要点')
    answer_points: list[KeyPointItem] = Field(default_factory=list, description='已覆盖要点')
    missing_points: list[KeyPointItem] = Field(default_factory=list, description='缺失要点')


class IssuesSection(SchemaBase):
    """问题诊断"""

    items: list[IssueItem] = Field(default_factory=list, description='问题列表')


class SuggestionsSection(SchemaBase):
    """提升建议"""

    items: list[SuggestionItem] = Field(default_factory=list, description='建议列表')


class ChangeItem(SchemaBase):
    """单条改动说明"""

    original: str = Field(description='原文片段')
    revised: str = Field(description='改写片段')
    reason: str = Field(description='改动原因')


class RewrittenTextSection(SchemaBase):
    """改写示范"""

    original: str = Field(description='用户原文')
    revised: str = Field(description='改写版')
    diff_summary: str = Field(default='', description='改动点说明')
    changes: list[ChangeItem] = Field(default_factory=list, description='逐条改动说明')
    inline_diff: str = Field(default='', description='行内对比格式 (~~删除~~**新增**)')


class ExplanationsSection(SchemaBase):
    """逐题解析"""

    items: list[ExplanationItem] = Field(default_factory=list, description='解析列表')


class OptionAnalysisSection(SchemaBase):
    """选项分析"""

    items: list[OptionAnalysisItem] = Field(default_factory=list, description='选项列表')


class DialogueTraceSection(SchemaBase):
    """对话回放"""

    turns: list[DialogueTurnItem] = Field(default_factory=list, description='对话轨迹')


class QCSection(SchemaBase):
    """质检"""

    passed: bool = Field(description='是否通过')
    confidence: float = Field(description='置信度')
    notes: list[str] = Field(default_factory=list, description='质检说明')
    retry_count: int = Field(default=0, description='重评次数')

    @model_validator(mode='after')
    def _check_passed_confidence_consistency(self) -> 'QCSection':
        """交叉校验: passed=True 但 confidence<0.3 是矛盾"""
        if self.passed and self.confidence < 0.3:
            raise ValueError(
                f'QCSection 内部矛盾: passed=True 但 confidence ({self.confidence}) < 0.3'
            )
        return self


class AgentTraceItem(SchemaBase):
    """执行轨迹"""

    agent: str = Field(description='节点名')
    stage: str = Field(description='阶段标识')
    started_at: datetime = Field(description='开始时间')
    finished_at: datetime = Field(description='结束时间')
    duration_ms: int = Field(description='耗时毫秒')
    model: str | None = Field(default=None, description='所用模型')
    tokens_in: int = Field(default=0, description='输入 token')
    tokens_out: int = Field(default=0, description='输出 token')
    summary: str = Field(default='', description='执行摘要')
    output: dict[str, Any] = Field(default_factory=dict, description='结构化输出, 调试用')


class AgentReport(SchemaBase):
    """Agent 报告"""

    agent_type: AgentType = Field(description='agent 类型')
    score_card: ScoreCardSection | None = Field(default=None, description='评分卡')
    key_points: KeyPointsSection | None = Field(default=None, description='要点对比')
    issues: IssuesSection | None = Field(default=None, description='问题诊断')
    suggestions: SuggestionsSection | None = Field(default=None, description='提升建议')
    rewritten_text: RewrittenTextSection | None = Field(default=None, description='改写示范')
    explanations: ExplanationsSection | None = Field(default=None, description='逐题解析')
    option_analysis: OptionAnalysisSection | None = Field(default=None, description='选项分析')
    dialogue_trace: DialogueTraceSection | None = Field(default=None, description='对话回放')
    qc: QCSection | None = Field(default=None, description='质检')
    traces: list[AgentTraceItem] = Field(default_factory=list, description='执行轨迹')
    extras: dict[str, Any] = Field(default_factory=dict, description='agent 私有扩展字段')
