from datetime import datetime
from typing import Any

from pydantic import Field

from backend.common.schema import SchemaBase


class StartShenlunGradingParam(SchemaBase):
    """启动申论批改参数"""

    force_regenerate: bool = Field(default=False, description='是否忽略可复用结果')
    model_name: str | None = Field(default=None, min_length=1, max_length=128, description='指定模型名称')


class StartShenlunGradingResult(SchemaBase):
    """启动申论批改响应"""

    run_id: int = Field(description='Agent 运行 ID')
    agent_key: str = Field(description='Agent 键')
    status: str = Field(description='运行状态')
    stream_url: str = Field(description='SSE 进度地址')


class GradingFeedbackParam(SchemaBase):
    """人工纠正申论批改结果"""

    point_key: str = Field(min_length=1, max_length=80, description='采分点键')
    corrected_status: str = Field(description='hit/partial/miss')
    corrected_quote: str = Field(default='', max_length=240, description='答案原文证据')
    note: str = Field(default='', max_length=500, description='纠正说明')
    scope: str = Field(default='report', description='纠正范围：report/question')


class AgentRunStepRead(SchemaBase):
    """Agent 节点轨迹"""

    step_no: int = Field(description='节点序号')
    node_key: str = Field(description='节点键')
    status: str = Field(description='节点状态')
    output_snapshot: dict[str, Any] | None = Field(default=None, description='节点输出')
    duration_ms: int = Field(description='耗时毫秒')


class GradingRunRead(SchemaBase):
    """申论批改运行详情"""

    id: int = Field(description='运行 ID')
    agent_key: str = Field(description='Agent 键')
    agent_version: str = Field(description='Agent 版本')
    workflow_key: str = Field(description='工作流键')
    workflow_version: str = Field(description='工作流版本')
    subject_type: str = Field(description='业务对象类型')
    subject_id: int = Field(description='业务对象 ID')
    status: str = Field(description='运行状态')
    stage: str | None = Field(default=None, description='当前阶段')
    progress: float = Field(description='运行进度')
    result_summary: str | None = Field(default=None, description='批改摘要')
    result_payload: dict[str, Any] | None = Field(default=None, description='结构化报告')
    steps: list[AgentRunStepRead] = Field(default_factory=list, description='节点轨迹')
    error_code: str | None = Field(default=None, description='错误码')
    error_message: str | None = Field(default=None, description='错误信息')
    started_time: datetime | None = Field(default=None, description='开始时间')
    finished_time: datetime | None = Field(default=None, description='结束时间')
