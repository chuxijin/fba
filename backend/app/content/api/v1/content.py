from typing import Annotated

from fastapi import APIRouter, Query

from backend.app.content.schema.content import CreateContentParam, UpdateContentParam, GetContentDetail, GetContentListDetails
from backend.app.content.service.content_service import content_service
from backend.common.pagination import DependsPagination, PageData
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.common.security.rbac import DependsRBAC
from backend.database.db import CurrentSession

router = APIRouter()


@router.get('/list', summary='获取内容列表(分页)', response_model=ResponseSchemaModel[PageData[GetContentListDetails]], dependencies=[DependsPagination])
async def get_sys_content_list(
    db: CurrentSession,
    app_code: str = Query(None, description='应用标识'),
    category_id: int = Query(None, description='分类 ID'),
    is_published: bool = Query(None, description='是否发布'),
):
    page_data = await content_service.get_list_paged(db=db, app_code=app_code, category_id=category_id, is_published=is_published)
    return response_base.success(data=page_data)


@router.get('/{pk}', summary='获取内容详情', response_model=ResponseSchemaModel[GetContentDetail])
async def get_sys_content(db: CurrentSession, pk: int):
    content = await content_service.get_with_incr_view(db=db, pk=pk)
    return response_base.success(data=content)


@router.post('', summary='创建内容', dependencies=[DependsJwtAuth, DependsRBAC])
async def create_sys_content(db: CurrentSession, obj: CreateContentParam):
    await content_service.create(db=db, obj=obj)
    return response_base.success()


@router.put('/{pk}', summary='更新内容', dependencies=[DependsJwtAuth, DependsRBAC])
async def update_sys_content(db: CurrentSession, pk: int, obj: UpdateContentParam):
    count = await content_service.update(db=db, pk=pk, obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete('', summary='删除内容', dependencies=[DependsJwtAuth, DependsRBAC])
async def delete_sys_content(db: CurrentSession, pk: Annotated[list[int], Query(...)]):
    count = await content_service.delete(db=db, pk=pk)
    if count > 0:
        return response_base.success()
    return response_base.fail()
