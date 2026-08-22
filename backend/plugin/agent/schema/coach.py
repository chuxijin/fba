from datetime import datetime
from typing import Any

from pydantic import Field

from backend.common.schema import SchemaBase


class CreateCoachSessionParam(SchemaBase):
    """创建申论教练会话参数。"""

    title: str = Field(default='申论训练教练', min_length=1, max_length=160)
    grading_run_id: int | None = Field(default=None, gt=0, description='作为起点的批改运行 ID')


class CoachMessageParam(SchemaBase):
    """发送教练消息参数。"""

    content: str = Field(min_length=1, max_length=8000)
    request_id: str | None = Field(default=None, min_length=8, max_length=80, description='客户端幂等请求 ID')
    model_name: str | None = Field(default=None, min_length=1, max_length=128)
    entrypoint: str = Field(default='chat', pattern='^(chat|today|recent_review|next_question)$')
    module: str | None = Field(
        default=None,
        max_length=32,
        description='overview/summary/analysis/countermeasure/document/essay',
    )


class StartCoachRunResult(SchemaBase):
    """启动申论教练异步运行响应。"""

    run_id: int
    agent_key: str
    status: str
    stream_url: str


class CoachMessageRead(SchemaBase):
    """教练消息。"""

    id: int
    role: str
    content: str
    metadata_payload: dict[str, Any] = Field(default_factory=dict)
    created_time: datetime


class CoachSessionRead(SchemaBase):
    """教练会话详情。"""

    id: int
    title: str
    status: str
    context_snapshot: dict[str, Any] = Field(default_factory=dict)
    last_summary: str | None = None
    messages: list[CoachMessageRead] = Field(default_factory=list)
    created_time: datetime
    updated_time: datetime | None = None


class CoachSessionListRead(SchemaBase):
    """申论教练会话列表项。"""

    id: int
    title: str
    status: str
    last_summary: str | None = None
    created_time: datetime
    updated_time: datetime | None = None


class CoachRunStepRead(SchemaBase):
    """申论教练运行步骤。"""

    step_no: int
    node_key: str
    status: str
    output_snapshot: dict[str, Any] | None = None
    duration_ms: int = 0


class CoachRunRead(SchemaBase):
    """申论教练异步运行详情。"""

    id: int
    agent_key: str
    agent_version: str
    workflow_key: str
    workflow_version: str
    subject_type: str
    subject_id: int
    status: str
    stage: str | None = None
    progress: float
    result_summary: str | None = None
    result_payload: dict[str, Any] | None = None
    steps: list[CoachRunStepRead] = Field(default_factory=list)
    error_code: str | None = None
    error_message: str | None = None
    started_time: datetime | None = None
    finished_time: datetime | None = None


class CoachMemoryRead(SchemaBase):
    """长期训练记忆。"""

    id: int
    memory_key: str
    memory_type: str
    content: str
    confidence: float
    source_ref: str | None = None
    evidence: dict[str, Any] = Field(default_factory=dict)
    last_seen_time: datetime | None = None


class CoachRecommendationRead(SchemaBase):
    """申论教练推荐题目。"""

    question_id: int
    code: str
    stem: str
    question_type: str
    difficulty: float | None = None
    module: str
    mastery_score: float | None = None
    attempt_count: int = 0
    correct_rate: float | None = None
    reason: str


class GenerateTrainingPlanParam(SchemaBase):
    """生成训练计划参数。"""

    goal: str = Field(default='提升申论作答稳定性和得分率', min_length=1, max_length=500)
    days: int = Field(default=14, ge=3, le=90)
    daily_minutes: int = Field(default=40, ge=10, le=240)
    request_id: str | None = Field(default=None, min_length=8, max_length=80, description='客户端幂等请求 ID')
    model_name: str | None = Field(default=None, min_length=1, max_length=128)


class TrainingPlanItemRead(SchemaBase):
    """训练计划项。"""

    id: int
    due_date: datetime | None = None
    task_type: str
    title: str
    instruction: str
    target: dict[str, Any] = Field(default_factory=dict)
    status: str
    completed_time: datetime | None = None


class TrainingPlanRead(SchemaBase):
    """训练计划详情。"""

    id: int
    title: str
    status: str
    goal: str
    start_date: datetime | None = None
    end_date: datetime | None = None
    summary: dict[str, Any] = Field(default_factory=dict)
    items: list[TrainingPlanItemRead] = Field(default_factory=list)
    created_time: datetime


class TrainingPlanListRead(SchemaBase):
    """申论训练计划列表项。"""

    id: int
    title: str
    status: str
    goal: str
    start_date: datetime | None = None
    end_date: datetime | None = None
    summary: dict[str, Any] = Field(default_factory=dict)
    created_time: datetime


class CoachAnalyticsRead(SchemaBase):
    """申论训练分析。"""

    grading_count: int
    average_score_rate: float | None = None
    latest_score_rate: float | None = None
    score_trend: list[dict[str, Any]] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    active_plan_count: int = 0
    pending_task_count: int = 0
    completed_task_count: int = 0
