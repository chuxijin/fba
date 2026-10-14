#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import APIRouter, Depends

from backend.core.conf import settings
from backend.plugin.openauth.api.v1.device import router as device_router
from backend.plugin.openauth.api.v1.distribution import router as distribution_router
from backend.plugin.openauth.api.v1.openauth import client_router, no_store, router

v1 = APIRouter(prefix=f'{settings.FASTAPI_API_V1_PATH}/openauth')

v1.include_router(router, tags=['开放平台授权'])
v1.include_router(client_router, prefix='/clients', tags=['开放平台客户端管理'])
v1.include_router(device_router, tags=['开放平台设备授权'], dependencies=[Depends(no_store)])
v1.include_router(distribution_router, tags=['开放平台 Skill 分发'], dependencies=[Depends(no_store)])
