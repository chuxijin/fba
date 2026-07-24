#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import APIRouter

from backend.app.study_plan.api.v1.admin import router as admin_router
from backend.app.study_plan.api.v1.mentor import router as mentor_router
from backend.app.study_plan.api.v1.spatial_cube import router as spatial_cube_router
from backend.app.study_plan.api.v1.spatial_cube_admin import router as spatial_cube_admin_router
from backend.app.study_plan.api.v1.student import router as student_router
from backend.core.conf import settings

v1 = APIRouter(prefix=settings.FASTAPI_API_V1_PATH)

v1.include_router(student_router, prefix='/study/student', tags=['学习规划-学员端'])
v1.include_router(mentor_router, prefix='/study/mentor', tags=['学习规划-导师端'])
v1.include_router(admin_router, prefix='/study/admin', tags=['学习规划-管理端'])
v1.include_router(spatial_cube_router, prefix='/study/spatial-cube', tags=['立体能力-六面体'])
v1.include_router(spatial_cube_admin_router, prefix='/study/admin/spatial-cube', tags=['学习规划-管理端'])
