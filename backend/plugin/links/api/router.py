#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import APIRouter

from backend.core.conf import settings
from backend.plugin.links.api.v1.domain import router as domain_router
from backend.plugin.links.api.v1.dwz import router as dwz_router
from backend.plugin.links.api.v1.kf import router as kf_router
from backend.plugin.links.api.v1.kf_redirect import router as kf_redirect_router
from backend.plugin.links.api.v1.page import router as page_router
from backend.plugin.links.api.v1.page_render import router as page_render_router
from backend.plugin.links.api.v1.qun import router as qun_router
from backend.plugin.links.api.v1.qun_redirect import router as qun_redirect_router
from backend.plugin.links.api.v1.redirect import router as redirect_router

v1 = APIRouter(prefix=f'{settings.FASTAPI_API_V1_PATH}/links')

# 管理接口
v1.include_router(domain_router, prefix='/domain', tags=['域名管理'])
v1.include_router(dwz_router, prefix='/dwz', tags=['短网址管理'])
v1.include_router(qun_router, prefix='/qun', tags=['群活码管理'])
v1.include_router(kf_router, prefix='/kf', tags=['客服码管理'])
v1.include_router(page_router, prefix='/page', tags=['静态页面管理'])

# 公开访问接口
v1.include_router(redirect_router, prefix='/c', tags=['短链访问'])
v1.include_router(qun_redirect_router, prefix='/q', tags=['群活码访问'])
v1.include_router(kf_redirect_router, prefix='/k', tags=['客服码访问'])
v1.include_router(page_render_router, prefix='/p', tags=['静态页面访问'])
