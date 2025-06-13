#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import APIRouter

from backend.plugin.app_auth.api.v1 import application, authorization, device, order, package, redeem_code, statistics, version
from backend.core.conf import settings

v1 = APIRouter(prefix=settings.FASTAPI_API_V1_PATH)

v1.include_router(application.router, prefix='/app-auth/applications', tags=['应用管理'])
v1.include_router(device.router, prefix='/app-auth/devices', tags=['设备管理'])
v1.include_router(package.router, prefix='/app-auth/packages', tags=['套餐管理'])
v1.include_router(order.router, prefix='/app-auth/orders', tags=['订单管理'])
v1.include_router(redeem_code.router, prefix='/app-auth/redeem-codes', tags=['兑换码管理'])
v1.include_router(version.router, prefix='/app-auth/versions', tags=['版本管理'])
v1.include_router(authorization.router, prefix='/app-auth/authorizations', tags=['授权管理'])
v1.include_router(statistics.router, prefix='/app-auth/statistics', tags=['统计数据']) 