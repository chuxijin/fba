#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Path, Query

from backend.app.halo.schema.halo import HaloCategoryItem, HaloPostDetail, HaloPostItem, HaloTagItem, DocTreeNode, DocDetail
from backend.app.halo.service.halo_service import halo_service
from backend.common.pagination import PageData
from backend.common.response.response_schema import ResponseSchemaModel, response_base

router = APIRouter()


@router.get('/posts', summary='文章列表', response_model=ResponseSchemaModel[PageData[HaloPostItem]])
async def get_halo_posts(
    page: Annotated[int, Query(description='页码', ge=1)] = 1,
    size: Annotated[int, Query(description='每页数量', ge=1, le=50)] = 10,
    category: Annotated[str | None, Query(description='分类名称（Halo name）')] = None,
    tag: Annotated[str | None, Query(description='标签名称（Halo name）')] = None,
    keyword: Annotated[str | None, Query(description='搜索关键词')] = None,
) -> ResponseSchemaModel[PageData[HaloPostItem]]:
    """
    分页获取文章列表

    :param page: 页码
    :param size: 每页数量
    :param category: 分类名称
    :param tag: 标签名称
    :param keyword: 搜索关键词
    :return:
    """
    data = await halo_service.list_posts(page=page, size=size, category=category, tag=tag, keyword=keyword)
    return response_base.success(data=data)


@router.get('/posts/{name}', summary='文章详情', response_model=ResponseSchemaModel[HaloPostDetail])
async def get_halo_post(name: Annotated[str, Path(description='文章名称')]) -> ResponseSchemaModel[HaloPostDetail]:
    """
    获取文章详情

    :param name: 文章名称
    :return:
    """
    data = await halo_service.get_post(name=name)
    return response_base.success(data=data)


@router.get('/categories', summary='分类列表', response_model=ResponseSchemaModel[list[HaloCategoryItem]])
async def get_halo_categories() -> ResponseSchemaModel[list[HaloCategoryItem]]:
    """
    获取分类列表

    :return:
    """
    data = await halo_service.list_categories()
    return response_base.success(data=data)


@router.get('/tags', summary='标签列表', response_model=ResponseSchemaModel[list[HaloTagItem]])
async def get_halo_tags() -> ResponseSchemaModel[list[HaloTagItem]]:
    """
    获取标签列表

    :return:
    """
    data = await halo_service.list_tags()
    return response_base.success(data=data)


@router.get('/docs/tree', summary='文档目录树', response_model=ResponseSchemaModel[list[DocTreeNode]])
async def get_doc_tree() -> ResponseSchemaModel[list[DocTreeNode]]:
    """
    获取 Docsme 文档目录树

    :return:
    """
    data = await halo_service.list_doc_tree()
    return response_base.success(data=data)


@router.get('/docs/{name}', summary='文档详情', response_model=ResponseSchemaModel[DocDetail])
async def get_doc_detail(name: Annotated[str, Path(description='文档 UUID')]) -> ResponseSchemaModel[DocDetail]:
    """
    获取文档详情（含 HTML 正文）

    :param name: 文档 UUID
    :return:
    """
    data = await halo_service.get_doc(name=name)
    if not data:
        return response_base.fail()
    return response_base.success(data=data)

