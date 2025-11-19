#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import APIRouter

from backend.app.jia.api.v1 import category, diaries, habits, note, reminders, tag

router = APIRouter(prefix='/jia')

router.include_router(note.router, prefix='/notes', tags=['笔记'])
router.include_router(category.router, prefix='/categories', tags=['分类'])
router.include_router(tag.router, prefix='/tags', tags=['标签'])
router.include_router(diaries.router, prefix='/diaries', tags=['日记'])
router.include_router(habits.router, prefix='/habits', tags=['习惯'])
router.include_router(reminders.router, prefix='/reminders', tags=['提醒'])

