#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import APIRouter

from backend.app.jia.api.v1.copilot import router as copilot_router
from backend.app.jia.api.v1.doc import router as doc_router
from backend.app.jia.api.v1.exercise import router as exercise_router
from backend.app.jia.api.v1.food import router as food_router
from backend.app.jia.api.v1.item import router as item_router
from backend.app.jia.api.v1.push import router as push_router
from backend.app.jia.api.v1.user_setting import router as setting_router
from backend.app.jia.api.v1.version import router as version_router
from backend.core.conf import settings

v1 = APIRouter(prefix=settings.FASTAPI_API_V1_PATH)

v1.include_router(item_router, prefix='/jia/items', tags=['Jia - 物品管理'])
v1.include_router(food_router, prefix='/jia/foods', tags=['Jia - 食物管理'])
v1.include_router(push_router, prefix='/jia/push', tags=['Jia - 推送管理'])
v1.include_router(exercise_router, prefix='/jia/exercises', tags=['Jia - 运动管理'])
v1.include_router(copilot_router, prefix='/jia/copilot', tags=['Jia - 智能助手'])
v1.include_router(setting_router, prefix='/jia/settings', tags=['Jia - 个人设置'])
v1.include_router(doc_router, prefix='/jia/docs', tags=['Jia - 文档管理'])
v1.include_router(version_router, prefix='/jia/app', tags=['Jia - 应用版本'])
