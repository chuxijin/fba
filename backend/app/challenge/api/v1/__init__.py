#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import APIRouter

from backend.app.challenge.api.v1.admin import router as admin_router
from backend.app.challenge.api.v1.user import router as user_router

router = APIRouter()
router.include_router(user_router, prefix='/challenges', tags=['闯关挑战'])
router.include_router(admin_router, prefix='/admin/challenges', tags=['闯关管理'])

