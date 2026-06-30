from typing import Annotated

from fastapi import APIRouter, Path, Query

from backend.app.halo.schema.halo import HaloCategoryItem, HaloPostDetail, HaloPostItem, HaloTagItem
from backend.app.halo.service.halo_service import halo_service
from backend.common.response.response_schema import ResponseSchemaModel, response_base

router = APIRouter()


@router.get('/posts', summary='文章列表', response_model=ResponseSchemaModel)
async def get_halo_posts(
    page: Annotated[int, Query(description='页码', ge=1)] = 1,
    size: Annotated[int, Query(description='每页数量', ge=1, le=50)] = 10,
    category: Annotated[str | None, Query(description='分类名称（Halo name）')] = None,
    tag: Annotated[str | None, Query(description='标签名称（Halo name）')] = None,
    keyword: Annotated[str | None, Query(description='搜索关键词')] = None,
):
    data = await halo_service.list_posts(page=page, size=size, category=category, tag=tag, keyword=keyword)
    return response_base.success(data=data)


@router.get('/posts/{name}', summary='文章详情', response_model=ResponseSchemaModel[HaloPostDetail])
async def get_halo_post(name: Annotated[str, Path(description='文章名称')]):
    data = await halo_service.get_post(name=name)
    return response_base.success(data=data)


@router.get('/categories', summary='分类列表', response_model=ResponseSchemaModel[list[HaloCategoryItem]])
async def get_halo_categories():
    data = await halo_service.list_categories()
    return response_base.success(data=data)


@router.get('/tags', summary='标签列表', response_model=ResponseSchemaModel[list[HaloTagItem]])
async def get_halo_tags():
    data = await halo_service.list_tags()
    return response_base.success(data=data)
