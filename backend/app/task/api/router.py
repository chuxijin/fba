#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import APIRouter

from backend.app.task.api.v1.task import router as task_router
from backend.app.task.api.v1.filesync import router as filesync_router
from backend.core.conf import settings

v1 = APIRouter(prefix=settings.FASTAPI_API_V1_PATH)

v1.include_router(task_router, prefix='/tasks', tags=['任务'])
v1.include_router(filesync_router, prefix='/tasks/filesync', tags=['文件同步任务'])
