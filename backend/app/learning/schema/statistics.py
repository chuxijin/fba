from datetime import date

from pydantic import Field

from backend.common.schema import SchemaBase


class LearningStatisticDistributionItem(SchemaBase):
    """学习专注分布项。"""

    name: str = Field(description='分布名称')
    color: str | None = Field(None, description='展示颜色')
    focused_seconds: int = Field(description='专注秒数')
    percentage: float = Field(description='占比百分比')


class LearningStatisticPoint(SchemaBase):
    """学习专注统计点。"""

    period: str = Field(description='周期标识')
    start_date: date = Field(description='开始日期')
    end_date: date = Field(description='结束日期')
    focused_seconds: int = Field(description='专注秒数')
    completed_task_count: int = Field(description='完成任务数')
    finished_session_count: int = Field(description='完成专注次数')


class GetLearningSummaryStatistic(SchemaBase):
    """学习专注汇总统计。"""

    start_date: date = Field(description='统计开始日期')
    end_date: date = Field(description='统计结束日期')
    focused_seconds: int = Field(description='专注秒数')
    completed_task_count: int = Field(description='完成任务数')
    finished_session_count: int = Field(description='完成专注次数')
    avg_task_seconds: int = Field(description='任务平均专注秒数')
    points: list[LearningStatisticPoint] = Field(description='统计点')
    distribution: list[LearningStatisticDistributionItem] = Field(description='分布数据')
