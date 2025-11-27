#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import APIRouter

from backend.app.actcode.api.v1.actcode import router as actcode_router

v1 = APIRouter(prefix='/v1')

v1.include_router(actcode_router)
