#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import APIRouter

from backend.core.conf import settings
from backend.plugin.ocr.api.v1.ocr import router as ocr_router

v1 = APIRouter(prefix=settings.FASTAPI_API_V1_PATH)

v1.include_router(ocr_router, prefix='/ocr', tags=['OCR 识别'])
