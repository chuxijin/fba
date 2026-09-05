#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import APIRouter

from backend.app.media_studio.api.v1.image_gen import router as image_gen_router
from backend.app.media_studio.api.v1.parser import router as parser_router
from backend.app.media_studio.api.v1.recreate import router as recreate_router

router = APIRouter(prefix='/media-studio')
router.include_router(parser_router)
router.include_router(image_gen_router)
router.include_router(recreate_router)