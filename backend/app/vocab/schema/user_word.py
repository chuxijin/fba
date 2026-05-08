#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class GetUserWordDetail(SchemaBase):
    """用户单词状态详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='记录 ID')
    user_id: int = Field(description='用户 ID')
    word_id: int = Field(description='单词 ID')
    state: int = Field(description='FSRS 状态')
    step: int | None = Field(None, description='FSRS 学习步骤')
    stability: float | None = Field(None, description='FSRS 稳定性')
    difficulty: float | None = Field(None, description='FSRS 难度')
    due: datetime = Field(description='下次到期时间')
    last_review: datetime | None = Field(None, description='上次复习时间')
    is_starred: bool = Field(description='是否收藏')


class ToggleStarParam(SchemaBase):
    """切换收藏参数"""

    word_id: int = Field(description='单词 ID')
    is_starred: bool = Field(description='是否收藏')
