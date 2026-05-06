#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase

PracticeAIEvaluationTargetType = Literal['question_eval', 'session_summary']
PracticeAIEvaluationStatus = Literal['pending', 'succeeded', 'failed']
PracticeAIEvaluationTriggerSource = Literal['auto', 'manual']


class TriggerPracticeAIEvaluationParam(SchemaBase):
    """触发 AI 评估参数"""

    force_regenerate: bool = Field(default=False, description='是否强制重新生成')


class PracticeAIEvaluationRead(SchemaBase):
    """练习 AI 评估结果"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='评估结果 ID')
    user_id: int = Field(description='用户 ID')
    session_id: int | None = Field(None, description='会话 ID')
    practice_record_id: int | None = Field(None, description='作答记录 ID')
    question_id: int | None = Field(None, description='题目 ID')
    target_type: PracticeAIEvaluationTargetType = Field(description='目标类型')
    trigger_source: PracticeAIEvaluationTriggerSource = Field(description='触发来源')
    status: PracticeAIEvaluationStatus = Field(description='状态')
    provider_id: int | None = Field(None, description='AI 供应商 ID')
    model_name: str | None = Field(None, description='模型名称')
    prompt_version: str | None = Field(None, description='提示词版本')
    score: Decimal | None = Field(None, ge=Decimal('0'), description='得分')
    max_score: Decimal | None = Field(None, ge=Decimal('0'), description='满分')
    confidence: Decimal | None = Field(None, ge=Decimal('0'), le=Decimal('1'), description='置信度')
    summary_text: str | None = Field(None, description='摘要文本')
    request_payload: dict[str, Any] | None = Field(None, description='请求快照')
    result_payload: dict[str, Any] | None = Field(None, description='结果快照')
    error_message: str | None = Field(None, description='错误信息')
    started_at: datetime | None = Field(None, description='开始时间')
    finished_at: datetime | None = Field(None, description='结束时间')
    is_latest: bool = Field(description='是否为最新结果')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')


class SubjectiveAnswerOCRResult(SchemaBase):
    """主观题 OCR 识别结果"""

    text: str = Field(description='识别后的文本')
