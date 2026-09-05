#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Query, Request

from backend.app.gongkao.schema.hanyu_quiz import GetQuizSession, SubmitQuizParam, SubmitQuizResult
from backend.app.gongkao.service.hanyu_quiz_service import hanyu_quiz_service
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession

router = APIRouter()


@router.get('/session', summary='获取选词检验会话', response_model=ResponseSchemaModel[GetQuizSession])
async def get_quiz_session(
    request: Request,
    db: CurrentSession,
    quiz_type: Annotated[str, Query(description='模式: meaning_to_word-看释义选词, word_to_meaning-看词选释义')] = 'meaning_to_word',
    count: Annotated[int, Query(ge=5, le=30, description='题量 (5-30)')] = 10,
):
    """全局随机抽取成语并智能生成干扰项会话"""
    data = await hanyu_quiz_service.generate_quiz_session(
        db=db,
        quiz_type=quiz_type,
        count=count,
    )
    return response_base.success(data=data)


@router.post('/submit', summary='提交选词检验结果', dependencies=[DependsJwtAuth], response_model=ResponseSchemaModel[SubmitQuizResult])
async def submit_quiz(
    request: Request,
    db: CurrentSession,
    obj: SubmitQuizParam,
):
    """提交检验答题结果并结算打卡"""
    result = await hanyu_quiz_service.submit_quiz(
        db=db,
        user_id=request.user.id,
        obj=obj,
    )
    return response_base.success(data=result)
