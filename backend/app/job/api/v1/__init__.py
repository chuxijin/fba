#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import APIRouter

from backend.app.job.api.v1.job import router as job_router

router = APIRouter()

router.include_router(job_router)


