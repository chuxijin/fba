from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request

from backend.app.gongkao.schema.content import (
    ContentParam,
    CreateContentParam,
    DeleteContentParam,
    GetContentDetail,
    GetContentListDetail,
    UpdateContentParam,
)
from backend.app.gongkao.service.content_service import content_service
from backend.common.pagination import DependsPagination, PageData
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.common.security.permission import RequestPermission
from backend.common.security.rbac import DependsRBAC
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get('/tags', summary='获取内容标签列表')
async def get_content_tags(
    db: CurrentSession,
    limit: Annotated[int, Query(description='限制数量')] = 50,
) -> ResponseSchemaModel[list[str]]:
    """获取所有已发布内容的标签（去重聚合）"""
    data = await content_service.get_tags(db=db, limit=limit)
    return response_base.success(data=data)


@router.get('/{pk}', summary='获取内容详情')
async def get_content(
    db: CurrentSession, pk: Annotated[int, Path(description='ID')]
) -> ResponseSchemaModel[GetContentDetail]:
    """通过 ID 获取内容详情"""
    data = await content_service.get(db=db, pk=pk)
    return response_base.success(data=data)


@router.get('/slug/{slug}', summary='通过别名获取内容详情')
async def get_content_by_slug(
    db: CurrentSession, slug: Annotated[str, Path(description='别名')]
) -> ResponseSchemaModel[GetContentDetail]:
    """通过别名获取内容详情"""
    data = await content_service.get_by_slug(db=db, slug=slug)
    return response_base.success(data=data)


@router.get(
    '',
    summary='获取内容列表',
    dependencies=[DependsPagination],
)
async def get_content_list(
    db: CurrentSession,
    title: Annotated[str | None, Query(description='标题关键词')] = None,
    category_id: Annotated[int | None, Query(description='分类 ID')] = None,
    tag: Annotated[str | None, Query(description='标签')] = None,
    is_pinned: Annotated[bool | None, Query(description='是否置顶')] = None,
    is_public: Annotated[bool | None, Query(description='是否公开')] = None,
    is_published: Annotated[bool | None, Query(description='是否发布')] = None,
) -> ResponseSchemaModel[PageData[GetContentListDetail]]:
    """获取内容列表（分页）"""
    params = ContentParam(
        title=title,
        category_id=category_id,
        tag=tag,
        is_pinned=is_pinned,
        is_public=is_public,
        is_published=is_published,
    )
    data = await content_service.get_list(db=db, params=params)
    return response_base.success(data=data)


@router.post(
    '',
    summary='创建内容',
    dependencies=[
        Depends(RequestPermission('gongkao:content:create')),
        DependsRBAC,
    ],
)
async def create_content(
    request: Request,
    db: CurrentSessionTransaction,
    obj: CreateContentParam,
) -> ResponseModel:
    """创建内容"""
    await content_service.create(db=db, obj=obj, created_by=request.user.id)
    return response_base.success()


@router.put(
    '/{pk}',
    summary='更新内容',
    dependencies=[
        Depends(RequestPermission('gongkao:content:update')),
        DependsRBAC,
    ],
)
async def update_content(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='ID')],
    obj: UpdateContentParam,
) -> ResponseModel:
    """更新内容"""
    count = await content_service.update(db=db, pk=pk, obj=obj, updated_by=request.user.id)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete(
    '',
    summary='删除内容',
    dependencies=[
        Depends(RequestPermission('gongkao:content:delete')),
        DependsRBAC,
    ],
)
async def delete_content(db: CurrentSessionTransaction, obj: DeleteContentParam) -> ResponseModel:
    """删除内容"""
    count = await content_service.delete(db=db, obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.post('/{pk}/view', summary='增加浏览量')
async def increment_content_view(
    db: CurrentSessionTransaction, pk: Annotated[int, Path(description='ID')]
) -> ResponseModel:
    """增加浏览量"""
    await content_service.increment_view(db=db, pk=pk)
    return response_base.success()
