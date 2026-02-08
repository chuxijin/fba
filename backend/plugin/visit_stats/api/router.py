#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import APIRouter
from backend.plugin.visit_stats.api.v1.visit import router as visit_router

# 定义插件的主路由变量，名为 v1
# 这里的 prefix='/api/v1' 决定了最终的 URL 前缀
v1 = APIRouter(prefix='/api/v1')

# 将 visit 模块的路由挂载到 v1 下
v1.include_router(visit_router, prefix='/visit', tags=['访问统计'])
