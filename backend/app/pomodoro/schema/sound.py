#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from pydantic import Field

from backend.app.pomodoro.enums import PomodoroSoundCategory
from backend.common.schema import SchemaBase


class PomodoroSoundPresetItem(SchemaBase):
    """番茄背景音预设项"""

    key: str = Field(description='背景音标识')
    name: str = Field(description='背景音名称')
    category: PomodoroSoundCategory = Field(description='背景音分类')
    local_asset_path: str = Field(description='小程序本地资源路径')
    description: str | None = Field(None, description='背景音描述')


class GetPomodoroSoundPresetList(SchemaBase):
    """番茄背景音预设列表"""

    items: list[PomodoroSoundPresetItem] = Field(description='背景音预设')
