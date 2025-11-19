#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import APIRouter

from backend.app.question_bank.api.v1.auth import router as auth_router
from backend.app.question_bank.api.v1.bank import router as bank_router
from backend.app.question_bank.api.v1.category import router as category_router
from backend.app.question_bank.api.v1.chapter import router as chapter_router
from backend.app.question_bank.api.v1.favorite import router as favorite_router
from backend.app.question_bank.api.v1.membership import router as membership_router
from backend.app.question_bank.api.v1.note import router as note_router
from backend.app.question_bank.api.v1.practice import router as practice_router
from backend.app.question_bank.api.v1.question import router as question_router
from backend.app.question_bank.api.v1.session import router as session_router
from backend.app.question_bank.api.v1.upload import router as upload_router
from backend.app.question_bank.api.v1.wrong_question import router as wrong_question_router

router = APIRouter(prefix='/qbank')

router.include_router(auth_router, prefix='/auth', tags=['认证'])
router.include_router(category_router, prefix='/categories', tags=['题库分类'])
router.include_router(bank_router, prefix='/banks', tags=['题库'])
router.include_router(chapter_router, prefix='/chapters', tags=['题库章节'])
router.include_router(question_router, prefix='/questions', tags=['题目'])
router.include_router(membership_router, prefix='/memberships', tags=['会员权益'])
router.include_router(practice_router, prefix='/practice', tags=['刷题'])
router.include_router(session_router, prefix='/sessions', tags=['练习会话'])
router.include_router(wrong_question_router, prefix='/wrong-questions', tags=['错题本'])
router.include_router(note_router, prefix='/notes', tags=['笔记'])
router.include_router(favorite_router, prefix='/favorites', tags=['收藏'])
router.include_router(upload_router, prefix='/upload', tags=['文件上传'])
