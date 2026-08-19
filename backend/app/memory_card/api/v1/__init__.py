#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import APIRouter

from backend.app.memory_card.api.v1.admin import router as admin_router
from backend.app.memory_card.api.v1.study import router as study_router

router = APIRouter()
router.include_router(admin_router)
router.include_router(study_router)
