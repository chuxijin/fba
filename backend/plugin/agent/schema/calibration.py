from typing import Any

from pydantic import Field

from backend.common.schema import SchemaBase


class CalibrationRefreshResult(SchemaBase):
    """校准锚点刷新结果"""

    session_id: int = Field(description='题库 V2 会话 ID')
    anchor_status: str = Field(description='锚点状态')
    exclusion_reason: str | None = Field(None, description='排除原因')
    activated_scopes: list[str] = Field(default_factory=list, description='本次激活的策略范围')


class CalibrationPolicyRead(SchemaBase):
    """当前校准策略"""

    scope_type: str = Field(description='策略范围类型')
    scope_key: str = Field(description='策略范围键')
    policy_version: str = Field(description='策略版本')
    policy_payload: dict[str, Any] = Field(description='策略内容')
    metrics_payload: dict[str, Any] = Field(description='验证指标')
