from datetime import date as calendar_date
from enum import IntEnum

from pydantic import Field

from backend.common.schema import SchemaBase


class WrongTrendDays(IntEnum):
    """整数枚举兼容 HTTP 字符串查询，同时仅接受7或30天。"""

    week = 7
    month = 30


class WrongTrendPoint(SchemaBase):
    date: calendar_date = Field(description='配置时区的自然日')
    wrong: int | None = Field(ge=0, description='当日入本或再次记错，按题去重')
    reviewed: int | None = Field(ge=0, description='当日完成复盘，按题去重')
    mastered: int | None = Field(ge=0, description='当日新掌握，按题去重；覆盖起点前为未知')


class GetWrongTrend(SchemaBase):
    start_date: calendar_date = Field(description='范围首日（含）')
    end_date: calendar_date = Field(description='范围末日（含）')
    timezone: str = Field(description='自然日统计时区')
    mastery_known_from: calendar_date | None = Field(description='掌握事件完整覆盖的首个自然日；迁移当日不完整')
    today: WrongTrendPoint = Field(description='今日统计，不随日期筛选改变')
    points: list[WrongTrendPoint] = Field(description='范围内连续自然日；未知为 null，已知无事件为 0')
