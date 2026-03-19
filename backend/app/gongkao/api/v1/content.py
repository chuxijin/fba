from datetime import date as date_type
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
from backend.common.security.permission import RequestPermission
from backend.common.security.rbac import DependsRBAC
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get('/tags', summary='Get content tags')
async def get_content_tags(
    db: CurrentSession,
    limit: Annotated[int, Query(description='limit')] = 50,
) -> ResponseSchemaModel[list[str]]:
    """Get all published content tags."""
    data = await content_service.get_tags(db=db, limit=limit)
    return response_base.success(data=data)


@router.get('/{pk}', summary='Get content detail')
async def get_content(
    db: CurrentSession,
    pk: Annotated[int, Path(description='id')],
) -> ResponseSchemaModel[GetContentDetail]:
    """Get content detail by id."""
    data = await content_service.get(db=db, pk=pk)
    return response_base.success(data=data)


@router.get('/slug/{slug}', summary='Get content detail by slug')
async def get_content_by_slug(
    db: CurrentSession,
    slug: Annotated[str, Path(description='slug')],
) -> ResponseSchemaModel[GetContentDetail]:
    """Get content detail by slug."""
    data = await content_service.get_by_slug(db=db, slug=slug)
    return response_base.success(data=data)


@router.get('', summary='Get content list', dependencies=[DependsPagination])
async def get_content_list(
    db: CurrentSession,
    title: Annotated[str | None, Query(description='title keyword')] = None,
    category_id: Annotated[int | None, Query(description='category id')] = None,
    tag: Annotated[str | None, Query(description='tag')] = None,
    is_pinned: Annotated[bool | None, Query(description='is pinned')] = None,
    is_public: Annotated[bool | None, Query(description='is public')] = None,
    is_published: Annotated[bool | None, Query(description='is published')] = None,
    content_type: Annotated[str | None, Query(description='content type in extra')] = None,
    daily_date: Annotated[str | None, Query(description='daily date in extra')] = None,
) -> ResponseSchemaModel[PageData[GetContentListDetail]]:
    """Get content list with filters."""
    params = ContentParam(
        title=title,
        category_id=category_id,
        tag=tag,
        is_pinned=is_pinned,
        is_public=is_public,
        is_published=is_published,
        content_type=content_type,
        daily_date=date_type.fromisoformat(daily_date) if daily_date else None,
    )
    data = await content_service.get_list(db=db, params=params)
    return response_base.success(data=data)


@router.post(
    '',
    summary='Create content',
    dependencies=[Depends(RequestPermission('gongkao:content:create')), DependsRBAC],
)
async def create_content(
    request: Request,
    db: CurrentSessionTransaction,
    obj: CreateContentParam,
) -> ResponseModel:
    """Create content."""
    await content_service.create(db=db, obj=obj, created_by=request.user.id)
    return response_base.success()


@router.put(
    '/{pk}',
    summary='Update content',
    dependencies=[Depends(RequestPermission('gongkao:content:update')), DependsRBAC],
)
async def update_content(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='id')],
    obj: UpdateContentParam,
) -> ResponseModel:
    """Update content."""
    count = await content_service.update(db=db, pk=pk, obj=obj, updated_by=request.user.id)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete(
    '',
    summary='Delete content',
    dependencies=[Depends(RequestPermission('gongkao:content:delete')), DependsRBAC],
)
async def delete_content(db: CurrentSessionTransaction, obj: DeleteContentParam) -> ResponseModel:
    """Delete content."""
    count = await content_service.delete(db=db, obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.post('/{pk}/view', summary='Increment content view count')
async def increment_content_view(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='id')],
) -> ResponseModel:
    """Increment content view count."""
    await content_service.increment_view(db=db, pk=pk)
    return response_base.success()
