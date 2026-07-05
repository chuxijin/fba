#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import APIRouter

from backend.app.pomodoro.api.v1.achievement import router as achievement_router
from backend.app.pomodoro.api.v1.break_session import router as break_router
from backend.app.pomodoro.api.v1.focus import router as focus_router
from backend.app.pomodoro.api.v1.habit import router as habit_router
from backend.app.pomodoro.api.v1.ranking import router as ranking_router
from backend.app.pomodoro.api.v1.setting import router as setting_router
from backend.app.pomodoro.api.v1.sound import router as sound_router
from backend.app.pomodoro.api.v1.statistic import router as statistic_router
from backend.app.pomodoro.api.v1.task import router as task_router
from backend.core.conf import settings

v1 = APIRouter(prefix=settings.FASTAPI_API_V1_PATH)

v1.include_router(task_router)
v1.include_router(focus_router)
v1.include_router(break_router)
v1.include_router(habit_router)
v1.include_router(setting_router)
v1.include_router(statistic_router)
v1.include_router(achievement_router)
v1.include_router(ranking_router)
v1.include_router(sound_router)
