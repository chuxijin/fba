#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime
from typing import Any

from pydantic import Field

from backend.common.schema import SchemaBase
from backend.plugin.agents.schema.report import AgentReport, AgentType, TaskStatus

DEFAULT_AGENT_PROVIDER_ID: int = 5
DEFAULT_AGENT_MODEL_ID: str = 'mimo-v2.5-pro'


class GradingStartParam(SchemaBase):
    """启动批改请求"""

    agent_type: AgentType = Field(description='agent 类型')
    user_id: int = Field(description='提交用户 ID')
    provider_id: int = Field(default=DEFAULT_AGENT_PROVIDER_ID, description='AI 供应商 ID')
    model_id: str = Field(default=DEFAULT_AGENT_MODEL_ID, description='主力模型 ID')
    mini_model_id: str | None = Field(default=None, description='经济模型 ID, 用于分类/抽取等')
    score_total: float | None = Field(default=None, description='满分, 留空按题型评分细则')
    question_stem: str = Field(description='题干')
    question: str = Field(description='题目')
    materials: str = Field(default='', description='给定材料')
    reference_answers: list[str] = Field(default_factory=list, description='多份参考答案')
    user_answer_text: str = Field(description='用户答案文本')


class GradingStartResult(SchemaBase):
    """启动批改响应"""

    task_id: int = Field(description='任务 ID')
    agent_type: AgentType = Field(description='agent 类型')
    status: TaskStatus = Field(description='当前状态')
    stream_url: str = Field(description='SSE 订阅地址')


class GradingDetail(SchemaBase):
    """批改详情"""

    id: int = Field(description='任务 ID')
    agent_type: AgentType = Field(description='agent 类型')
    user_id: int = Field(description='提交用户 ID')
    status: TaskStatus = Field(description='任务状态')
    stage: str | None = Field(default=None, description='当前阶段')
    progress: float = Field(description='进度 0-1')
    report: AgentReport | None = Field(default=None, description='最终批改报告')
    state_snapshot: dict[str, Any] | None = Field(default=None, description='中间快照')
    error_code: str | None = Field(default=None, description='错误码')
    error_message: str | None = Field(default=None, description='错误信息')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(default=None, description='更新时间')


class GradingOcrResult(SchemaBase):
    """OCR 识别结果"""

    text: str = Field(description='识别后归一化的考生答卷文本')
    image_count: int = Field(description='实际处理的图片数')
    provider: str = Field(default='', description='OCR provider 名称')
