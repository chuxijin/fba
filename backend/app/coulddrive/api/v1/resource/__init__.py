#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import APIRouter

from backend.app.coulddrive.api.v1.resource.resource import router as resource_router

router = APIRouter()

router.include_router(resource_router, prefix='/resources', tags=['资源管理']) 