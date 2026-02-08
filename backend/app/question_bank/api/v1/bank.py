#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from backend.app.question_bank.schema.bank import (
    CreateBankParam,
    DeleteBankParam,
    GetBankDetail,
    GetBankDetailWithChapters,
    UpdateBankParam,
)
from backend.app.question_bank.schema.question import GetQuestionWithAnswer
from backend.app.question_bank.service.bank_service import bank_service
from backend.app.question_bank.service.question_service import question_service
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.permission import RequestPermission
from backend.common.security.rbac import DependsRBAC
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get('/recommend', summary='获取推荐题库', name='qbank_get_recommend_banks')
async def get_recommend_banks(
    db: CurrentSession,
) -> ResponseSchemaModel[list[GetBankDetail]]:
    """🌍 公开接口 - 获取全局热门推荐题库（最近7天做题最多的前5个）"""
    data = await bank_service.get_recommend_banks(db=db)
    return response_base.success(data=data)


@router.get('/{pk}', summary='获取题库详情', name='qbank_get_bank')
async def get_bank(
    db: CurrentSession, pk: Annotated[int, Path(description='题库 ID')]
) -> ResponseSchemaModel[GetBankDetailWithChapters]:
    """🌍 公开接口 - 任何人都可以查看题库详情（含章节树）"""
    data = await bank_service.get(db=db, pk=pk)
    data = await bank_service.get(db=db, pk=pk)
    return response_base.success(data=data)


@router.get(
    '/{pk}/questions/all',
    summary='获取题库下所有题目（含答案）',
    name='qbank_get_bank_questions_all',
)
async def get_bank_questions_all(
    db: CurrentSession, pk: Annotated[int, Path(description='题库 ID')]
) -> ResponseSchemaModel[list[GetQuestionWithAnswer]]:
    """
    🌍 公开接口 - 获取指定题库下的所有题目（包含答案和解析）
    
    - 不分页，一次性返回所有
    - 用于导出或离线使用
    """
    # 验证题库是否存在
    await bank_service.get(db=db, pk=pk)
    
    # 获取题目列表（不分页）
    data = await question_service.get_list(
        db=db,
        bank_id=pk,
        page=None,
        size=None,
        include_analysis=True,
    )
    
    # 构造包含答案的返回数据
    result_with_answer = []
    if isinstance(data, list):
         for q in data:
            # 动态添加字段到 ORM 对象
            if hasattr(q, 'analysis') and q.analysis:
                q.answer_data = q.analysis.answer_data
                q.analysis_content = q.analysis.content
            else:
                q.answer_data = None
                q.analysis_content = None
            
            # 手动提取材料数据
            if hasattr(q, 'materials') and q.materials:
                 q.materials_data = [{'id': m.id, 'content': m.content} for m in q.materials]
            else:
                 q.materials_data = []

            # 注意：Pydantic model_validate 会从 dict 或 object 属性读取
            # 这里我们需要确保 materials 字段被正确填充
            # 由于 ORM 对象 q 没有 materials_data 属性，且 schema 字段名为 materials
            # 我们可以构造一个 dict 来 validate，或者给 q 动态添加属性（如果是 object）
            
            # 为了简单起见，且避免污染 ORM 对象，由于 GetQuestionWithAnswer 是 from_attributes=True
            # 我们可以先转成 dict
            
            q_dict = {
                'id': q.id,
                'bank_id': q.bank_id,
                'chapter_id': q.chapter_id,
                'type': q.type,
                'stem': q.stem,
                'options_data': q.options_data,
                'difficulty': q.difficulty,
                'score': q.score,
                'knowledge_point': q.knowledge_point,
                'is_active': q.is_active,
                'review_status': q.review_status,
                'created_time': q.created_time,
                'bank_name': q.bank.name if q.bank else None,
                'chapter_name': q.chapter.name if q.chapter else None,
                'answer_data': q.answer_data,
                'analysis_content': q.analysis_content,
                'materials': [{'id': m.id, 'content': m.content} for m in q.materials] if q.materials else [],
                'analyses': q.analyses if q.analyses else []
            }
            
            result_with_answer.append(GetQuestionWithAnswer.model_validate(q_dict))
            
    return response_base.success(data=result_with_answer)


@router.get('', summary='获取题库树形列表', name='qbank_get_bank_list')
async def get_bank_list(
    db: CurrentSession,
    cat_id: Annotated[int | None, Query(description='分类 ID')] = None,
    status: Annotated[int | None, Query(description='题库状态')] = None,
    scope: Annotated[int | None, Query(description='可见范围')] = None,
    keyword: Annotated[str | None, Query(description='关键字搜索')] = None,
    type: Annotated[int | None, Query(description='类型: 10=题库, 20=合集')] = None,
    parent_id: Annotated[int | None, Query(description='父级题库 ID')] = None,
) -> ResponseModel:
    """🌍 公开接口 - 任何人都可以查看题库树形列表"""
    data = await bank_service.get_list(db=db, cat_id=cat_id, status=status, scope=scope, keyword=keyword, type=type, parent_id=parent_id)
    return response_base.success(data=data)


@router.post(
    '',
    summary='创建题库',
    name='qbank_create_bank',
    dependencies=[
        Depends(RequestPermission('question_bank:bank:create')),
        DependsRBAC,
    ],
)
async def create_bank(db: CurrentSessionTransaction, obj: CreateBankParam) -> ResponseModel:
    """🔐 管理员接口 - 只有管理员可以创建题库"""
    await bank_service.create(db=db, obj=obj)
    return response_base.success()


@router.put(
    '/{pk}',
    summary='更新题库',
    name='qbank_update_bank',
    dependencies=[
        Depends(RequestPermission('question_bank:bank:update')),
        DependsRBAC,
    ],
)
async def update_bank(
    db: CurrentSessionTransaction, pk: Annotated[int, Path(description='题库 ID')], obj: UpdateBankParam
) -> ResponseModel:
    """🔐 管理员接口 - 只有管理员可以更新题库"""
    count = await bank_service.update(db=db, pk=pk, obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete(
    '',
    summary='删除题库',
    name='qbank_delete_bank',
    dependencies=[
        Depends(RequestPermission('question_bank:bank:delete')),
        DependsRBAC,
    ],
)
async def delete_bank(db: CurrentSessionTransaction, obj: DeleteBankParam) -> ResponseModel:
    """🔐 管理员接口 - 只有管理员可以删除题库"""
    count = await bank_service.delete(db=db, obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()
