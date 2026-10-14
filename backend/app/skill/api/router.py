#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import APIRouter

from backend.app.skill.api.v1.calculation import router as calculation_router
from backend.app.skill.api.v1.qbank import router as qbank_router
from backend.app.skill.api.v1.skill import router as skill_router
from backend.core.conf import settings

v1 = APIRouter(prefix=settings.FASTAPI_API_V1_PATH)

v1.include_router(skill_router, prefix='/skill', tags=['skill 业务'])
v1.include_router(calculation_router, prefix='/skill', tags=['skill 计算练习'])
v1.include_router(qbank_router, prefix='/skill', tags=['skill 题库只读'])

router_app = v1
