#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime
from typing import Any

from pydantic import Field

from backend.common.schema import SchemaBase
from backend.plugin.agents.schema.report import (
    AgentTraceItem,
    DialogueTraceSection,
    ExplanationsSection,
    IssuesSection,
    KeyPointsSection,
    OptionAnalysisSection,
    QCSection,
    RewrittenTextSection,
    ScoreCardSection,
    SuggestionsSection,
)


class GradingState(SchemaBase):
    """节点间共享状态"""

    task_id: int = Field(description='任务 ID')
    user_id: int = Field(description='提交用户 ID')
    provider_id: int = Field(description='AI 供应商 ID')
    primary_model: str = Field(description='主力模型 ID')

    question_stem: str = Field(description='题干')
    question: str = Field(description='题目')
    materials: str = Field(default='', description='给定材料')
    reference_answers: list[str] = Field(default_factory=list, description='参考答案列表')
    user_answer_text: str = Field(description='用户答案文本, OCR 完成或文字直接输入')

    score_total: float | None = Field(default=None, description='满分, 留空按题型评分细则')
    question_type: str | None = Field(default=None, description='题型, 自动识别后填')
    rubric: dict[str, Any] | None = Field(default=None, description='当前题型评分细则')

    score_card: ScoreCardSection | None = Field(default=None, description='评分卡 section')
    key_points: KeyPointsSection | None = Field(default=None, description='要点对比 section')
    issues: IssuesSection | None = Field(default=None, description='问题诊断 section')
    suggestions: SuggestionsSection | None = Field(default=None, description='提升建议 section')
    rewritten_text: RewrittenTextSection | None = Field(default=None, description='改写示范 section')
    explanations: ExplanationsSection | None = Field(default=None, description='逐题解析 section')
    option_analysis: OptionAnalysisSection | None = Field(default=None, description='选项分析 section')
    dialogue_trace: DialogueTraceSection | None = Field(default=None, description='对话回放 section')
    qc: QCSection | None = Field(default=None, description='质检 section')

    traces: list[AgentTraceItem] = Field(default_factory=list, description='执行轨迹')
    extras: dict[str, Any] = Field(default_factory=dict, description='节点间临时共享数据, 非持久化')
    started_at: datetime = Field(default_factory=datetime.now, description='开始时间')
    last_checkpoint_stage: str | None = Field(default=None, description='上次落库阶段')
