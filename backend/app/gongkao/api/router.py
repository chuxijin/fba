#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import APIRouter

from backend.app.gongkao.api.v1 import shiping, shizhen, ciyu
from backend.core.conf import settings

v1 = APIRouter(prefix=settings.FASTAPI_API_V1_PATH)

v1.include_router(shiping.router, prefix='/gk/shiping', tags=['公考时评管理'])
v1.include_router(shizhen.router, prefix='/gk/shizhen', tags=['公考时政管理'])
v1.include_router(ciyu.router, prefix='/gk/ciyu', tags=['公考词语管理'])
