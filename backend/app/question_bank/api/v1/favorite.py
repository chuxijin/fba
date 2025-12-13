#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
收藏接口

设计原则：
- 支持收藏夹分组（类似 LeetCode）
- 支持自定义标签
- 支持置顶功能
"""
from typing import Annotated

from fastapi import APIRouter, Body, Path, Query

from backend.app.question_bank.crud.crud_question_favorite import question_favorite_dao
from backend.app.question_bank.schema.favorite import (
    BatchDeleteFavoritesParam,
    ClearFolderParam,
    CreateQuestionFavoriteParam,
    FavoriteStatistics,
    FolderInfo,
    GetQuestionFavoriteDetail,
    GetQuestionFavoriteListItem,
    SetFavoritePinParam,
    UpdateQuestionFavoriteParam,
)
from backend.app.question_bank.security import DependsCustomerAuth
from backend.common.pagination import DependsPagination, PageData, paging_data
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.auth_strategy import AuthUser
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


# ============ 收藏管理接口 ============
# 重要：具体路径的路由必须放在通配路由（/{pk}）之前，否则会被通配路由拦截


@router.post('', summary='收藏题目', name='qbank_favorite_create')
async def create_favorite(
    db: CurrentSessionTransaction,
    obj: CreateQuestionFavoriteParam,
    current_user: AuthUser = DependsCustomerAuth,
) -> ResponseSchemaModel[GetQuestionFavoriteDetail]:
    """
    收藏题目

    可指定收藏夹、标签和备注
    """
    # 检查是否已收藏
    existing = await question_favorite_dao.get_by_user_and_question(
        db=db, user_id=current_user.user_id, question_id=obj.question_id
    )
    if existing:
        return response_base.fail(msg='该题目已收藏')

    favorite_dict = obj.model_dump()
    favorite_dict['user_id'] = current_user.user_id

    new_favorite = await question_favorite_dao.create(
        db=db,
        user_id=current_user.user_id,
        question_id=obj.question_id,
        folder_name=obj.folder_name,
        tags=obj.tags,
        remark=obj.remark,
    )

    return response_base.success(data=GetQuestionFavoriteDetail.model_validate(new_favorite))


@router.get('', summary='获取收藏列表', name='qbank_favorite_get_list', dependencies=[DependsPagination])
async def get_favorites(
    db: CurrentSession,
    current_user: AuthUser = DependsCustomerAuth,
    folder_name: Annotated[str | None, Query(description='收藏夹名称')] = None,
    is_pinned: Annotated[bool | None, Query(description='是否置顶')] = None,
) -> ResponseSchemaModel[PageData[GetQuestionFavoriteListItem]]:
    """
    获取用户的收藏列表（分页）

    支持按收藏夹、置顶状态筛选

    注：只返回收藏基本信息（使用冗余字段），不返回题目详细内容
    题目详细内容在刷题页面通过 question_id 查询
    """
    stmt = await question_favorite_dao.get_select(
        user_id=current_user.user_id, folder_name=folder_name, is_pinned=is_pinned
    )
    page_data = await paging_data(db, stmt, GetQuestionFavoriteListItem)
    return response_base.success(data=page_data)


# ============ 收藏夹管理接口（具体路径，必须在 /{pk} 之前）============


@router.get('/folders', summary='获取收藏夹列表', name='qbank_favorite_get_folders')
async def get_folders(
    db: CurrentSession, current_user: AuthUser = DependsCustomerAuth
) -> ResponseSchemaModel[list[str]]:
    """获取用户的所有收藏夹名称"""
    folders = await question_favorite_dao.get_user_folders(db=db, user_id=current_user.user_id)
    return response_base.success(data=folders)


@router.post('/folders/clear', summary='清空收藏夹', name='qbank_favorite_clear_folder')
async def clear_folder(
    db: CurrentSessionTransaction,
    obj: ClearFolderParam,
    current_user: AuthUser = DependsCustomerAuth,
) -> ResponseModel:
    """
    清空指定收藏夹

    删除该收藏夹下的所有收藏
    """
    count = await question_favorite_dao.clear_folder(db=db, user_id=current_user.user_id, folder_name=obj.folder_name)

    if count > 0:
        return response_base.success(msg=f'成功清空收藏夹，删除 {count} 个收藏')
    return response_base.success(msg='收藏夹为空')


# ============ 工具接口（具体路径，必须在 /{pk} 之前）============


@router.post('/questions/check', summary='检查题目收藏状态', name='qbank_favorite_check')
async def check_favorited(
    db: CurrentSession,
    question_ids: Annotated[list[int], Body(description='题目 ID 列表（可以是单个或多个）')],
    current_user: AuthUser = DependsCustomerAuth,
) -> ResponseSchemaModel[dict[int, bool]]:
    """
    检查题目的收藏状态（统一接口）

    支持单个题目和批量题目查询，传入题目 ID 数组即可
    - 单个查询：传入 [123]
    - 批量查询：传入 [123, 456, 789]

    :param db: 数据库会话
    :param question_ids: 题目 ID 列表
    :param current_user: 当前用户
    :return: 字典 {question_id: is_favorited}
    """
    from sqlalchemy import select

    # 查询用户已收藏的题目
    stmt = select(question_favorite_dao.model.question_id).where(
        question_favorite_dao.model.user_id == current_user.user_id,
        question_favorite_dao.model.question_id.in_(question_ids),
    )
    result = await db.execute(stmt)
    favorited_ids = {row[0] for row in result.fetchall()}

    # 构建返回字典
    status_map = {qid: qid in favorited_ids for qid in question_ids}

    return response_base.success(data=status_map)


@router.get('/statistics', summary='获取收藏统计', name='qbank_favorite_statistics')
async def get_statistics(
    db: CurrentSession, current_user: AuthUser = DependsCustomerAuth
) -> ResponseSchemaModel[FavoriteStatistics]:
    """
    获取用户的收藏统计数据

    包括总数、收藏夹数量、各收藏夹的收藏数量
    """
    all_favorites = await question_favorite_dao.get_by_user(db=db, user_id=current_user.user_id)
    folder_names = await question_favorite_dao.get_user_folders(db=db, user_id=current_user.user_id)

    # 统计各收藏夹的数量
    folder_stats = []
    for folder_name in folder_names:
        folder_favorites = [f for f in all_favorites if f.folder_name == folder_name]
        folder_stats.append(FolderInfo(folder_name=folder_name, count=len(folder_favorites)))

    # 统计未分组的收藏
    no_folder_count = sum(1 for f in all_favorites if not f.folder_name)
    if no_folder_count > 0:
        folder_stats.insert(0, FolderInfo(folder_name='未分组', count=no_folder_count))

    stats = FavoriteStatistics(
        total_count=len(all_favorites), folder_count=len(folder_names), folders=folder_stats
    )

    return response_base.success(data=stats)


@router.post('/batch-delete', summary='批量取消收藏', name='qbank_favorite_batch_delete')
async def batch_delete_favorites(
    db: CurrentSessionTransaction,
    obj: BatchDeleteFavoritesParam,
    current_user: AuthUser = DependsCustomerAuth,
) -> ResponseModel:
    """批量取消收藏题目"""
    # 验证所有收藏是否属于当前用户
    for favorite_id in obj.favorite_ids:
        favorite = await question_favorite_dao.get(db=db, favorite_id=favorite_id)
        if favorite and favorite.user_id != current_user.user_id:
            return response_base.fail(msg=f'无权操作收藏 {favorite_id}')

    # 批量删除
    count = await question_favorite_dao.batch_delete(db=db, favorite_ids=obj.favorite_ids)

    if count > 0:
        return response_base.success(msg=f'成功取消 {count} 个收藏')
    return response_base.fail()


# ============ 通配路径接口（必须放在最后）============


@router.get('/{pk}', summary='获取收藏详情', name='qbank_favorite_get')
async def get_favorite(
    db: CurrentSession,
    pk: Annotated[int, Path(description='收藏 ID')],
    current_user: AuthUser = DependsCustomerAuth,
) -> ResponseSchemaModel[GetQuestionFavoriteDetail]:
    """获取收藏详情"""
    favorite = await question_favorite_dao.get(db=db, favorite_id=pk)
    if not favorite:
        return response_base.fail(msg='收藏不存在')
    if favorite.user_id != current_user.user_id:
        return response_base.fail(msg='无权访问此收藏')

    return response_base.success(data=GetQuestionFavoriteDetail.model_validate(favorite))


@router.put('/{pk}', summary='更新收藏', name='qbank_favorite_update')
async def update_favorite(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='收藏 ID')],
    obj: UpdateQuestionFavoriteParam,
    current_user: AuthUser = DependsCustomerAuth,
) -> ResponseModel:
    """
    更新收藏信息

    可修改收藏夹、标签、备注
    """
    favorite = await question_favorite_dao.get(db=db, favorite_id=pk)
    if not favorite:
        return response_base.fail(msg='收藏不存在')
    if favorite.user_id != current_user.user_id:
        return response_base.fail(msg='无权操作此收藏')

    count = await question_favorite_dao.update(
        db=db, favorite_id=pk, folder_name=obj.folder_name, tags=obj.tags, remark=obj.remark
    )

    if count > 0:
        return response_base.success()
    return response_base.fail(msg='没有需要更新的数据')


@router.put('/{pk}/pin', summary='设置收藏置顶', name='qbank_favorite_set_pin')
async def set_pin(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='收藏 ID')],
    is_pinned: Annotated[bool, Body(embed=True, description='是否置顶')],
    current_user: AuthUser = DependsCustomerAuth,
) -> ResponseModel:
    """设置收藏置顶或取消置顶"""
    favorite = await question_favorite_dao.get(db=db, favorite_id=pk)
    if not favorite:
        return response_base.fail(msg='收藏不存在')
    if favorite.user_id != current_user.user_id:
        return response_base.fail(msg='无权操作此收藏')

    count = await question_favorite_dao.set_pin(db=db, favorite_id=pk, is_pinned=is_pinned)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete('/{pk}', summary='取消收藏', name='qbank_favorite_delete')
async def delete_favorite(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='收藏 ID')],
    current_user: AuthUser = DependsCustomerAuth,
) -> ResponseModel:
    """取消收藏题目"""
    favorite = await question_favorite_dao.get(db=db, favorite_id=pk)
    if not favorite:
        return response_base.fail(msg='收藏不存在')
    if favorite.user_id != current_user.user_id:
        return response_base.fail(msg='无权操作此收藏')

    count = await question_favorite_dao.delete(db=db, favorite_id=pk)
    if count > 0:
        return response_base.success()
    return response_base.fail()
