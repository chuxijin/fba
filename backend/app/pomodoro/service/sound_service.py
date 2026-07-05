#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from backend.app.pomodoro.enums import PomodoroSoundCategory
from backend.app.pomodoro.schema.sound import GetPomodoroSoundPresetList, PomodoroSoundPresetItem


class PomodoroSoundService:
    """番茄背景音服务类"""

    @staticmethod
    async def get_presets() -> GetPomodoroSoundPresetList:
        """获取背景音预设"""
        return GetPomodoroSoundPresetList(
            items=[
                PomodoroSoundPresetItem(
                    key='rain',
                    name='雨声',
                    category=PomodoroSoundCategory.nature,
                    local_asset_path='/static/sounds/pomodoro/rain.mp3',
                    description='稳定雨声背景音',
                ),
                PomodoroSoundPresetItem(
                    key='cafe',
                    name='咖啡厅',
                    category=PomodoroSoundCategory.ambient,
                    local_asset_path='/static/sounds/pomodoro/cafe.mp3',
                    description='轻量环境人声背景音',
                ),
                PomodoroSoundPresetItem(
                    key='white_noise',
                    name='白噪音',
                    category=PomodoroSoundCategory.noise,
                    local_asset_path='/static/sounds/pomodoro/white-noise.mp3',
                    description='平稳白噪音',
                ),
            ]
        )


pomodoro_sound_service: PomodoroSoundService = PomodoroSoundService()
