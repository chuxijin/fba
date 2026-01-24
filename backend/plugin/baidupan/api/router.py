#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import APIRouter

from backend.core.conf import settings
from backend.plugin.baidupan.api.v1 import oauth

v1 = APIRouter(prefix=settings.FASTAPI_API_V1_PATH)

v1.include_router(oauth.router, prefix='/baidupan/oauth', tags=['百度网盘 OAuth'])
