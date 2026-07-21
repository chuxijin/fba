#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import APIRouter

from backend.app.mydrive.api.v1.account import router as account_router
from backend.app.mydrive.api.v1.public_resource import router as public_resource_router
from backend.app.mydrive.api.v1.relationship import router as relationship_router
from backend.app.mydrive.api.v1.resource import router as resource_router
from backend.app.mydrive.api.v1.space import router as space_router
from backend.app.mydrive.api.v1.sync import router as sync_router
from backend.core.conf import settings

v1 = APIRouter(prefix=settings.FASTAPI_API_V1_PATH)
v1.include_router(account_router, prefix='/mydrive/accounts', tags=['我的网盘账户'])
v1.include_router(public_resource_router, prefix='/mydrive/public/resources', tags=['公开资源'])
v1.include_router(relationship_router, prefix='/mydrive', tags=['我的关系分享'])
v1.include_router(resource_router, prefix='/mydrive/resources', tags=['我的资源'])
v1.include_router(space_router, prefix='/mydrive/spaces', tags=['我的文件空间'])
v1.include_router(sync_router, prefix='/mydrive/sync', tags=['我的文件同步'])

router = v1
