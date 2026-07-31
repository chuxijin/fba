from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase

EvaluationPurpose = Literal['attempt_grading', 'attempt_feedback', 'session_summary']
EvaluationEngineType = Literal['rule', 'ai', 'agent', 'manual']
EvaluationTriggerSource = Literal['auto', 'manual', 'retry']
EvaluationStatus = Literal['queued', 'running', 'succeeded', 'failed', 'cancelled']


class TriggerEvaluationParam(SchemaBase):
    """触发 AI 评测参数"""

    force_regenerate: bool = Field(default=False, description='是否忽略当前结果并创建替代运行')
    model_name: str | None = Field(None, min_length=1, max_length=128, description='指定已启用模型；为空使用默认模型')


class EvaluationRunRead(SchemaBase):
    """面向用户的评测运行结果，不暴露提示词与参考答案快照"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='评测运行 ID')
    user_id: int = Field(description='用户 ID')
    purpose: EvaluationPurpose = Field(description='运行目的')
    engine_type: EvaluationEngineType = Field(description='评测引擎类型')
    session_id: int | None = Field(None, description='会话 ID')
    attempt_id: int | None = Field(None, description='作答事实 ID')
    supersedes_id: int | None = Field(None, description='被本次运行替代的运行 ID')
    trigger_source: EvaluationTriggerSource = Field(description='触发来源')
    status: EvaluationStatus = Field(description='运行状态')
    provider: str | None = Field(None, description='模型服务商')
    model_name: str | None = Field(None, description='模型名称')
    model_version: str | None = Field(None, description='模型固定版本')
    prompt_version: str | None = Field(None, description='提示词版本')
    rubric_version: str | None = Field(None, description='评分量规版本')
    score: Decimal | None = Field(None, ge=0, description='评测得分')
    max_score: Decimal | None = Field(None, ge=0, description='满分')
    confidence: Decimal | None = Field(None, ge=0, le=1, description='评测置信度')
    needs_manual_review: bool = Field(description='是否需要人工复核')
    summary_text: str | None = Field(None, description='面向用户的评测摘要')
    result_payload: dict[str, Any] = Field(default_factory=dict, description='结构化评测结果')
    error_code: str | None = Field(None, description='失败错误码')
    error_message: str | None = Field(None, description='失败信息')
    started_time: datetime | None = Field(None, description='开始时间')
    finished_time: datetime | None = Field(None, description='结束时间')
    is_latest: bool = Field(description='是否为当前结果')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')


class SubjectiveAnswerOCRResult(SchemaBase):
    """主观题 OCR 识别结果"""

    text: str = Field(description='识别后的文本')
