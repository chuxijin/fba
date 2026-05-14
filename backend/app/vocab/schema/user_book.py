#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class StartBookParam(SchemaBase):
    """开始学习词书参数"""

    daily_new_target: int | None = Field(None, ge=1, le=200, description='每日新词目标(可选,覆盖全局设置)')


class CreateUserBookParam(SchemaBase):
    """创建用户词书参数"""

    user_id: int = Field(description='用户 ID')
    book_id: int = Field(description='词书 ID')
    is_active: bool = Field(True, description='是否当前在学')
    started_at: datetime = Field(description='开始学习时间')


class GetUserBookDetail(SchemaBase):
    """用户词书详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='记录 ID')
    user_id: int = Field(description='用户 ID')
    book_id: int = Field(description='词书 ID')
    is_active: bool = Field(description='是否当前在学')
    started_at: datetime | None = Field(None, description='开始学习时间')
    finished_at: datetime | None = Field(None, description='完成时间')
    created_time: datetime = Field(description='创建时间')


class GetUserBookWithProgress(GetUserBookDetail):
    """用户词书详情(含进度)"""

    book_name: str = Field(default='', description='词书名称')
    book_cover: str | None = Field(None, description='封面图')
    total_words: int = Field(default=0, description='词书总词数')
    learned_words: int = Field(default=0, description='已学词数')
    mastered_words: int = Field(default=0, description='已掌握词数')
