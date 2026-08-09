from datetime import time
from typing import Literal

from pydantic import ConfigDict, Field, field_validator

from backend.common.schema import SchemaBase

PracticeMode = Literal['practice', 'exercise', 'exam', 'mock', 'memorize', 'review', 'adaptive']
ThemeMode = Literal['light', 'dark', 'auto']
RandomPracticeYearRange = Literal['unlimited', 'last_3_years', 'last_5_years']


class CustomTab(SchemaBase):
    """用户自定义题库标签"""

    id: str = Field(min_length=1, max_length=64, description='标签业务 ID')
    name: str = Field(min_length=1, max_length=64, description='标签名称')
    category_id: int = Field(gt=0, description='分类 ID')
    category_name: str = Field(min_length=1, max_length=64, description='分类名称快照')
    bank_id: int | None = Field(None, gt=0, description='题库 ID')
    bank_name: str | None = Field(None, max_length=160, description='题库名称快照')
    is_fixed: bool = Field(default=False, description='是否固定')
    order: int = Field(default=0, description='标签排序')


CategoryCustomTabs = dict[str, list[CustomTab]]

KnowledgeSystemChoice = dict[str, int]
"""各科目选定的知识体系版本；key 为体系 code（如 xingce），value 为 system_id，未配置的科目回落 default"""


class UpdatePracticePreferenceParam(SchemaBase):
    """更新用户练习偏好参数"""

    current_category_id: int | None = Field(None, gt=0, description='当前题库业务分类 ID')
    current_knowledge_point_id: int | None = Field(None, gt=0, description='当前知识点导航根节点 ID')
    practice_mode: PracticeMode | None = Field(None, description='默认练习模式')
    mastery_threshold: int | None = Field(None, ge=1, le=20, description='错题连续答对掌握阈值')
    theme_mode: ThemeMode | None = Field(None, description='主题模式')
    random_practice_count: int | None = Field(None, ge=10, le=100, description='默认随机练习题数')
    random_practice_year_range: RandomPracticeYearRange | None = Field(None, description='随机练习年份范围')
    review_reminder_enabled: bool | None = Field(None, description='是否启用错题复习提醒')
    review_reminder_time: time | None = Field(None, description='用户本地每日提醒时间')
    review_reminder_timezone: str | None = Field(None, min_length=1, max_length=64, description='IANA 提醒时区')
    review_daily_limit: int | None = Field(None, ge=1, le=200, description='单日复习题数上限')
    custom_tabs: CategoryCustomTabs | None = Field(None, description='按分类范围隔离的自定义导航标签')
    knowledge_system_choice: KnowledgeSystemChoice | None = Field(
        None,
        description='各科目选定的知识体系版本；key 为体系 code，未配置的科目回落 default',
    )

    @field_validator('knowledge_system_choice')
    @classmethod
    def validate_knowledge_system_choice(
        cls, value: KnowledgeSystemChoice | None
    ) -> KnowledgeSystemChoice | None:
        if value is None:
            return None
        if len(value) > 50:
            raise ValueError('知识体系选择最多 50 个科目')
        if any(not code.strip() for code in value):
            raise ValueError('知识体系编码不能为空')
        if any(system_id <= 0 for system_id in value.values()):
            raise ValueError('知识体系 ID 必须大于 0')
        return value

    @field_validator('custom_tabs')
    @classmethod
    def validate_custom_tabs(cls, value: CategoryCustomTabs | None) -> CategoryCustomTabs | None:
        if value is None:
            return None
        if len(value) > 20:
            raise ValueError('自定义标签分类最多 20 个')
        if any(len(tabs) > 20 for tabs in value.values()):
            raise ValueError('每个分类最多 20 个自定义标签')
        if sum(map(len, value.values())) > 100:
            raise ValueError('自定义标签总数最多 100 个')
        return value


class GetPracticePreferenceDetail(SchemaBase):
    """用户练习偏好详情"""

    model_config = ConfigDict(from_attributes=True)

    current_category_id: int | None = Field(None, description='当前题库业务分类 ID')
    current_knowledge_point_id: int | None = Field(None, description='当前知识点导航根节点 ID')
    practice_mode: PracticeMode = Field(default='practice', description='默认练习模式')
    mastery_threshold: int = Field(default=3, description='错题连续答对掌握阈值')
    theme_mode: ThemeMode = Field(default='light', description='主题模式')
    random_practice_count: int = Field(default=20, description='默认随机练习题数')
    random_practice_year_range: RandomPracticeYearRange = Field(default='unlimited', description='随机练习年份范围')
    review_reminder_enabled: bool = Field(default=False, description='是否启用错题复习提醒')
    review_reminder_time: time = Field(default=time(20, 0), description='用户本地每日提醒时间')
    review_reminder_timezone: str = Field(default='Asia/Shanghai', description='IANA 提醒时区')
    review_daily_limit: int = Field(default=30, description='单日复习题数上限')
    custom_tabs: CategoryCustomTabs = Field(default_factory=dict, description='按分类范围隔离的自定义导航标签')
    knowledge_system_choice: KnowledgeSystemChoice = Field(
        default_factory=dict,
        description='各科目选定的知识体系版本；key 为体系 code，未配置的科目回落 default',
    )
