#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""交互标注 API 路由"""

from typing import Annotated

from fastapi import APIRouter, Path, Query, Request

from backend.app.question_bank.schema.interaction import (
    AnchorType,
    BatchCreateMaterialAnchorParam,
    CreateMaterialAnchorParam,
    CreateQuestionInteractionAnnotationParam,
    DeleteInteractionIdsParam,
    GetMaterialBlocksResult,
    GetMaterialAnchorDetail,
    GetMaterialQuestionPreview,
    GetQuestionInteractionAnnotationDetail,
    MaterialAnchorQueryParam,
    QuestionInteractionAnnotationQueryParam,
    UpdateMaterialAnchorParam,
    UpdateQuestionInteractionAnnotationParam,
)
from backend.app.question_bank.service.interaction_service import interaction_annotation_service
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.rbac import DependsRBAC
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get(
    '/materials/{material_id}/blocks',
    summary='解析材料顺序分块',
    name='qbank_get_interaction_material_blocks',
    dependencies=[DependsRBAC],
)
async def get_interaction_material_blocks(
    db: CurrentSession,
    material_id: Annotated[int, Path(description='材料 ID')],
) -> ResponseSchemaModel[GetMaterialBlocksResult]:
    """🔐 管理员接口 - 解析材料顺序分块"""
    data = await interaction_annotation_service.get_material_blocks(db=db, material_id=material_id)
    return response_base.success(data=data)


@router.get(
    '/materials/{material_id}/questions',
    summary='获取材料关联题目预览',
    name='qbank_get_interaction_material_questions',
    dependencies=[DependsRBAC],
)
async def get_interaction_material_questions(
    db: CurrentSession,
    material_id: Annotated[int, Path(description='材料 ID')],
) -> ResponseSchemaModel[list[GetMaterialQuestionPreview]]:
    """🔐 管理员接口 - 获取材料关联题目预览"""
    data = await interaction_annotation_service.get_material_questions(db=db, material_id=material_id)
    return response_base.success(data=data)


@router.get('/anchors', summary='获取材料锚点列表', name='qbank_get_material_anchor_list', dependencies=[DependsRBAC])
async def get_material_anchor_list(
    db: CurrentSession,
    material_id: Annotated[int | None, Query(description='材料 ID')] = None,
    anchor_type: Annotated[AnchorType | None, Query(description='锚点类型')] = None,
    role: Annotated[str | None, Query(description='锚点角色')] = None,
    status: Annotated[int | None, Query(description='状态')] = None,
) -> ResponseSchemaModel[list[GetMaterialAnchorDetail]]:
    """🔐 管理员接口 - 获取材料锚点列表"""
    params = MaterialAnchorQueryParam(
        material_id=material_id,
        anchor_type=anchor_type,
        role=role,
        status=status,
    )
    data = await interaction_annotation_service.get_anchor_list(db=db, params=params)
    return response_base.success(data=data)


@router.post('/anchors', summary='创建材料锚点', name='qbank_create_material_anchor', dependencies=[DependsRBAC])
async def create_material_anchor(
    request: Request,
    db: CurrentSessionTransaction,
    obj: CreateMaterialAnchorParam,
) -> ResponseSchemaModel[GetMaterialAnchorDetail]:
    """🔐 管理员接口 - 创建材料锚点"""
    data = await interaction_annotation_service.create_anchor(db=db, obj=obj, created_by=request.user.id)
    return response_base.success(data=data)


@router.post(
    '/anchors/batch',
    summary='批量创建材料锚点',
    name='qbank_batch_create_material_anchor',
    dependencies=[DependsRBAC],
)
async def batch_create_material_anchor(
    request: Request,
    db: CurrentSessionTransaction,
    obj: BatchCreateMaterialAnchorParam,
) -> ResponseSchemaModel[list[GetMaterialAnchorDetail]]:
    """🔐 管理员接口 - 批量创建材料锚点"""
    data = await interaction_annotation_service.create_anchors(db=db, obj=obj, created_by=request.user.id)
    return response_base.success(data=data)


@router.put('/anchors/{pk}', summary='更新材料锚点', name='qbank_update_material_anchor', dependencies=[DependsRBAC])
async def update_material_anchor(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='锚点 ID')],
    obj: UpdateMaterialAnchorParam,
) -> ResponseModel:
    """🔐 管理员接口 - 更新材料锚点"""
    count = await interaction_annotation_service.update_anchor(
        db=db,
        pk=pk,
        obj=obj,
        updated_by=request.user.id,
    )
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete('/anchors', summary='删除材料锚点', name='qbank_delete_material_anchor', dependencies=[DependsRBAC])
async def delete_material_anchor(
    db: CurrentSessionTransaction,
    obj: DeleteInteractionIdsParam,
) -> ResponseModel:
    """🔐 管理员接口 - 删除材料锚点"""
    count = await interaction_annotation_service.delete_anchors(db=db, obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.get(
    '/annotations',
    summary='获取题目交互标注列表',
    name='qbank_get_question_interaction_annotation_list',
    dependencies=[DependsRBAC],
)
async def get_question_interaction_annotation_list(
    db: CurrentSession,
    question_id: Annotated[int | None, Query(description='题目 ID')] = None,
    material_id: Annotated[int | None, Query(description='材料 ID')] = None,
    interaction_type: Annotated[str | None, Query(description='交互类型')] = None,
    is_default: Annotated[bool | None, Query(description='是否默认使用')] = None,
    status: Annotated[int | None, Query(description='状态')] = None,
) -> ResponseSchemaModel[list[GetQuestionInteractionAnnotationDetail]]:
    """🔐 管理员接口 - 获取题目交互标注列表"""
    params = QuestionInteractionAnnotationQueryParam(
        question_id=question_id,
        material_id=material_id,
        interaction_type=interaction_type,
        is_default=is_default,
        status=status,
    )
    data = await interaction_annotation_service.get_annotation_list(db=db, params=params)
    return response_base.success(data=data)


@router.post(
    '/annotations',
    summary='创建题目交互标注',
    name='qbank_create_question_interaction_annotation',
    dependencies=[DependsRBAC],
)
async def create_question_interaction_annotation(
    request: Request,
    db: CurrentSessionTransaction,
    obj: CreateQuestionInteractionAnnotationParam,
) -> ResponseSchemaModel[GetQuestionInteractionAnnotationDetail]:
    """🔐 管理员接口 - 创建题目交互标注"""
    data = await interaction_annotation_service.create_annotation(db=db, obj=obj, created_by=request.user.id)
    return response_base.success(data=data)


@router.put(
    '/annotations/{pk}',
    summary='更新题目交互标注',
    name='qbank_update_question_interaction_annotation',
    dependencies=[DependsRBAC],
)
async def update_question_interaction_annotation(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='标注 ID')],
    obj: UpdateQuestionInteractionAnnotationParam,
) -> ResponseModel:
    """🔐 管理员接口 - 更新题目交互标注"""
    count = await interaction_annotation_service.update_annotation(
        db=db,
        pk=pk,
        obj=obj,
        updated_by=request.user.id,
    )
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete(
    '/annotations',
    summary='删除题目交互标注',
    name='qbank_delete_question_interaction_annotation',
    dependencies=[DependsRBAC],
)
async def delete_question_interaction_annotation(
    db: CurrentSessionTransaction,
    obj: DeleteInteractionIdsParam,
) -> ResponseModel:
    """🔐 管理员接口 - 删除题目交互标注"""
    count = await interaction_annotation_service.delete_annotations(db=db, obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()
