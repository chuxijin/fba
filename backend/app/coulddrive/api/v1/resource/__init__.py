#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import APIRouter

from backend.app.coulddrive.api.v1.resource.resource import router as resource_router

# 分类管理直接使用 admin 的 API: /api/v1/sys/categories?app_code=clouddrive

router = APIRouter()

router.include_router(resource_router, prefix='/resources', tags=['资源管理'])