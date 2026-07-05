#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import APIRouter

from backend.app.pomodoro.schema.sound import GetPomodoroSoundPresetList
from backend.app.pomodoro.service.sound_service import pomodoro_sound_service
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth

router = APIRouter(prefix='/pomodoro/sounds', tags=['番茄背景音'], dependencies=[DependsJwtAuth])


@router.get(
    '/presets',
    summary='获取番茄背景音预设',
    name='pomodoro_sound_presets',
    operation_id='pomodoroSoundPresets',
    response_model=ResponseSchemaModel[GetPomodoroSoundPresetList],
)
async def get_pomodoro_sound_presets() -> ResponseSchemaModel[GetPomodoroSoundPresetList]:
    """获取番茄背景音预设"""
    data = await pomodoro_sound_service.get_presets()
    return response_base.success(data=data)
