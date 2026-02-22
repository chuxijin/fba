#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import APIRouter

from backend.core.conf import settings
from backend.plugin.notify.api.v1 import notify

v1 = APIRouter(prefix=settings.FASTAPI_API_V1_PATH)

v1.include_router(notify.router, prefix='/notify', tags=['通知服务'])
