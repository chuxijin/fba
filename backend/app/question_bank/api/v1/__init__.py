#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import APIRouter

from backend.app.question_bank.api.v1.activation import router as activation_router
from backend.app.question_bank.api.v1.auth import router as auth_router
from backend.app.question_bank.api.v1.bank import router as bank_router
from backend.app.question_bank.api.v1.banner import router as banner_router
from backend.app.question_bank.api.v1.chapter import router as chapter_router
from backend.app.question_bank.api.v1.customer import router as customer_router
from backend.app.question_bank.api.v1.device import router as device_router
from backend.app.question_bank.api.v1.favorite import router as favorite_router
from backend.app.question_bank.api.v1.home import router as home_router
from backend.app.question_bank.api.v1.material import router as material_router
from backend.app.question_bank.api.v1.membership import router as membership_router
from backend.app.question_bank.api.v1.note import router as note_router
from backend.app.question_bank.api.v1.notice import router as notice_router
from backend.app.question_bank.api.v1.practice import router as practice_router
from backend.app.question_bank.api.v1.question import router as question_router
from backend.app.question_bank.api.v1.session import router as session_router
from backend.app.question_bank.api.v1.upload import router as upload_router
from backend.app.question_bank.api.v1.user_settings import router as user_settings_router
from backend.app.question_bank.api.v1.wrong_question import router as wrong_question_router

router = APIRouter(prefix='/qbank')

router.include_router(auth_router, prefix='/auth', tags=['认证'])
router.include_router(customer_router, prefix='/customer', tags=['用户'])
router.include_router(user_settings_router, prefix='/settings', tags=['用户设置'])
router.include_router(device_router, prefix='/device', tags=['设备管理'])
router.include_router(home_router, prefix='/home', tags=['首页'])
router.include_router(banner_router, prefix='/banners', tags=['轮播图'])
router.include_router(notice_router, prefix='/notices', tags=['通知栏'])
router.include_router(bank_router, prefix='/banks', tags=['题库'])
router.include_router(chapter_router, prefix='/chapters', tags=['题库章节'])
router.include_router(material_router, prefix='/materials', tags=['题目材料'])
router.include_router(question_router, prefix='/questions', tags=['题目'])
router.include_router(membership_router, prefix='/memberships', tags=['会员权益'])
router.include_router(activation_router, tags=['激活码'])
router.include_router(practice_router, prefix='/practice', tags=['刷题'])
router.include_router(session_router, prefix='/sessions', tags=['练习会话'])
router.include_router(wrong_question_router, prefix='/wrong-questions', tags=['错题本'])
router.include_router(note_router, prefix='/notes', tags=['笔记'])
router.include_router(favorite_router, prefix='/favorites', tags=['收藏'])
router.include_router(upload_router, prefix='/upload', tags=['文件上传'])
