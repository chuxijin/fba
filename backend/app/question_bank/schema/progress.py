#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from pydantic import Field

from backend.common.schema import SchemaBase


class SyncUserBankQuestionProgressItem(SchemaBase):
    """用户内容题目进度同步项"""

    user_id: int = Field(description='用户 ID')
    bank_id: int = Field(description='内容 ID')
    question_id: int = Field(description='题目 ID')
    placement_id: int | None = Field(None, description='挂载 ID')
    is_correct: bool = Field(default=False, description='是否答对')
    first_answered_time: datetime = Field(description='首次作答时间')
    last_answered_time: datetime = Field(description='最近作答时间')
    last_correct_time: datetime | None = Field(None, description='最近答对时间')
