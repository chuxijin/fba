#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Body, Path, Query, Request

from backend.app.question_bank.crud.crud_question_favorite import question_favorite_dao
from backend.app.question_bank.schema.favorite import (
    ClearFolderParam,
    CreateQuestionFavoriteParam,
    GetQuestionFavoriteDetail,
    GetQuestionFavoriteListItem,
    UpdateQuestionFavoriteParam,
)
from backend.app.question_bank.schema.wrong_question import WrongQuestionGroupItem
from backend.app.question_bank.service.favorite_service import favorite_service
from backend.app.question_bank.service.membership_service import membership_service
from backend.common.pagination import DependsPagination, PageData, paging_data
from backend.common.response.response_code import CustomResponse
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


# ============ 收藏管理接口 ============
# 重要：具体路径的路由必须放在通配路由（/{pk}）之前，否则会被通配路由拦截


@router.post('', summary='收藏题目', name='qbank_favorite_create', dependencies=[DependsJwtAuth])
async def create_favorite(
    request: Request,
    db: CurrentSessionTransaction,
    obj: CreateQuestionFavoriteParam,
) -> ResponseSchemaModel[GetQuestionFavoriteDetail]:
    """收藏题目"""
    if obj.placement_id is not None:
        await membership_service.verify_placement_access(db=db, user_id=request.user.id, placement_id=obj.placement_id)
    else:
        await membership_service.verify_question_access(db=db, user_id=request.user.id, question_id=obj.question_id)

    new_favorite = await favorite_service.create_favorite(db=db, user_id=request.user.id, obj=obj)
    return response_base.success(data=GetQuestionFavoriteDetail.model_validate(new_favorite))


@router.get('', summary='获取收藏列表', name='qbank_favorite_get_list', dependencies=[DependsJwtAuth, DependsPagination])
async def get_favorites(
    request: Request,
    db: CurrentSession,
    folder_name: Annotated[str | None, Query(description='收藏夹名称')] = None,
    is_pinned: Annotated[bool | None, Query(description='是否置顶')] = None,
) -> ResponseSchemaModel[PageData[GetQuestionFavoriteListItem]]:
    """获取用户的收藏列表（分页）"""
    stmt = await question_favorite_dao.get_select(
        user_id=request.user.id, folder_name=folder_name, is_pinned=is_pinned
    )
    page_data = await paging_data(db, stmt, GetQuestionFavoriteListItem)
    return response_base.success(data=page_data)


# ============ 收藏夹管理接口（具体路径，必须在 /{pk} 之前）============


@router.delete('/questions/{question_id}', summary='通过题目ID取消收藏', name='qbank_favorite_delete_by_question', dependencies=[DependsJwtAuth])
async def delete_favorite_by_question(
    request: Request,
    db: CurrentSessionTransaction,
    question_id: Annotated[int, Path(description='题目 ID')],
) -> ResponseModel:
    """通过题目ID直接取消收藏"""
    count = await favorite_service.delete_favorite_by_question(
        db=db, user_id=request.user.id, question_id=question_id
    )

    if count > 0:
        return response_base.success(res=CustomResponse(code=200, msg='取消收藏成功'))
    return response_base.success(res=CustomResponse(code=200, msg='该题目未收藏或已取消'))


@router.get('/folders', summary='获取收藏夹列表', name='qbank_favorite_get_folders', dependencies=[DependsJwtAuth])
async def get_folders(
    request: Request,
    db: CurrentSession,
) -> ResponseSchemaModel[list[str]]:
    """获取用户的所有收藏夹名称"""
    folders = await question_favorite_dao.get_user_folders(db=db, user_id=request.user.id)
    return response_base.success(data=folders)


@router.post('/folders/clear', summary='清空收藏夹', name='qbank_favorite_clear_folder', dependencies=[DependsJwtAuth])
async def clear_folder(
    request: Request,
    db: CurrentSessionTransaction,
    obj: ClearFolderParam,
) -> ResponseModel:
    """清空指定收藏夹"""
    count = await question_favorite_dao.clear_folder(db=db, user_id=request.user.id, folder_name=obj.folder_name)

    if count > 0:
        return response_base.success(res=CustomResponse(code=200, msg=f'成功清空收藏夹，删除 {count} 个收藏'))
    return response_base.success(res=CustomResponse(code=200, msg='收藏夹为空'))


# ============ 工具接口（具体路径，必须在 /{pk} 之前）============


@router.post('/questions/check', summary='检查题目收藏状态', name='qbank_favorite_check', dependencies=[DependsJwtAuth])
async def check_favorited(
    request: Request,
    db: CurrentSession,
    question_ids: Annotated[list[int], Body(description='题目 ID 列表（可以是单个或多个）')],
) -> ResponseSchemaModel[dict[int, bool]]:
    """批量检查题目的收藏状态"""
    status_map = await favorite_service.check_favorited(
        db=db, user_id=request.user.id, question_ids=question_ids
    )
    return response_base.success(data=status_map)


@router.get('/statistics', summary='获取收藏统计', name='qbank_favorite_statistics', dependencies=[DependsJwtAuth])
async def get_statistics(
    request: Request,
    db: CurrentSession,
    group_by: str | None = None,
    cat_id: int | None = None,
    kp_cat_id: int | None = None,
) -> ResponseSchemaModel:
    """获取用户的收藏统计数据，传 group_by 时返回树形分组"""
    if group_by:
        data = await favorite_service.get_statistics_with_groups(
            db=db, user_id=request.user.id, group_by=group_by, cat_id=cat_id, kp_cat_id=kp_cat_id,
        )
        return response_base.success(data=data)
    stats = await favorite_service.get_statistics(db=db, user_id=request.user.id, cat_id=cat_id, kp_cat_id=kp_cat_id)
    return response_base.success(data=stats)


@router.get('/grouped', summary='获取收藏分组聚合', name='qbank_favorite_grouped', dependencies=[DependsJwtAuth])
async def get_grouped(
    request: Request,
    db: CurrentSession,
    group_by: str = 'bank',
    cat_id: int | None = None,
    kp_cat_id: int | None = None,
) -> ResponseSchemaModel[list[WrongQuestionGroupItem]]:
    """按题库或知识点分组聚合收藏数量"""
    data = await favorite_service.get_grouped(
        db=db,
        user_id=request.user.id,
        group_by=group_by,
        cat_id=cat_id,
        kp_cat_id=kp_cat_id,
    )
    return response_base.success(data=data)


@router.get('/ids', summary='获取分组内收藏题目 ID 列表', name='qbank_favorite_ids', dependencies=[DependsJwtAuth])
async def get_question_ids(
    request: Request,
    db: CurrentSession,
    bank_id: int | None = None,
    chapter_id: int | None = None,
    knowledge_point: str | None = None,
) -> ResponseSchemaModel[list[int]]:
    """按分组条件获取收藏的题目 ID 列表"""
    if chapter_id is not None:
        bank_id = await membership_service.resolve_bank_context_for_chapter(
            db=db,
            chapter_id=chapter_id,
            bank_id=bank_id,
            user_id=request.user.id,
        )

    ids = await question_favorite_dao.get_question_ids(
        db=db, user_id=request.user.id, bank_id=bank_id, chapter_id=chapter_id, knowledge_point=knowledge_point,
    )
    return response_base.success(data=ids)


# ============ 通配路径接口（必须放在最后）============


@router.get('/{pk}', summary='获取收藏详情', name='qbank_favorite_get', dependencies=[DependsJwtAuth])
async def get_favorite(
    request: Request,
    db: CurrentSession,
    pk: Annotated[int, Path(description='收藏 ID')],
) -> ResponseSchemaModel[GetQuestionFavoriteDetail]:
    """获取收藏详情"""
    favorite = await favorite_service.get_favorite(db=db, favorite_id=pk, user_id=request.user.id)
    return response_base.success(data=GetQuestionFavoriteDetail.model_validate(favorite))


@router.put('/{pk}', summary='更新收藏', name='qbank_favorite_update', dependencies=[DependsJwtAuth])
async def update_favorite(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='收藏 ID')],
    obj: UpdateQuestionFavoriteParam,
) -> ResponseModel:
    """更新收藏信息"""
    count = await favorite_service.update_favorite(
        db=db,
        favorite_id=pk,
        user_id=request.user.id,
        folder_name=obj.folder_name,
        tags=obj.tags,
        remark=obj.remark,
    )

    if count > 0:
        return response_base.success()
    return response_base.fail(res=CustomResponse(code=400, msg='没有需要更新的数据'))


@router.put('/{pk}/pin', summary='设置收藏置顶', name='qbank_favorite_set_pin', dependencies=[DependsJwtAuth])
async def set_pin(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='收藏 ID')],
    is_pinned: Annotated[bool, Body(embed=True, description='是否置顶')],
) -> ResponseModel:
    """设置收藏置顶或取消置顶"""
    count = await favorite_service.set_pin(
        db=db, favorite_id=pk, user_id=request.user.id, is_pinned=is_pinned
    )

    if count > 0:
        return response_base.success()
    return response_base.fail(res=CustomResponse(code=400, msg='设置失败'))


@router.delete('', summary='取消收藏', name='qbank_favorite_delete', dependencies=[DependsJwtAuth])
async def delete_favorites(
    request: Request,
    db: CurrentSessionTransaction,
    favorite_ids: Annotated[list[int], Body(description='收藏 ID 列表（支持单个或批量）')],
) -> ResponseModel:
    """取消收藏题目（支持单个和批量）"""
    count = await favorite_service.delete_favorites(
        db=db, favorite_ids=favorite_ids, user_id=request.user.id
    )

    if count > 0:
        return response_base.success(res=CustomResponse(code=200, msg=f'成功取消 {count} 个收藏'))
    return response_base.fail(res=CustomResponse(code=400, msg='取消收藏失败'))
