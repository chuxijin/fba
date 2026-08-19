#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import APIRouter

from backend.app.sensitive_word.api.v1.admin import router as admin_router

router = APIRouter()
router.include_router(admin_router)
