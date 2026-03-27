#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import APIRouter

from backend.app.gongkao.api.v1 import (
    category,
    content,
    dict_major,
    dict_region,
    gangwei,
    gangwei_match,
    guanmei,
    hanyu,
    jingyan,
    shiping,
    shizhen,
    user_profile,
    zhenti,
)
from backend.core.conf import settings

v1 = APIRouter(prefix=settings.FASTAPI_API_V1_PATH)

v1.include_router(category.router, prefix='/gk/category', tags=['公考分类管理'])
v1.include_router(shiping.router, prefix='/gk/shiping', tags=['公考时评管理'])
v1.include_router(shizhen.router, prefix='/gk/shizhen', tags=['公考时政管理'])
v1.include_router(gangwei.router, prefix='/gk/gangwei', tags=['公考岗位管理'])
v1.include_router(gangwei_match.router, prefix='/gk/gangwei', tags=['岗位匹配'])
v1.include_router(guanmei.router, prefix='/gk/guanmei', tags=['官媒学语言'])
v1.include_router(hanyu.router, prefix='/gk/hanyu', tags=['汉语词汇管理'])
v1.include_router(jingyan.router, prefix='/gk/jingyan', tags=['公考经验管理'])
v1.include_router(zhenti.router, prefix='/gk/zhenti', tags=['公考真题管理'])
v1.include_router(content.router, prefix='/gk/content', tags=['公考内容管理'])
v1.include_router(dict_region.router, prefix='/gk/dict/region', tags=['地区字典'])
v1.include_router(dict_major.router, prefix='/gk/dict/major', tags=['专业目录'])
v1.include_router(user_profile.router, prefix='/gk/profile', tags=['用户画像'])
