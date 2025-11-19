#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import APIRouter

from backend.app.bili.api.v1 import (
    account,
    category,
    duplicate_check,
    task_config,
    task_execution_log,
    task_scheduler,
    template,
    work,
)
from backend.core.conf import settings

v1 = APIRouter(prefix=settings.FASTAPI_API_V1_PATH)

v1.include_router(account.router, prefix='/bili/account', tags=['B 站账号管理'])
v1.include_router(category.router, prefix='/bili/category', tags=['B 站分类管理'])
v1.include_router(work.router, prefix='/bili/work', tags=['B 站作品管理'])
v1.include_router(template.router, prefix='/bili/template', tags=['B 站模板管理'])
v1.include_router(duplicate_check.router, prefix='/bili/duplicate_check', tags=['B 站操作记录管理'])
v1.include_router(task_config.router, prefix='/bili/task_config', tags=['B 站任务配置管理'])
v1.include_router(task_scheduler.router, prefix='/bili/task_scheduler', tags=['B 站任务调度管理'])
v1.include_router(task_execution_log.router, prefix='/bili/task_execution_log', tags=['B 站任务执行记录'])
