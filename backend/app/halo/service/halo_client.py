#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio
from typing import Any

import httpx

from backend.core.conf import settings

HALO_PUBLIC_API = '/apis/api.content.halo.run/v1alpha1'
HALO_EXTENSION_API = '/apis/content.halo.run/v1alpha1'
HALO_DOCS_API = '/apis/api.uc.doc.halo.run/v1alpha1'
HALO_TIMEOUT = 30
HALO_CONNECT_TIMEOUT = 10
HALO_RETRY_COUNT = 2


class HaloClient:
    """Halo 2.x API 客户端"""

    def __init__(self) -> None:
        self._base_url = settings.HALO_BASE_URL.rstrip('/')
        self._pat = settings.HALO_PAT
        self._basic_username = settings.HALO_BASIC_USERNAME
        self._basic_password = settings.HALO_BASIC_PASSWORD

    def _auth_headers(self) -> dict[str, str]:
        """
        构建 PAT 认证请求头

        :return:
        """
        return {'Authorization': f'Bearer {self._pat}'}

    def _basic_auth(self) -> httpx.BasicAuth | None:
        """构建 Basic Auth 认证对象"""
        if not self._basic_username or not self._basic_password:
            return None
        return httpx.BasicAuth(self._basic_username, self._basic_password)

    async def _get(self, path: str, *, auth: bool = False, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """
        发送 GET 请求

        :param path: API 路径
        :param auth: 是否需要 PAT 认证
        :param params: 查询参数
        :return:
        """
        headers = self._auth_headers() if auth else {}
        async with httpx.AsyncClient(timeout=HALO_TIMEOUT) as client:
            response = await client.get(f'{self._base_url}{path}', headers=headers, params=params)
            response.raise_for_status()
            return response.json()

    async def _get_docsme(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        """
        发送 Docsme GET 请求

        :param path: Docsme API 路径
        :param params: 查询参数
        :return:
        """
        timeout = httpx.Timeout(HALO_TIMEOUT, connect=HALO_CONNECT_TIMEOUT)
        last_error: httpx.TimeoutException | None = None
        for attempt in range(HALO_RETRY_COUNT):
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.get(
                        f'{self._base_url}{HALO_DOCS_API}{path}',
                        auth=self._basic_auth(),
                        headers={'Accept': 'application/json'},
                        params=params,
                    )
                    response.raise_for_status()
                    return response.json()
            except httpx.TimeoutException as exc:
                last_error = exc
                if attempt + 1 < HALO_RETRY_COUNT:
                    await asyncio.sleep(0.2)

        if last_error is not None:
            raise last_error
        raise RuntimeError('Docsme 请求失败')

    async def get_public_html(self, url: str) -> str:
        """
        获取 Halo Docsme 发布页面 HTML

        :param url: 发布页面地址
        :return:
        """
        timeout = httpx.Timeout(HALO_TIMEOUT, connect=HALO_CONNECT_TIMEOUT)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url, headers={'Accept': 'text/html'})
            response.raise_for_status()
            return response.text

    async def _post(self, path: str, *, json_data: dict[str, Any]) -> dict[str, Any]:
        """
        发送 POST 请求（需要 PAT 认证）

        :param path: API 路径
        :param json_data: 请求体
        :return:
        """
        async with httpx.AsyncClient(timeout=HALO_TIMEOUT) as client:
            response = await client.post(
                f'{self._base_url}{path}',
                headers={**self._auth_headers(), 'Content-Type': 'application/json'},
                json=json_data,
            )
            response.raise_for_status()
            return response.json()

    async def _put(self, path: str, *, json_data: dict[str, Any]) -> dict[str, Any]:
        """
        发送 PUT 请求（需要 PAT 认证）

        :param path: API 路径
        :param json_data: 请求体
        :return:
        """
        async with httpx.AsyncClient(timeout=HALO_TIMEOUT) as client:
            response = await client.put(
                f'{self._base_url}{path}',
                headers={**self._auth_headers(), 'Content-Type': 'application/json'},
                json=json_data,
            )
            response.raise_for_status()
            return response.json()

    async def _delete(self, path: str, *, auth: bool = True) -> dict[str, Any]:
        """
        发送 DELETE 请求（默认需要 PAT 认证）

        :param path: API 路径
        :param auth: 是否需要 PAT 认证
        :return:
        """
        headers = self._auth_headers() if auth else {}
        async with httpx.AsyncClient(timeout=HALO_TIMEOUT) as client:
            response = await client.delete(f'{self._base_url}{path}', headers=headers)
            if response.status_code == 204:
                return {}
            response.raise_for_status()
            try:
                return response.json()
            except Exception:
                return {}

    async def list_posts(
        self,
        *,
        page: int = 1,
        size: int = 10,
        category: str | None = None,
        tag: str | None = None,
    ) -> dict[str, Any]:
        """
        获取已发布文章列表（Public API）

        :param page: 页码
        :param size: 每页数量
        :param category: 分类名称（Halo metadata.name）
        :param tag: 标签名称（Halo metadata.name）
        :return:
        """
        params: dict[str, Any] = {'page': page, 'size': size}
        if category:
            path = f'{HALO_PUBLIC_API}/categories/{category}/posts'
        elif tag:
            path = f'{HALO_PUBLIC_API}/tags/{tag}/posts'
        else:
            path = f'{HALO_PUBLIC_API}/posts'
        return await self._get(path, params=params)

    async def search_posts(self, keyword: str, limit: int = 10) -> dict[str, Any]:
        """
        通过关键词公开检索文章（Public API）

        :param keyword: 检索关键词
        :param limit: 限定数量
        :return:
        """
        json_data = {'keyword': keyword, 'limit': limit}
        async with httpx.AsyncClient(timeout=HALO_TIMEOUT) as client:
            response = await client.post(
                f'{self._base_url}/apis/api.halo.run/v1alpha1/indices/-/search',
                json=json_data,
            )
            response.raise_for_status()
            return response.json()

    async def get_post(self, name: str) -> dict[str, Any]:
        """
        获取文章详情（Public API）

        :param name: 文章的 metadata.name
        :return:
        """
        return await self._get(f'{HALO_PUBLIC_API}/posts/{name}')

    async def list_categories(self) -> list[dict[str, Any]]:
        """
        获取所有分类（Public API）

        :return:
        """
        data = await self._get(f'{HALO_PUBLIC_API}/categories', params={'page': 1, 'size': 100})
        return data.get('items', [])

    async def list_tags(self) -> list[dict[str, Any]]:
        """
        获取所有标签（Public API）

        :return:
        """
        data = await self._get(f'{HALO_PUBLIC_API}/tags', params={'page': 1, 'size': 100})
        return data.get('items', [])

    async def create_post(self, post_data: dict[str, Any]) -> dict[str, Any]:
        """
        创建文章（Extension API）

        :param post_data: Halo Post 对象
        :return:
        """
        return await self._post(f'{HALO_EXTENSION_API}/posts', json_data=post_data)

    async def update_post(self, name: str, post_data: dict[str, Any]) -> dict[str, Any]:
        """
        更新文章（Extension API）

        :param name: 文章的 metadata.name
        :param post_data: Halo Post 对象
        :return:
        """
        return await self._put(f'{HALO_EXTENSION_API}/posts/{name}', json_data=post_data)

    async def create_snapshot(self, snapshot_data: dict[str, Any]) -> dict[str, Any]:
        """
        创建内容快照（Extension API）

        :param snapshot_data: Halo Snapshot 对象
        :return:
        """
        return await self._post('/apis/content.halo.run/v1alpha1/snapshots', json_data=snapshot_data)

    async def get_post_extension(self, name: str) -> dict[str, Any]:
        """
        获取文章CRD实体（Extension API）

        :param name: 文章的 metadata.name
        :return:
        """
        return await self._get(f'{HALO_EXTENSION_API}/posts/{name}', auth=True)

    async def update_post_content(self, name: str, content_data: dict[str, Any]) -> dict[str, Any]:
        """
        更新文章正文内容（Extension Console API）

        :param name: 文章的 metadata.name
        :param content_data: 包含 content, raw, rawType 的正文数据
        :return:
        """
        return await self._put(f'/apis/api.console.halo.run/v1alpha1/posts/{name}/content', json_data=content_data)

    async def publish_post(self, name: str, head_snapshot: str | None = None) -> dict[str, Any]:
        """
        发布文章（Extension Console API）

        :param name: 文章的 metadata.name
        :param head_snapshot: 发布的快照资源名称
        :return:
        """
        path = f'/apis/api.console.halo.run/v1alpha1/posts/{name}/publish'
        if head_snapshot:
            path = f'{path}?headSnapshot={head_snapshot}'
        return await self._put(path, json_data={})

    async def unpublish_post(self, name: str) -> dict[str, Any]:
        """
        取消发布文章（Extension Console API）

        :param name: 文章的 metadata.name
        :return:
        """
        return await self._put(f'/apis/api.console.halo.run/v1alpha1/posts/{name}/unpublish', json_data={})

    async def delete_post_extension(self, name: str) -> dict[str, Any]:
        """
        物理删除文章资源实体（Extension API）

        :param name: 文章的 metadata.name
        :return:
        """
        return await self._delete(f'{HALO_EXTENSION_API}/posts/{name}', auth=True)

    async def get_snapshot(self, name: str) -> dict[str, Any]:
        """
        获取快照资源详情（Extension API）

        :param name: 快照的 metadata.name
        :return:
        """
        return await self._get(f'/apis/content.halo.run/v1alpha1/snapshots/{name}', auth=True)

    async def list_doc_projects(self, page: int = 1, size: int = 100) -> list[dict[str, Any]]:
        """
        获取 Docsme 项目列表

        :param page: 页码
        :param size: 每页数量
        :return:
        """
        data = await self._get_docsme('/projects', params={'page': page, 'size': size})
        if isinstance(data, list):
            return data
        return data.get('items', [])

    async def list_doc_project_versions(self, project_name: str) -> list[dict[str, Any]]:
        """
        获取 Docsme 项目版本列表

        :param project_name: 项目资源名称
        :return:
        """
        data = await self._get_docsme(f'/projects/{project_name}/versions')
        if isinstance(data, list):
            return data
        return data.get('items', [])

    async def list_doc_tree_by_version(self, project_version_name: str) -> list[dict[str, Any]]:
        """
        获取 Docsme 项目版本文档树

        :param project_version_name: 项目版本资源名称
        :return:
        """
        data = await self._get_docsme(f'/projectversions/{project_version_name}/tree')
        if isinstance(data, list):
            return data
        return data.get('items', [])

    async def get_doc_tree(self, name: str) -> dict[str, Any]:
        """
        获取 Docsme 文档树节点

        :param name: DocTree 资源名称
        :return:
        """
        return await self._get_docsme(f'/doctrees/{name}')

    async def get_doc_resource(self, name: str) -> dict[str, Any]:
        """
        获取 Docsme 文档资源

        :param name: Doc 资源名称
        :return:
        """
        return await self._get_docsme(f'/docs/{name}')

    async def get_doc_head_content(self, name: str) -> dict[str, Any]:
        """
        获取 Docsme 文档最新正文

        :param name: Doc 资源名称
        :return:
        """
        return await self._get_docsme(f'/docs/{name}/head-content')


halo_client = HaloClient()
