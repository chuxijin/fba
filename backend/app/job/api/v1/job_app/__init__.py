#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import APIRouter

from backend.app.job.api.v1.job_app.internship_application import router as internship_application_router
from backend.app.job.api.v1.job_app.internship_posting import router as internship_posting_router
from backend.app.job.api.v1.job_app.job_application import router as job_application_router
from backend.app.job.api.v1.job_app.job_posting import router as job_posting_router

router = APIRouter(prefix="/job")
router.include_router(job_posting_router, prefix="/posting", tags=['招聘信息'])
router.include_router(job_application_router, prefix="/application", tags=['投递记录'])
router.include_router(internship_posting_router, prefix="/internship", tags=['实习信息'])
router.include_router(internship_application_router, prefix="/internship_application", tags=['实习投递记录'])