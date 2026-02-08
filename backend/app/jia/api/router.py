#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import APIRouter

from backend.app.jia.api.v1.item import router as item_router
from backend.app.jia.api.v1.push import router as push_router

v1 = APIRouter(prefix='/jia')

v1.include_router(item_router, prefix='/items', tags=['Jia - 物品管理'])
v1.include_router(push_router, prefix='/push', tags=['Jia - 推送管理'])
