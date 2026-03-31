#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Path, Request, UploadFile, File
from starlette.concurrency import run_in_threadpool

from backend.app.coulddrive.schema.resource import (
    CreateResourceParam,
    UpdateResourceParam,
    GetResourceListParam,
    ResourceStatistics,
    CreateResourceViewHistoryParam,
    GetResourceViewHistoryDetail,
    GetResourceViewHistoryListParam,
    ResourceViewTrendResponse,
    GetResourceViewTrendParam,
    UpdateResourceViewCountParam,
    GetResourceDetail,
    ResourceListItem,
    UpdateResourceUserParam,
    OverallStatisticsTrendResponse,
    GetOverallStatisticsTrendParam,
    VectorSearchResultItem,
    VectorSearchKnowledgeResultItem,
    BatchDeleteResourceParam
)
from backend.app.coulddrive.schema.enum import (
    DriveType
)
from backend.app.coulddrive.service.resource_service import resource_service, resource_view_history_service
from backend.common.pagination import DependsPagination
from backend.common.response.response_code import CustomResponse
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession

router = APIRouter()




@router.get(
    '',
    summary='获取资源列表',
    dependencies=[DependsPagination]
)
async def get_resource_list(
    request: Request,
    db: CurrentSession,
    params: Annotated[GetResourceListParam, Depends()]
) -> ResponseModel:
    """
    获取资源列表

    :param request: 请求对象
    :param db: 数据库会话
    :param params: 查询参数
    :return: 资源列表
    """
    page_data = await resource_service.get_list(db=db, params=params)
    return response_base.success(data=page_data)


@router.get(
    '/hot',
    summary='获取热门资源列表',
    response_model=ResponseSchemaModel[list[ResourceListItem]],
    dependencies=[DependsPagination]
)
async def get_hot_resource_list(
    request: Request,
    db: CurrentSession,
    category_id: Annotated[int | None, Query(description='分类ID')] = None,
    resource_type: Annotated[str | None, Query(description='资源类型')] = None,
    resource_types: Annotated[list[str] | None, Query(description='资源类型列表，可重复传参或逗号分隔')] = None,
    limit: Annotated[int, Query(description='数量限制', ge=1, le=50)] = 20
) -> ResponseSchemaModel[list[ResourceListItem]]:
    """
    获取热门资源列表（按热度排序）

    :param request: 请求对象
    :param db: 数据库会话
    :param category_id: 分类ID
    :param resource_type: 资源类型
    :param resource_types: 资源类型列表
    :param limit: 数量限制
    :return: 热门资源列表
    """
    hot_list = await resource_service.get_hot_list(
        db=db,
        category_id=category_id,
        resource_type=resource_type,
        resource_types=resource_types,
        limit=limit,
    )
    return response_base.success(data=hot_list)


@router.post(
    '/{resource_id}/click',
    summary='记录资源点击',
    response_model=ResponseModel,
)
async def record_resource_click(
    resource_id: Annotated[int, Path(description='资源ID')],
) -> ResponseModel:
    """
    记录前端资源点击事件（用于热度计算）

    :param resource_id: 资源ID
    :return:
    """
    from backend.app.coulddrive.service.hot_score_service import hot_score_service

    count = await hot_score_service.record_click(resource_id)
    return response_base.success(data={'click_count': count})


@router.get(
    '/statistics',
    summary='获取资源统计信息',
    response_model=ResponseSchemaModel[ResourceStatistics],
    dependencies=[DependsJwtAuth]
)
async def get_resource_statistics(
    request: Request,
    db: CurrentSession,
    user_id: Annotated[int | None, Query(description='用户ID')] = None
) -> ResponseSchemaModel[ResourceStatistics]:
    """
    获取资源统计信息

    :param request: 请求对象
    :param db: 数据库会话
    :param user_id: 用户ID
    :return: 资源统计信息
    """
    stats = await resource_service.get_statistics(db=db, user_id=user_id)
    return response_base.success(data=stats)


@router.get(
    '/statistics/trend',
    summary='获取整体资源统计趋势',
    response_model=ResponseSchemaModel[OverallStatisticsTrendResponse],
    dependencies=[DependsJwtAuth]
)
async def get_overall_statistics_trend(
    request: Request,
    db: CurrentSession,
    params: Annotated[GetOverallStatisticsTrendParam, Depends()]
) -> ResponseSchemaModel[OverallStatisticsTrendResponse]:
    """
    获取整体资源统计趋势

    :param request: 请求对象
    :param db: 数据库会话
    :param params: 查询参数
    :return: 整体统计趋势数据
    """
    trend_data = await resource_service.get_overall_statistics_trend(db=db, params=params)
    return response_base.success(data=trend_data)


@router.get(
    '/view-trend',
    summary='获取资源浏览量趋势',
    response_model=ResponseSchemaModel[ResourceViewTrendResponse],
    dependencies=[DependsJwtAuth]
)
async def get_resource_view_trend(
    request: Request,
    db: CurrentSession,
    params: Annotated[GetResourceViewTrendParam, Depends()]
) -> ResponseSchemaModel[ResourceViewTrendResponse]:
    """
    获取资源浏览量趋势

    :param request: 请求对象
    :param db: 数据库会话
    :param params: 查询参数
    :return: 浏览量趋势数据
    """
    trend_data = await resource_view_history_service.get_view_trend(db=db, params=params)
    return response_base.success(data=trend_data)


@router.post('', summary='创建资源', dependencies=[DependsJwtAuth])
async def create_resource(
    request: Request,
    db: CurrentSession,
    params: CreateResourceParam,
    auto_vectorize: Annotated[bool, Query(description='是否自动向量化资源')] = False
) -> ResponseSchemaModel[GetResourceDetail]:
    """
    创建资源

    :param request: 请求对象
    :param db: 数据库会话
    :param params: 创建参数
    :param auto_vectorize: 是否自动向量化资源
    :return: 资源详情
    """
    resource = await resource_service.create(db=db, obj=params, created_by=request.user.id, auto_vectorize=auto_vectorize)
    return response_base.success(data=resource)


@router.get(
    '/vector-search',
    summary='向量搜索资源',
    response_model=ResponseSchemaModel[list],
    dependencies=[DependsJwtAuth]
)
async def vector_search_resources(
    request: Request,
    db: CurrentSession,
    query: Annotated[str, Query(description='搜索查询文本', min_length=1)],
    category_id: Annotated[int | None, Query(description='分类过滤')] = None,
    limit: Annotated[int, Query(description='返回结果数量', ge=1, le=100)] = 20,
    similarity_threshold: Annotated[float, Query(description='相似度阈值 (0-1)', ge=0, le=1)] = 0.7,
    include_content: Annotated[bool, Query(description='是否包含完整内容（供AI知识库调用时设为true）')] = False,
) -> ResponseSchemaModel[list]:
    """
    向量搜索资源

    支持两种模式：
    1. 搜索框模式（include_content=false）：返回资源基础信息，适合前端展示
    2. AI知识库模式（include_content=true）：返回完整内容，供AI理解和生成答案

    支持按科目过滤搜索结果，query 会在资源介绍和描述中进行语义搜索

    :param request: 请求对象
    :param db: 数据库会话
    :param query: 搜索查询文本（在资源介绍和描述中搜索）
    :param category_id: 分类过滤
    :param limit: 返回结果数量限制
    :param similarity_threshold: 相似度阈值
    :param include_content: 是否包含完整内容（AI知识库模式）
    :return: 搜索结果列表
    """
    results = await resource_service.vector_search(
        db=db,
        query_text=query,
        limit=limit,
        similarity_threshold=similarity_threshold,
        include_content=include_content,
        category_id=category_id,
    )

    # 记录搜索曝光（异步，不阻塞响应）
    if results:
        from backend.app.coulddrive.service.hot_score_service import hot_score_service

        resource_ids: list[int] = []
        for item in results:
            resource = None
            if isinstance(item, dict):
                resource = item.get('resource')
            elif hasattr(item, 'resource'):
                resource = item.resource

            resource_id = getattr(resource, 'id', None)
            if isinstance(resource_id, int):
                resource_ids.append(resource_id)

        if resource_ids:
            asyncio.create_task(hot_score_service.record_search_impressions(resource_ids))

    return response_base.success(data=results)


@router.post(
    '/vectorize',
    summary='向量化资源（支持单个或批量）',
    response_model=ResponseModel,
    dependencies=[DependsJwtAuth]
)
async def vectorize_resources(
    request: Request,
    db: CurrentSession,
    resource_id: Annotated[int | None, Query(description='单个资源ID')] = None,
    batch_size: Annotated[int, Query(description='批量处理时的每批次数量', ge=1, le=200)] = 50
) -> ResponseModel:
    """
    向量化资源

    两种模式：
    1. 单个向量化：传入 resource_id 参数
    2. 批量向量化：不传 resource_id，自动处理所有未向量化的资源

    :param request: 请求对象
    :param db: 数据库会话
    :param resource_id: 单个资源ID（可选）
    :param batch_size: 批量处理时的每批次数量
    :return: 向量化结果
    """
    if resource_id:
        # 单个向量化
        success = await resource_service.update_vector(db=db, pk=resource_id)
        if success:
            return response_base.success(res=CustomResponse(code=200, msg='资源向量化成功'))
        return response_base.fail(res=CustomResponse(code=400, msg='资源向量化失败'))
    else:
        # 批量向量化
        count = await resource_service.batch_update_vectors(db=db, batch_size=batch_size)
        return response_base.success(
            res=CustomResponse(code=200, msg=f'成功向量化 {count} 个资源'),
            data={'count': count}
        )


@router.get(
    '/{resource_id}',
    summary='获取资源详情',
    response_model=ResponseSchemaModel[GetResourceDetail],
)
async def get_resource_detail(
    request: Request,
    db: CurrentSession,
    resource_id: Annotated[int, Path(description='资源ID')]
) -> ResponseSchemaModel[GetResourceDetail]:
    """
    获取资源详情

    :param request: 请求对象
    :param db: 数据库会话
    :param resource_id: 资源ID
    :return: 资源详情
    """
    resource = await resource_service.get(db=db, pk=resource_id)
    return response_base.success(data=resource)


@router.put(
    '/{resource_id}',
    summary='更新资源',
    response_model=ResponseSchemaModel[GetResourceDetail],
    dependencies=[DependsJwtAuth]
)
async def update_resource(
    request: Request,
    db: CurrentSession,
    resource_id: Annotated[int, Path(description='资源ID')],
    obj: UpdateResourceUserParam,
    auto_refresh: Annotated[bool, Query(description='是否自动刷新分享信息')] = False
) -> ResponseSchemaModel[GetResourceDetail]:
    """
    更新资源

    :param request: 请求对象
    :param db: 数据库会话
    :param resource_id: 资源ID
    :param obj: 更新参数
    :param auto_refresh: 是否自动刷新分享信息
    :return: 更新后的资源详情
    """
    # 将用户输入参数转换为完整的更新参数
    update_param = UpdateResourceParam(**obj.model_dump(exclude_unset=True))
    resource = await resource_service.update(db=db, pk=resource_id, obj=update_param, updated_by=request.user.id, auto_refresh=auto_refresh)
    return response_base.success(data=resource)


@router.put(
    '/{resource_id}/refresh-share-info',
    summary='刷新资源分享信息',
    response_model=ResponseSchemaModel[GetResourceDetail],
    dependencies=[DependsJwtAuth]
)
async def refresh_resource_share_info(
    request: Request,
    db: CurrentSession,
    resource_id: Annotated[int, Path(description='资源ID')]
) -> ResponseSchemaModel[GetResourceDetail]:
    """
    刷新资源分享信息

    :param request: 请求对象
    :param db: 数据库会话
    :param resource_id: 资源ID
    :return: 更新后的资源详情
    """
    resource = await resource_service.refresh_share_info(db=db, resource_id=resource_id, updated_by=request.user.id)
    return response_base.success(data=resource)


@router.delete(
    '',
    summary='删除资源（支持批量）',
    response_model=ResponseModel,
    dependencies=[DependsJwtAuth]
)
async def delete_resources(
    request: Request,
    db: CurrentSession,
    params: BatchDeleteResourceParam
) -> ResponseModel:
    """
    删除资源（支持单个或批量）

    :param request: 请求对象
    :param db: 数据库会话
    :param params: 删除参数（包含资源ID列表）
    :return: 删除结果
    """
    count = await resource_service.delete(db=db, ids=params.ids, deleted_by=request.user.id)
    return response_base.success(data={'count': count}, msg=f'成功删除 {count} 个资源')


# 浏览量历史记录相关接口
@router.post(
    '/{resource_id}/view-history',
    summary='记录资源浏览量',
    response_model=ResponseSchemaModel[GetResourceViewHistoryDetail],
    dependencies=[DependsJwtAuth]
)
async def create_resource_view_history(
    request: Request,
    db: CurrentSession,
    resource_id: Annotated[int, Path(description='资源ID')],
    params: CreateResourceViewHistoryParam
) -> ResponseSchemaModel[GetResourceViewHistoryDetail]:
    """
    记录资源浏览量
    
    :param request: 请求对象
    :param db: 数据库会话
    :param resource_id: 资源ID
    :param params: 创建参数
    :return: 浏览量历史记录详情
    """
    history = await resource_view_history_service.create_view_history(db, params)
    return response_base.success(data=history)


@router.get(
    '/{resource_id}/view-history',
    summary='获取资源浏览量历史',
    dependencies=[DependsJwtAuth, DependsPagination]
)
async def get_resource_view_history(
    request: Request,
    db: CurrentSession,
    resource_id: Annotated[int, Path(description='资源ID')],
    params: Annotated[GetResourceViewHistoryListParam, Depends()]
) -> ResponseModel:
    """
    获取资源浏览量历史
    
    :param request: 请求对象
    :param db: 数据库会话
    :param resource_id: 资源ID
    :param params: 查询参数
    :return: 浏览量历史记录列表
    """
    page_data = await resource_view_history_service.get_view_history_list(db, params)
    return response_base.success(data=page_data)


@router.put(
    '/{resource_id}/view-count',
    summary='更新资源浏览量',
    response_model=ResponseModel,
    dependencies=[DependsJwtAuth]
)
async def update_resource_view_count(
    request: Request,
    db: CurrentSession,
    resource_id: Annotated[int, Path(description='资源ID')],
    params: UpdateResourceViewCountParam
) -> ResponseModel:
    """
    更新资源浏览量
    
    :param request: 请求对象
    :param db: 数据库会话
    :param resource_id: 资源ID
    :param params: 更新参数
    :return: 更新结果
    """
    await resource_view_history_service.update_view_count(db, params)
    return response_base.success()


@router.delete('/view-histories', summary='清理旧的浏览量历史记录', dependencies=[DependsJwtAuth])
async def clean_old_view_history(
    db: CurrentSession,
    days: Annotated[int, Query(description='保留天数')] = 30
) -> ResponseModel:
    """清理旧的浏览量历史记录"""
    count = await run_in_threadpool(resource_view_history_service.clean_old_view_history, db, days)
    return response_base.success(data={'count': count})


@router.post(
    '/upload',
    summary='上传资源文件',
    description='上传资源文件到服务器',
    dependencies=[DependsJwtAuth]
)
async def upload_resource_file(
    file: Annotated[UploadFile, File(description="文件")]
) -> ResponseModel:
    """
    上传资源文件
    
    :param file: 文件对象
    :return: 文件路径和类型
    """
    try:
        from backend.core.path_conf import UPLOAD_DIR
        import shutil
        import os
        from datetime import datetime
        import uuid
        
        # 允许的文件类型
        ALLOWED_EXTENSIONS = {
            'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 
            'txt', 'md', 'jpg', 'jpeg', 'png', 'gif', 
            'mp4', 'mp3', 'zip', 'rar', '7z'
        }
        
        filename = file.filename
        ext = filename.split('.')[-1].lower() if '.' in filename else ''
        
        # 简单检查文件类型（可选）
        # if ext not in ALLOWED_EXTENSIONS:
        #     return response_base.fail(res=CustomResponse(code=400, msg='不支持的文件类型'))
            
        # 生成保存路径: uploads/resources/YYYYMMDD/uuid.ext
        today = datetime.now().strftime('%Y%m%d')
        save_dir = UPLOAD_DIR / 'resources' / today
        
        if not save_dir.exists():
            save_dir.mkdir(parents=True, exist_ok=True)
            
        base_name = filename.rsplit('.', 1)[0]
        new_filename = f"{base_name}_{uuid.uuid4().hex[:8]}.{ext}"
        save_path = save_dir / new_filename
        
        # 保存文件
        with open(save_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # 生成相对路径（用于前端访问）
        # 假设静态文件挂载在 /static/upload
        relative_path = f"/static/upload/resources/{today}/{new_filename}"
        
        return response_base.success(data={
            'url': relative_path,
            'local_path': str(save_path),
            'filename': filename,
            'file_type': ext
        })
        
    except Exception as e:
        return response_base.fail(res=CustomResponse(code=500, msg=f'文件上传失败: {str(e)}'))
