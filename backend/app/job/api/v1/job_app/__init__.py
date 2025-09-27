#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import APIRouter

from backend.app.job.api.v1.job_app.job_application import router as job_application_router
from backend.app.job.api.v1.job_app.job_posting import router as job_posting_router

router = APIRouter(prefix="/job")
router.include_router(job_posting_router, tags=['招聘信息'])
router.include_router(job_application_router, tags=['投递记录'])