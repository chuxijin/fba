#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Literal

from pydantic import BaseModel, Field

StudyDomainCode = Literal['cet', 'kaoyan', 'gongkao', 'jiaozhi']


class CustomTab(BaseModel):
    """自定义 Tab"""

    id: str = Field(description='Tab ID')
    name: str = Field(description='Tab 名称')
    category_id: int = Field(description='分类 ID')
    category_name: str = Field(description='分类名称')
    bank_id: int | None = Field(description='题库 ID')
    bank_name: str | None = Field(description='题库名称')
    is_fixed: bool = Field(description='是否固定')
    order: int = Field(description='排序')


ThemeMode = Literal['light', 'dark', 'auto']


class StudyPreferenceSettings(BaseModel):
    """学习偏好设置"""

    current_domain: StudyDomainCode = Field(default='gongkao', description='当前学习领域')
    practice_mode: str = Field(default='practice', description='做题模式：practice/exercise/memorize')
    custom_tabs: list[CustomTab] = Field(default_factory=list, description='自定义 Tab 列表')
    mastery_threshold: int = Field(default=3, ge=1, le=20, description='错题连续答对掌握阈值')
    theme_mode: ThemeMode = Field(default='light', description='主题模式：light/dark/auto')


class UpdateStudyPreferenceParam(BaseModel):
    """更新学习偏好设置参数"""

    current_domain: StudyDomainCode | None = Field(None, description='当前学习领域')
    practice_mode: str | None = Field(None, description='做题模式：practice/exercise/memorize')
    custom_tabs: list[CustomTab] | None = Field(None, description='自定义 Tab 列表')
    mastery_threshold: int | None = Field(None, ge=1, le=20, description='错题连续答对掌握阈值')
    theme_mode: ThemeMode | None = Field(None, description='主题模式：light/dark/auto')


class GetStudyPreferenceResponse(BaseModel):
    """获取学习偏好设置响应"""

    current_domain: StudyDomainCode = Field(default='gongkao', description='当前学习领域')
    practice_mode: str = Field(description='做题模式：practice/exercise/memorize')
    custom_tabs: list[CustomTab] = Field(default_factory=list, description='自定义 Tab 列表')
    mastery_threshold: int = Field(default=3, description='错题连续答对掌握阈值')
    theme_mode: ThemeMode = Field(default='light', description='主题模式：light/dark/auto')


class InitDomainPreferenceParam(BaseModel):
    """新用户领域初始化参数"""

    domain_code: StudyDomainCode = Field(description='选择的学习领域编码')


class PracticeDataResetResult(BaseModel):
    """做题数据重置结果"""

    ai_evaluation_count: int = Field(default=0, description='删除的 AI 批改记录数')
    agent_task_count: int = Field(default=0, description='删除的申论 Agent 批改任务数')
    practice_record_count: int = Field(default=0, description='删除的答题记录数')
    progress_count: int = Field(default=0, description='删除的内容进度汇总数')
    session_question_count: int = Field(default=0, description='删除的会话题目快照数')
    practice_session_count: int = Field(default=0, description='删除的练习会话数')
    wrong_question_count: int = Field(default=0, description='删除的错题记录数')
    check_in_count: int = Field(default=0, description='删除的打卡记录数')
    daily_rank_count: int = Field(default=0, description='删除的每日排名记录数')
    stats_reset_count: int = Field(default=0, description='重置的统计快照数')
