#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import APIRouter

from backend.core.conf import settings
from backend.plugin.agiso.api.v1 import webhook

v1 = APIRouter(prefix=settings.FASTAPI_API_V1_PATH)

v1.include_router(webhook.router, prefix='/agiso/webhooks', tags=['阿奇索推送接口'])
