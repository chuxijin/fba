#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
用户设置相关 Schema
"""
from pydantic import BaseModel, Field


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


class StudyPreferenceSettings(BaseModel):
    """学习偏好设置"""

    practice_mode: str = Field(default='practice', description='做题模式：practice/exercise/memorize')
    custom_tabs: list[CustomTab] = Field(default_factory=list, description='自定义 Tab 列表')
    mastery_threshold: int = Field(default=3, ge=1, le=20, description='错题连续答对掌握阈值')


class UpdateStudyPreferenceParam(BaseModel):
    """更新学习偏好设置参数"""

    practice_mode: str | None = Field(None, description='做题模式：practice/exercise/memorize')
    custom_tabs: list[CustomTab] | None = Field(None, description='自定义 Tab 列表')
    mastery_threshold: int | None = Field(None, ge=1, le=20, description='错题连续答对掌握阈值')


class GetStudyPreferenceResponse(BaseModel):
    """获取学习偏好设置响应"""

    practice_mode: str = Field(description='做题模式：practice/exercise/memorize')
    custom_tabs: list[CustomTab] = Field(default_factory=list, description='自定义 Tab 列表')
    mastery_threshold: int = Field(default=3, description='错题连续答对掌握阈值')
