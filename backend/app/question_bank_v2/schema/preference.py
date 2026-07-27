from typing import Literal

from pydantic import ConfigDict, Field

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


class UpdatePracticePreferenceParam(SchemaBase):
    """更新用户练习偏好参数"""

    current_category_id: int | None = Field(None, gt=0, description='当前题库业务分类 ID')
    current_knowledge_point_id: int | None = Field(None, gt=0, description='当前知识点导航根节点 ID')
    practice_mode: PracticeMode | None = Field(None, description='默认练习模式')
    mastery_threshold: int | None = Field(None, ge=1, le=20, description='错题连续答对掌握阈值')
    theme_mode: ThemeMode | None = Field(None, description='主题模式')
    random_practice_count: int | None = Field(None, ge=10, le=100, description='默认随机练习题数')
    random_practice_year_range: RandomPracticeYearRange | None = Field(None, description='随机练习年份范围')
    custom_tabs: CategoryCustomTabs | None = Field(None, description='按分类范围隔离的自定义导航标签')


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
    custom_tabs: CategoryCustomTabs = Field(default_factory=dict, description='按分类范围隔离的自定义导航标签')
