#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import APIRouter

from backend.app.coulddrive.api.v1.sync.tasks import router as task_router
from backend.app.coulddrive.api.v1.sync.config import router as config_router

router = APIRouter(prefix='/couldsync')

router.include_router(task_router, tags=['云盘同步管理'])
router.include_router(config_router, tags=['云盘同步配置'])
