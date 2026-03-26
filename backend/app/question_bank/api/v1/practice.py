#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Path, Query, Request

from backend.app.question_bank.schema.question import (
    GetQuestionDetail,
    GetQuestionListItem,
    QuestionAnalysisItem,
)
from backend.common.security.jwt import DependsJwtAuth
from backend.app.question_bank.service.membership_service import membership_service
from backend.app.question_bank.service.practice_service import practice_service
from backend.app.question_bank.service.question_service import question_service
from backend.common.exception import errors
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.permission import verify_permission
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get('/questions', summary='获取练习题目列表', name='practice_get_questions')
async def get_practice_questions(
    db: CurrentSession,
    request: Request, _token: str = DependsJwtAuth,
    bank_id: Annotated[int | None, Query(description='题库 ID')] = None,
    chapter_id: Annotated[int | None, Query(description='章节 ID')] = None,
    type: Annotated[str | None, Query(description='题型')] = None,
    difficulty: Annotated[str | None, Query(description='难度')] = None,
) -> ResponseSchemaModel[list[GetQuestionListItem]]:
    """
    客户端刷题接口 - 获取可练习的题目列表（不含答案）

    支持按题库、章节、题型、难度筛选题目
    只返回已启用且审核通过的题目
    """
    if bank_id:
        perm_key = f'practice:bank:{bank_id}'
        if not await verify_permission(request, perm_key):
            raise errors.ForbiddenError(msg=f'您没有该题库的刷题权限(需权限: {perm_key})')

    if bank_id and chapter_id:
        await membership_service.verify_bank_chapter_access(
            db=db,
            user_id=request.user.id,
            bank_id=bank_id,
            chapter_id=chapter_id,
        )
    elif bank_id:
        await membership_service.verify_bank_list_access(db=db, user_id=request.user.id, bank_id=bank_id)
    elif chapter_id:
        await membership_service.verify_chapter_access(db=db, user_id=request.user.id, chapter_id=chapter_id)

    questions = await practice_service.get_practice_questions(
        db=db, bank_id=bank_id, chapter_id=chapter_id, type=type, difficulty=difficulty,
    )

    result = [
        question_service.serialize_question(question=q, bank_id=bank_id, chapter_id=chapter_id)
        for q in questions
    ]
    return response_base.success(data=result)


@router.get('/banks/{bank_id}/questions', summary='获取题库题目列表', name='practice_get_bank_questions')
async def get_bank_questions(
    db: CurrentSession,
    bank_id: Annotated[int, Path(description='题库 ID')],
    request: Request, _token: str = DependsJwtAuth,
    type: Annotated[str | None, Query(description='题型')] = None,
    difficulty: Annotated[str | None, Query(description='难度')] = None,
) -> ResponseSchemaModel[list[GetQuestionListItem]]:
    """客户端刷题接口 - 获取指定题库的题目列表（不含答案）"""
    await membership_service.verify_bank_list_access(db=db, user_id=request.user.id, bank_id=bank_id)

    questions = await practice_service.get_practice_questions(
        db=db, bank_id=bank_id, type=type, difficulty=difficulty,
    )
    result = [question_service.serialize_question(question=q, bank_id=bank_id) for q in questions]
    return response_base.success(data=result)


@router.get('/chapters/{chapter_id}/questions', summary='获取章节题目列表', name='practice_get_chapter_questions')
async def get_chapter_questions(
    db: CurrentSession,
    chapter_id: Annotated[int, Path(description='章节 ID')],
    request: Request, _token: str = DependsJwtAuth,
    type: Annotated[str | None, Query(description='题型')] = None,
    difficulty: Annotated[str | None, Query(description='难度')] = None,
) -> ResponseSchemaModel[list[GetQuestionListItem]]:
    """客户端刷题接口 - 获取指定章节的题目列表（不含答案）"""
    await membership_service.verify_chapter_access(db=db, user_id=request.user.id, chapter_id=chapter_id)

    questions = await practice_service.get_practice_questions(
        db=db, chapter_id=chapter_id, type=type, difficulty=difficulty,
    )
    result = [question_service.serialize_question(question=q, chapter_id=chapter_id) for q in questions]
    return response_base.success(data=result)


@router.get('/questions/{pk}', summary='获取题目详情（刷题）', name='practice_get_question')
async def get_question(
    db: CurrentSession,
    pk: Annotated[int, Path(description='题目 ID')],
    request: Request, _token: str = DependsJwtAuth,
) -> ResponseSchemaModel[GetQuestionDetail]:
    """客户端刷题接口 - 获取题目详情用于练习（不含答案）"""
    await membership_service.verify_question_access(db=db, user_id=request.user.id, question_id=pk)

    question = await practice_service.get_question_for_practice(db=db, question_id=pk)
    return response_base.success(data=question)


@router.get('/questions/{pk}/analysis', summary='查看题目解析', name='practice_get_analysis')
async def get_analysis(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='题目 ID')],
    request: Request, _token: str = DependsJwtAuth,
) -> ResponseSchemaModel[QuestionAnalysisItem]:
    """
    客户端刷题接口 - 查看题目解析（含答案）

    通常在提交答案后查看，会自动增加解析的查看次数
    """
    await membership_service.verify_question_access(db=db, user_id=request.user.id, question_id=pk)

    analysis = await practice_service.get_practice_analysis(db=db, question_id=pk)
    return response_base.success(data=analysis)



