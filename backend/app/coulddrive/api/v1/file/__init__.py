#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import APIRouter

from backend.app.coulddrive.api.v1.file.file import router as file_router
from backend.app.coulddrive.api.v1.file.file_cache import router as file_cache_router

router = APIRouter(prefix='/couldfile')

router.include_router(file_router, tags=['云盘文件管理'])
router.include_router(file_cache_router, prefix='/cache', tags=['云盘文件缓存管理'])
