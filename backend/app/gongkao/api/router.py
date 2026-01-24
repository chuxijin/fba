#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import APIRouter

from backend.app.gongkao.api.v1 import category, ciyu, gangwei, jingyan, resource, shiping, shizhen, zhenti
from backend.core.conf import settings

v1 = APIRouter(prefix=settings.FASTAPI_API_V1_PATH)

v1.include_router(category.router, prefix='/gk/category', tags=['公考分类管理'])
v1.include_router(shiping.router, prefix='/gk/shiping', tags=['公考时评管理'])
v1.include_router(shizhen.router, prefix='/gk/shizhen', tags=['公考时政管理'])
v1.include_router(ciyu.router, prefix='/gk/ciyu', tags=['公考词语管理'])
v1.include_router(gangwei.router, prefix='/gk/gangwei', tags=['公考岗位管理'])
v1.include_router(jingyan.router, prefix='/gk/jingyan', tags=['公考经验管理'])
v1.include_router(resource.router, prefix='/gk/resource', tags=['公考资料管理'])
v1.include_router(zhenti.router, prefix='/gk/zhenti', tags=['公考真题管理'])
