from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import Field

from backend.common.schema import SchemaBase

RankType = Literal['practice_count', 'accuracy_rate', 'streak_days']


class QuestionTypeProgress(SchemaBase):
    """题型进度统计"""

    question_count: int = Field(ge=0, description='题目总数')
    answered_count: int = Field(ge=0, description='已作答题数')
    correct_count: int = Field(ge=0, description='最近一次答对题数')
    wrong_count: int = Field(ge=0, description='最近一次答错题数')
    progress_rate: Decimal = Field(ge=0, le=1, description='完成率')
    accuracy_rate: Decimal = Field(ge=0, le=1, description='已判题正确率')


QuestionTypeProgressMap = dict[str, QuestionTypeProgress]


class BankProgressSummary(SchemaBase):
    """题库或篇章进度汇总"""

    total_count: int = Field(ge=0, description='题目总数')
    answered_count: int = Field(ge=0, description='已作答题数')
    correct_count: int = Field(ge=0, description='最近一次答对题数')
    wrong_count: int = Field(ge=0, description='最近一次答错题数')
    progress_rate: Decimal = Field(ge=0, le=1, description='完成率')
    accuracy_rate: Decimal = Field(ge=0, le=1, description='已判题正确率')
    question_type_counts: dict[str, int] = Field(default_factory=dict, description='各题型题目数')
    question_type_progress: QuestionTypeProgressMap = Field(default_factory=dict, description='各题型进度')


class BankSectionProgress(BankProgressSummary):
    """篇章树进度节点"""

    id: int = Field(description='篇章 ID')
    name: str = Field(description='篇章名称')
    parent_id: int | None = Field(None, description='父篇章 ID')
    depth: int = Field(ge=0, description='篇章深度')
    sort_order: int = Field(description='同层排序')
    children: list['BankSectionProgress'] = Field(default_factory=list, description='子篇章')


class ResumableScope(SchemaBase):
    """当前可续接的进行中会话维度，用于判断练习入口展示“继续”还是“开始”"""

    section_id: int | None = Field(None, description='篇章 ID；None 表示题库整卷维度')
    question_type: str | None = Field(None, description='题型；None 表示全题型维度')
    modes: list[str] = Field(default_factory=list, description='存在进行中会话的练习模式')


class GetBankProgressDetail(BankProgressSummary):
    """题库当前发布版本学习进度"""

    bank_id: int = Field(description='题库稳定身份 ID')
    bank_revision_id: int = Field(description='题库当前发布版本 ID')
    bank_name: str = Field(description='题库名称')
    unsectioned: BankProgressSummary = Field(description='未归入篇章的题目进度')
    sections: list[BankSectionProgress] = Field(default_factory=list, description='篇章进度树')
    resumable_scopes: list[ResumableScope] = Field(
        default_factory=list, description='当前可续接的进行中会话维度'
    )


class GetBankProgressBrief(SchemaBase):
    """题库当前发布版本进度摘要，供列表页批量展示"""

    bank_id: int = Field(description='题库稳定身份 ID')
    bank_revision_id: int = Field(description='题库当前发布版本 ID')
    total_count: int = Field(ge=0, description='题目总数')
    answered_count: int = Field(ge=0, description='已作答题数')
    correct_count: int = Field(ge=0, description='最近一次答对题数')
    wrong_count: int = Field(ge=0, description='最近一次答错题数')
    progress_rate: Decimal = Field(ge=0, le=1, description='完成率')
    accuracy_rate: Decimal = Field(ge=0, le=1, description='已判题正确率')


class WrongSectionCount(SchemaBase):
    """篇章错题数量节点"""

    id: int = Field(description='篇章 ID')
    name: str = Field(description='篇章名称')
    parent_id: int | None = Field(None, description='父篇章 ID')
    depth: int = Field(ge=0, description='篇章深度')
    sort_order: int = Field(description='同层排序')
    wrong_count: int = Field(ge=0, description='包含后代篇章的活跃错题数')
    children: list['WrongSectionCount'] = Field(default_factory=list, description='子篇章')


class GetBankWrongSectionCounts(SchemaBase):
    """题库当前发布版本错题篇章统计"""

    bank_id: int = Field(description='题库稳定身份 ID')
    bank_revision_id: int = Field(description='题库当前发布版本 ID')
    total_wrong_count: int = Field(ge=0, description='活跃错题总数')
    unsectioned_wrong_count: int = Field(ge=0, description='未归入篇章的活跃错题数')
    sections: list[WrongSectionCount] = Field(default_factory=list, description='错题篇章树')


class UserDailyPracticeDetail(SchemaBase):
    """用户每日刷题趋势"""

    activity_date: date = Field(description='练习日期')
    attempt_count: int = Field(ge=0, description='提交次数')
    graded_count: int = Field(ge=0, description='已判题次数')
    correct_count: int = Field(ge=0, description='答对次数')
    duration_ms: int = Field(ge=0, description='有效作答时长毫秒')


class UserMonthlyPracticeDetail(SchemaBase):
    """用户月度刷题趋势"""

    month: str = Field(description='月份，格式 YYYY-MM')
    attempt_count: int = Field(ge=0, description='提交次数')
    graded_count: int = Field(ge=0, description='已判题次数')
    correct_count: int = Field(ge=0, description='答对次数')
    duration_ms: int = Field(ge=0, description='有效作答时长毫秒')


class GetUserPracticeReport(SchemaBase):
    """用户刷题累计报告"""

    session_count: int = Field(ge=0, description='累计有效会话数')
    attempt_count: int = Field(ge=0, description='累计提交次数')
    graded_count: int = Field(ge=0, description='累计已判题次数')
    correct_count: int = Field(ge=0, description='累计答对次数')
    accuracy_rate: Decimal = Field(ge=0, le=1, description='累计已判题正确率')
    total_duration_ms: int = Field(ge=0, description='累计有效作答时长毫秒')
    practice_days: int = Field(ge=0, description='累计练习天数')
    streak_days: int = Field(ge=0, description='当前连续练习天数')
    last_practice_date: date | None = Field(None, description='最近练习日期')
    site_total_attempt_count: int = Field(ge=0, description='全站累计提交次数')
    site_max_attempt_count: int = Field(ge=0, description='单用户最高累计提交次数')
    attempt_rank: int | None = Field(None, gt=0, description='当前用户答题量排名')
    today_attempt_count: int = Field(ge=0, description='今日累计提交次数')
    daily_trend: list[UserDailyPracticeDetail] = Field(default_factory=list, description='每日趋势')
    monthly_trend: list[UserMonthlyPracticeDetail] = Field(default_factory=list, description='月度趋势')


class PracticeRankItem(SchemaBase):
    """刷题排行榜项"""

    rank: int = Field(gt=0, description='排名')
    user_id: int = Field(description='用户 ID')
    nickname: str = Field(description='用户昵称')
    avatar: str | None = Field(None, description='用户头像')
    value: Decimal = Field(ge=0, description='排名指标值')


class GetCollectionProgressSummary(SchemaBase):
    """合集作用域下的题库进度摘要，供首页一次性渲染 tab 汇总与列表进度"""

    collection_id: int = Field(description='合集 ID')
    total_count: int = Field(ge=0, description='作用域内去重题目总数')
    answered_count: int = Field(ge=0, description='已作答题数')
    correct_count: int = Field(ge=0, description='最近一次答对题数')
    wrong_count: int = Field(ge=0, description='最近一次答错题数')
    progress_rate: Decimal = Field(ge=0, le=1, description='完成率')
    accuracy_rate: Decimal = Field(ge=0, le=1, description='已判题正确率')
    banks: list[GetBankProgressBrief] = Field(default_factory=list, description='作用域内各题库进度')


class GetPracticeRankList(SchemaBase):
    """刷题排行榜"""

    rank_type: RankType = Field(description='排行榜类型')
    total_users: int = Field(ge=0, description='参与排名用户数')
    current_user_rank: PracticeRankItem | None = Field(None, description='当前用户排名')
    items: list[PracticeRankItem] = Field(default_factory=list, description='排行榜列表')
