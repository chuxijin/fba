#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import APIRouter

from backend.app.question_generation.api.v1.candidate import router as candidate_router
from backend.app.question_generation.api.v1.material import router as material_router
from backend.app.question_generation.api.v1.task import router as task_router

router = APIRouter(prefix='/question-generation')

router.include_router(material_router, prefix='/materials', tags=['AI 出题素材'])
router.include_router(task_router, prefix='/tasks', tags=['AI 出题任务'])
router.include_router(candidate_router, prefix='/candidates', tags=['AI 候选题'])

