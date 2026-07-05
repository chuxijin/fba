#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from pydantic import Field

from backend.app.pomodoro.enums import PomodoroRankingPeriod, PomodoroRankingScope
from backend.common.schema import SchemaBase


class PomodoroRankingItem(SchemaBase):
    """番茄排行榜项"""

    rank: int = Field(description='排名')
    user_id: int = Field(description='用户 ID')
    nickname: str = Field(description='用户昵称')
    avatar: str | None = Field(None, description='用户头像')
    focused_seconds: int = Field(description='专注秒数')
    completed_pomodoro_count: int = Field(description='完成番茄数')


class GetPomodoroRankingDetail(SchemaBase):
    """番茄排行榜详情"""

    period: PomodoroRankingPeriod = Field(description='榜单周期')
    scope: PomodoroRankingScope = Field(description='榜单范围')
    generated_at: datetime = Field(description='生成时间')
    items: list[PomodoroRankingItem] = Field(description='榜单项')
    my_rank: PomodoroRankingItem | None = Field(None, description='我的排名')
