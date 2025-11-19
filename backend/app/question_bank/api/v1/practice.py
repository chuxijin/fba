#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
刷题接口

设计原则：
- 客户端专用的刷题流程接口
- 提供简洁的刷题体验：获取题目 → 做题 → 提交答案 → 查看解析
- 与 question.py 的区别：更贴近刷题场景，接口设计更简化
"""
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Body, Path, Query

from backend.app.question_bank.schema.question import (
    BatchSubmitAnswerParam,
    BatchSubmitAnswerResult,
    GetQuestionAnalysisDetail,
    GetQuestionDetail,
    GetQuestionListItem,
)
from backend.app.question_bank.security import DependsCustomerAuth
from backend.app.question_bank.service.membership_service import membership_service
from backend.app.question_bank.service.practice_service import practice_service
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.auth_strategy import AuthUser
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get('/questions', summary='获取练习题目列表', name='practice_get_questions')
async def get_practice_questions(
    db: CurrentSession,
    current_user: AuthUser = DependsCustomerAuth,
    bank_id: Annotated[int | None, Query(description='题库 ID')] = None,
    chapter_id: Annotated[int | None, Query(description='章节 ID')] = None,
    type: Annotated[str | None, Query(description='题型')] = None,
    difficulty: Annotated[str | None, Query(description='难度')] = None,
) -> ResponseSchemaModel[list[GetQuestionListItem]]:
    """
    👤 客户端刷题接口 - 获取可练习的题目列表（不含答案）

    支持按题库、章节、题型、难度筛选题目
    只返回已启用且审核通过的题目
    """
    # 验证会员权限
    if bank_id:
        await membership_service.verify_bank_list_access(db=db, user_id=current_user.user_id, bank_id=bank_id)
    elif chapter_id:
        await membership_service.verify_chapter_access(db=db, user_id=current_user.user_id, chapter_id=chapter_id)

    questions = await practice_service.get_practice_questions(
        db=db,
        bank_id=bank_id,
        chapter_id=chapter_id,
        type=type,
        difficulty=difficulty,
    )

    # 手动添加 bank_name 和 chapter_name 字段
    result = []
    for q in questions:
        question_dict = GetQuestionListItem.model_validate(q).model_dump()
        # 从关联对象中提取名称
        question_dict['bank_name'] = q.bank.name if q.bank else None
        question_dict['chapter_name'] = q.chapter.name if q.chapter else None
        result.append(GetQuestionListItem(**question_dict))

    return response_base.success(data=result)


@router.get('/banks/{bank_id}/questions', summary='获取题库题目列表', name='practice_get_bank_questions')
async def get_bank_questions(
    db: CurrentSession,
    bank_id: Annotated[int, Path(description='题库 ID')],
    current_user: AuthUser = DependsCustomerAuth,
    type: Annotated[str | None, Query(description='题型')] = None,
    difficulty: Annotated[str | None, Query(description='难度')] = None,
) -> ResponseSchemaModel[list[GetQuestionListItem]]:
    """
    👤 客户端刷题接口 - 获取指定题库的题目列表（不含答案）

    快捷接口，等同于 GET /practice/questions?bank_id={bank_id}
    """
    await membership_service.verify_bank_list_access(db=db, user_id=current_user.user_id, bank_id=bank_id)

    questions = await practice_service.get_practice_questions(
        db=db,
        bank_id=bank_id,
        type=type,
        difficulty=difficulty,
    )

    # 手动添加 bank_name 和 chapter_name 字段
    result = []
    for q in questions:
        question_dict = GetQuestionListItem.model_validate(q).model_dump()
        # 从关联对象中提取名称
        question_dict['bank_name'] = q.bank.name if q.bank else None
        question_dict['chapter_name'] = q.chapter.name if q.chapter else None
        result.append(GetQuestionListItem(**question_dict))

    return response_base.success(data=result)


@router.get('/chapters/{chapter_id}/questions', summary='获取章节题目列表', name='practice_get_chapter_questions')
async def get_chapter_questions(
    db: CurrentSession,
    chapter_id: Annotated[int, Path(description='章节 ID')],
    current_user: AuthUser = DependsCustomerAuth,
    type: Annotated[str | None, Query(description='题型')] = None,
    difficulty: Annotated[str | None, Query(description='难度')] = None,
) -> ResponseSchemaModel[list[GetQuestionListItem]]:
    """
    👤 客户端刷题接口 - 获取指定章节的题目列表（不含答案）

    快捷接口，等同于 GET /practice/questions?chapter_id={chapter_id}
    """
    await membership_service.verify_chapter_access(db=db, user_id=current_user.user_id, chapter_id=chapter_id)

    questions = await practice_service.get_practice_questions(
        db=db,
        chapter_id=chapter_id,
        type=type,
        difficulty=difficulty,
    )

    # 手动添加 bank_name 和 chapter_name 字段
    result = []
    for q in questions:
        question_dict = GetQuestionListItem.model_validate(q).model_dump()
        # 从关联对象中提取名称
        question_dict['bank_name'] = q.bank.name if q.bank else None
        question_dict['chapter_name'] = q.chapter.name if q.chapter else None
        result.append(GetQuestionListItem(**question_dict))

    return response_base.success(data=result)


@router.get('/questions/{pk}', summary='获取题目详情（刷题）', name='practice_get_question')
async def get_question(
    db: CurrentSession,
    pk: Annotated[int, Path(description='题目 ID')],
    current_user: AuthUser = DependsCustomerAuth,
) -> ResponseSchemaModel[GetQuestionDetail]:
    """
    👤 客户端刷题接口 - 获取题目详情用于练习（不含答案）

    用于开始做题前查看题目内容
    """
    await membership_service.verify_question_access(db=db, user_id=current_user.user_id, question_id=pk)

    question = await practice_service.get_question_for_practice(db=db, question_id=pk)
    return response_base.success(data=question)


@router.get('/questions/{pk}/analysis', summary='查看题目解析', name='practice_get_analysis')
async def get_analysis(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='题目 ID')],
    current_user: AuthUser = DependsCustomerAuth,
) -> ResponseSchemaModel[GetQuestionAnalysisDetail]:
    """
    👤 客户端刷题接口 - 查看题目解析（含答案）

    通常在提交答案后查看
    会自动增加解析的查看次数
    """
    await membership_service.verify_question_access(db=db, user_id=current_user.user_id, question_id=pk)

    analysis = await practice_service.get_practice_analysis(db=db, question_id=pk)
    return response_base.success(data=analysis)


@router.post('/submit', summary='提交答案', name='practice_submit_answer')
async def submit_answer(
    db: CurrentSessionTransaction,
    obj: BatchSubmitAnswerParam,
    current_user: AuthUser = DependsCustomerAuth,
) -> ResponseSchemaModel[BatchSubmitAnswerResult]:
    """
    👤 客户端刷题接口 - 批量提交答案并获得判分结果（适合考试/试卷场景）

    一次性提交多道题的答案，返回整体统计和每道题的结果

    **适用场景**：
    - 模拟考试（提交整张试卷）
    - 章节测试（提交一组题目）
    - 闯关模式（批量提交一关的所有题目）

    **参数说明**：
    - `answers`: 题目答案列表
    - `include_analysis`: 是否在结果中包含每道题的解析内容（默认 false）
      - `false`: 只返回对错和正确答案（适合先看成绩，再选择性查看解析）
      - `true`: 同时返回每道题的详细解析（适合提交后立即显示全部解析）

    **提交后会自动更新所有题目的统计数据**
    """
    # 验证用户对所有题目的访问权限（批量验证）
    for answer_item in obj.answers:
        await membership_service.verify_question_access(
            db=db,
            user_id=current_user.user_id,
            question_id=answer_item.question_id,
        )

    # 调用服务层批量判分
    from backend.app.question_bank.service.question_service import question_service
    result = await question_service.batch_submit_answer(db=db, obj=obj)

    return response_base.success(data=result)

