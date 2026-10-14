#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""skill 题库只读端点：OpenAuth 认证 + 会员闸门 + 复用 question_bank_v2 只读服务"""

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Path, Query

from backend.app.admin.service.category_service import category_service
from backend.app.question_bank_v2.crud.crud_knowledge import question_knowledge_point_dao
from backend.app.question_bank_v2.schema.bank import GetBankListItem
from backend.app.question_bank_v2.schema.knowledge import GetKnowledgeSystemListItem
from backend.app.question_bank_v2.schema.question import GetQuestionDetail, GetQuestionListItem
from backend.app.question_bank_v2.service.bank_service import bank_service
from backend.app.question_bank_v2.service.knowledge_service import knowledge_service
from backend.app.question_bank_v2.service.question_service import question_service
from backend.app.skill.service import ensure_skill_access
from backend.common.pagination import DependsPagination, PageData, paging_data
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.database.db import CurrentSessionTransaction
from backend.plugin.openauth.dependencies import RequireOpenAuth
from backend.plugin.openauth.schema.authorization import GetOpenAuthCheckResult

router = APIRouter()

QbankIdentity = Annotated[GetOpenAuthCheckResult, Depends(RequireOpenAuth('qbank:read'))]


@router.get('/qbank/categories', summary='获取题库分类树（只读）')
async def skill_get_qbank_categories(
    db: CurrentSessionTransaction,
    identity: QbankIdentity,
    app_code: Annotated[str, Query(min_length=1, max_length=64)] = 'youanshang',
    category_type: Annotated[
        Literal['product_catalog', 'knowledge_point', 'resource_exam'], Query(description='分类类型')
    ] = 'product_catalog',
    include_disabled: Annotated[bool, Query(description='是否包含停用分类')] = False,
) -> ResponseSchemaModel[list[dict[str, Any]]]:
    """返回分类树；题库检索用的 category_id 取这里 `product_catalog` 树下的节点 ID"""
    await ensure_skill_access(db, user_id=identity.user_id)
    data = await category_service.get_tree(
        db=db,
        app_code=app_code,
        type_=category_type,
        status=None if include_disabled else True,
    )
    return response_base.success(data=data)


@router.get('/qbank/banks', summary='获取已发布题库目录', dependencies=[DependsPagination])
async def skill_get_qbank_banks(
    db: CurrentSessionTransaction,
    identity: QbankIdentity,
    category_id: Annotated[int | None, Query(gt=0, description='业务分类 ID')] = None,
    bank_kind: Annotated[
        Literal['practice', 'paper', 'mock'] | None, Query(description='题库用途类型')
    ] = None,
    keyword: Annotated[str | None, Query(max_length=80, description='题库名称关键字')] = None,
) -> ResponseSchemaModel[PageData[GetBankListItem]]:
    """OpenAuth 用户获取当前已发布的公开题库列表（分页）"""
    await ensure_skill_access(db, user_id=identity.user_id)
    stmt = await bank_service.get_select(
        db=db,
        category_id=category_id,
        include_descendants=True,
        bank_kind=bank_kind,
        keyword=keyword,
    )
    return response_base.success(data=await paging_data(db, stmt, GetBankListItem))


@router.get('/qbank/questions', summary='检索题库题目', dependencies=[DependsPagination])
async def skill_get_qbank_questions(
    db: CurrentSessionTransaction,
    identity: QbankIdentity,
    bank_id: Annotated[int | None, Query(gt=0, description='题库 ID')] = None,
    question_type: Annotated[QuestionType | None, Query(description='题型')] = None,
    keyword: Annotated[str | None, Query(max_length=200, description='题干关键字')] = None,
    knowledge_point_ids: Annotated[str | None, Query(description='知识点 ID 列表，逗号分隔')] = None,
) -> ResponseSchemaModel[PageData[GetQuestionListItem]]:
    """OpenAuth 用户按题库 / 题型 / 关键字 / 知识点检索题目（分页，不含答案解析）"""
    await ensure_skill_access(db, user_id=identity.user_id)
    parsed_knowledge_point_ids: list[int] | None = None
    if knowledge_point_ids:
        parsed_knowledge_point_ids = [int(k.strip()) for k in knowledge_point_ids.split(',') if k.strip()]
    stmt = await question_service.get_list_select(
        db=db,
        bank_id=bank_id,
        question_type=question_type,
        keyword=keyword,
        knowledge_point_ids=parsed_knowledge_point_ids,
    )
    return response_base.success(data=await paging_data(db, stmt, GetQuestionListItem))


@router.get('/qbank/knowledge-systems/{system_id}/points', summary='获取知识点树（只读）')
async def skill_get_knowledge_points_tree(
    db: CurrentSessionTransaction,
    identity: QbankIdentity,
    system_id: Annotated[int, Path(gt=0, description='知识体系 ID')],
) -> ResponseSchemaModel:
    """按知识体系拉知识点树，供 qbank-search 的 knowledge_point_ids 使用"""
    await ensure_skill_access(db, user_id=identity.user_id)
    data = await knowledge_service.get_points_tree(db=db, system_id=system_id)
    return response_base.success(data=data)


@router.get('/qbank/knowledge-systems', summary='获取知识体系列表（只读）', dependencies=[DependsPagination])
async def skill_get_knowledge_systems(
    db: CurrentSessionTransaction,
    identity: QbankIdentity,
    domain_category_id: Annotated[
        int | None, Query(gt=0, description='领域分类 ID；默认取当前用户默认领域')
    ] = None,
) -> ResponseSchemaModel:
    """列出知识体系（按领域分类隔离）；拿到 system_id 后续查知识点树"""
    await ensure_skill_access(db, user_id=identity.user_id)
    stmt = knowledge_service.get_systems_select(domain_category_id=domain_category_id)
    return response_base.success(data=await paging_data(db, stmt, GetKnowledgeSystemListItem))


@router.get('/qbank/questions/{pk}', summary='获取题目详情')
async def skill_get_qbank_question_detail(
    db: CurrentSessionTransaction,
    identity: QbankIdentity,
    pk: Annotated[int, Path(gt=0, description='题目 ID')],
) -> ResponseSchemaModel[GetQuestionDetail]:
    """OpenAuth 用户获取题目聚合详情（含材料、选项、答案、解析、知识点）"""
    await ensure_skill_access(db, user_id=identity.user_id)
    data = await question_service.get(db=db, pk=pk)
    return response_base.success(data=data)
