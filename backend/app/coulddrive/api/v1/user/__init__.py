#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import APIRouter

from backend.app.coulddrive.api.v1.user.user import router as user_router

router = APIRouter(prefix='/coulduser')

router.include_router(user_router, tags=['云盘用户管理'])
