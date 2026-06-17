#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import re

from typing import Annotated
from urllib.parse import urljoin, urlparse

import requests

from fastapi import APIRouter, Query
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from backend.app.content.schema.content import (
    CreateContentParam,
    GetContentDetail,
    GetContentListDetails,
    UpdateContentParam,
)
from backend.app.content.service.content_service import content_service
from backend.common.pagination import DependsPagination, PageData
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.common.security.rbac import DependsRBAC
from backend.database.db import CurrentSession

router = APIRouter()


@router.get(
    '/list',
    summary='获取内容列表(分页)',
    response_model=ResponseSchemaModel[PageData[GetContentListDetails]],
    dependencies=[DependsPagination],
)
async def get_sys_content_list(
    db: CurrentSession,
    app_code: Annotated[str | None, Query(description='应用标识')] = None,
    category_id: Annotated[int | None, Query(description='分类 ID')] = None,
    is_published: Annotated[bool | None, Query(description='是否发布')] = None,
    keyword: Annotated[str | None, Query(description='标题关键词模糊搜索')] = None,
):
    page_data = await content_service.get_list_paged(
        db=db,
        app_code=app_code,
        category_id=category_id,
        is_published=is_published,
        keyword=keyword,
    )
    return response_base.success(data=page_data)


@router.get('/link-detail', summary='获取链接详情')
async def get_link_detail(url: Annotated[str, Query(description='解析URL')]):
    def fetch_tdk(target_url: str):
        try:
            parsed_url = urlparse(target_url)
            if parsed_url.scheme not in {'http', 'https'}:
                raise ValueError('Unsupported URL scheme')

            response = requests.get(
                target_url,
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'},
                timeout=5,
            )
            response.raise_for_status()
            html = response.content.decode('utf-8', errors='ignore')

            title_match = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
            title = title_match.group(1).strip() if title_match else ''

            desc_match = re.search(
                r'<meta\s+name=[\"\']description[\"\']\s+content=[\"\']([^\"\']+)[\"\']', html, re.IGNORECASE
            )
            if not desc_match:
                desc_match = re.search(
                    r'<meta\s+content=[\"\']([^\"\']+)[\"\']\s+name=[\"\']description[\"\']', html, re.IGNORECASE
                )

            desc = ''
            if desc_match:
                desc = desc_match.group(1).strip()

            icon_match = re.search(
                r'<link\s+rel=[\"\'].*?icon.*?[\"\']\s+href=[\"\']([^\"\']+)[\"\']', html, re.IGNORECASE
            )
            icon = icon_match.group(1).strip() if icon_match else ''
            if icon and not icon.startswith('http'):
                icon = urljoin(target_url, icon)

            img_match = re.search(
                r'<meta\s+property=[\"\']og:image[\"\']\s+content=[\"\']([^\"\']+)[\"\']', html, re.IGNORECASE
            )
            image = img_match.group(1).strip() if img_match else icon

            return {'title': title or target_url, 'description': desc, 'image': image, 'icon': icon, 'url': target_url}
        except Exception:
            return {'title': target_url, 'description': '', 'image': '', 'icon': '', 'url': target_url}

    res = await run_in_threadpool(fetch_tdk, url)
    return JSONResponse(content=res)


@router.get('/tags', summary='获取内容标签', response_model=ResponseSchemaModel[list[str]])
async def get_sys_content_tags(
    db: CurrentSession,
    limit: Annotated[int, Query(description='返回数量限制')] = 50,
):
    # 这里是一个简单的标签提取逻辑，实际可能需要更复杂的聚合查询
    from sqlalchemy import select

    from backend.app.content.model.content import Content

    stmt = select(Content.tags).where(Content.tags.isnot(None))
    result = await db.execute(stmt)
    all_tags = set()
    for row in result.scalars():
        if row:
            all_tags.update(row)
    return response_base.success(data=list(all_tags)[:limit])


@router.get('/slug/{slug}', summary='根据别名获取内容详情', response_model=ResponseSchemaModel[GetContentDetail])
async def get_sys_content_by_slug(db: CurrentSession, slug: str):
    content = await content_service.get_by_slug(db=db, slug=slug)
    return response_base.success(data=content)


@router.get(
    '/{pk}/related', summary='获取相关内容列表', response_model=ResponseSchemaModel[list[GetContentListDetails]]
)
async def get_related_content_list(
    db: CurrentSession,
    pk: int,
    limit: Annotated[int, Query(description='限制条数')] = 5,
):
    items = await content_service.get_related_list(db=db, pk=pk, limit=limit)
    return response_base.success(data=items)


@router.get('/{pk}', summary='获取内容详情', response_model=ResponseSchemaModel[GetContentDetail])
async def get_sys_content(db: CurrentSession, pk: int):
    content = await content_service.get_with_incr_view(db=db, pk=pk)
    return response_base.success(data=content)


@router.post('/{pk}/view', summary='增加浏览量')
async def increment_sys_content_view(db: CurrentSession, pk: int):
    await content_service.get_with_incr_view(db=db, pk=pk)
    return response_base.success()


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
