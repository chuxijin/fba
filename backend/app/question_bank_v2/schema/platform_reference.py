from datetime import datetime
from typing import Literal, Self

from pydantic import ConfigDict, Field, field_serializer, model_validator

from backend.common.schema import SchemaBase


class PlatformReferenceBase(SchemaBase):
    """外部参照快照；抓取时间不是平台统计时间，不接收鉴权或任意原始响应。"""

    model_config = ConfigDict(extra='forbid')

    version: Literal['fenbi-global-v1'] = 'fenbi-global-v1'
    captured_at: datetime = Field(description='该响应首次被页面捕获的时间，含时区')
    population: Literal['platform_unspecified'] = 'platform_unspecified'

    @model_validator(mode='after')
    def validate_time(self) -> Self:
        if self.captured_at.tzinfo is None:
            raise ValueError('统计抓取时间必须包含时区')
        return self

    @field_serializer('captured_at', when_used='json')
    def serialize_capture_time(self, value: datetime) -> str:
        # SchemaBase的普通展示时间会去掉时区，统计快照必须可无损重读。
        return value.isoformat()


class PlatformQuestionReference(PlatformReferenceBase):
    correct_ratio_percent: float | None = Field(None, ge=0, le=100, allow_inf_nan=False, strict=True)
    total_count_raw: int | None = Field(None, ge=0, le=10**12, strict=True, description='平台原计数，不视为独立人数')
    wrong_count_raw: int | None = Field(
        None, ge=0, le=10**12, strict=True, description='保留异常原值，不用于错误率推导'
    )
    most_wrong_choice: str | None = Field(None, max_length=100, description='平台原选项编码，非完整选项分布')


class PlatformReportReference(PlatformReferenceBase):
    difficulty_raw: float | None = Field(None, ge=0, allow_inf_nan=False, description='原平台量表，方向未知')
    average_score: float | None = Field(None, ge=0, allow_inf_nan=False)
    beat_rate_percent: float | None = Field(None, ge=0, le=100, allow_inf_nan=False)
    highest_score: float | None = Field(None, ge=0, allow_inf_nan=False)
    sigma_raw: float | None = Field(None, ge=0, allow_inf_nan=False)
    total_user_raw: int | None = Field(None, ge=0, le=10**12)
