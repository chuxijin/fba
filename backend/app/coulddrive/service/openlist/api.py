#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from enum import Enum
from functools import partial
from typing import Any

import requests
from starlette.concurrency import run_in_threadpool

from backend.core.conf import settings

from backend.app.coulddrive.service.openlist.errors import OpenListApiError
from backend.app.coulddrive.service.openlist.errors import assert_ok

OPENLIST_UA = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
    'AppleWebKit/537.36 (KHTML, like Gecko) '
    'Chrome/125.0.0.0 Safari/537.36'
)
OPENLIST_HEADERS = {'User-Agent': OPENLIST_UA, 'Content-Type': 'application/json'}


class Method(Enum):
    """HTTP 方法枚举"""

    GET = 'GET'
    POST = 'POST'


class OpenListNode(Enum):
    """OpenList API 节点"""

    ACCOUNT = '/api/me'
    FILE_LIST = '/api/fs/list'
    FILE_REMOVE = '/api/fs/remove'
    FILE_COPY = '/api/fs/copy'
    FILE_MOVE = '/api/fs/move'
    FILE_RENAME = '/api/fs/rename'
    FILE_MKDIR = '/api/fs/mkdir'
    COPY_TASK_INFO = '/api/admin/task/copy/info'
    COPY_TASK_DELETE = '/api/admin/task/copy/delete'

    def url(self, base_url: str) -> str:
        """
        拼接完整请求地址

        :param base_url: OpenList 服务地址
        :return:
        """
        return f'{base_url}{self.value}'


class OpenListApi:
    """OpenList API 封装"""

    def __init__(self, token: str):
        """
        初始化 OpenList API

        :param token: OpenList 令牌
        :return:
        """
        base_url = settings.OPENLIST_BASE_URL.strip().rstrip('/')
        if not base_url:
            raise OpenListApiError('未配置 OPENLIST_BASE_URL')
        if not token or not token.strip():
            raise OpenListApiError('OpenList Token 不能为空')

        self._base_url = base_url
        self._token = token.strip()
        self._session = requests.Session()
        self._timeout = settings.HTTP_REQUEST_TIMEOUT
        self._headers = OPENLIST_HEADERS.copy()
        self._headers['Authorization'] = self._token

    @property
    def cookies(self) -> str:
        """获取当前 Token"""
        return self._token

    async def _request_raw(
        self,
        method: Method,
        url: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        data: dict[str, Any] | None = None,
        timeout: float | tuple[float, float] | None = None,
        **kwargs,
    ) -> requests.Response:
        """
        发送原始请求

        :param method: HTTP 方法
        :param url: 完整请求地址
        :param params: URL 参数
        :param headers: 请求头
        :param data: JSON 请求体
        :param timeout: 超时时间
        :return:
        """
        request_callable = partial(
            self._session.request,
            method.value,
            url,
            params=params or {},
            headers=headers or self._headers,
            json=data,
            timeout=timeout or self._timeout,
            **kwargs,
        )

        try:
            return await run_in_threadpool(request_callable)
        except requests.RequestException as err:
            raise OpenListApiError(f'OpenList 请求失败: {err}', cause=err) from err

    async def _request(
        self,
        method: Method,
        url: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        data: dict[str, Any] | None = None,
        timeout: float | tuple[float, float] | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """
        发送并解析 JSON 请求

        :param method: HTTP 方法
        :param url: 完整请求地址
        :param params: URL 参数
        :param headers: 请求头
        :param data: JSON 请求体
        :param timeout: 超时时间
        :return:
        """
        response = await self._request_raw(
            method=method,
            url=url,
            params=params,
            headers=headers,
            data=data,
            timeout=timeout,
            **kwargs,
        )

        try:
            payload = response.json()
        except ValueError as err:
            raise OpenListApiError(f'OpenList 返回了非法 JSON: {response.text[:200]}', cause=err) from err

        if response.status_code != 200:
            message = payload.get('message') if isinstance(payload, dict) else response.text
            raise OpenListApiError(
                f'OpenList 请求失败: HTTP {response.status_code}, message: {message}',
                error_code=response.status_code,
            )

        return payload

    @assert_ok
    async def get_account_info(self) -> dict[str, Any]:
        """获取当前账户信息"""
        return await self._request(Method.GET, OpenListNode.ACCOUNT.url(self._base_url))

    @assert_ok
    async def list(self, file_path: str, page: int = 1, num: int = 0, refresh: bool = False) -> dict[str, Any]:
        """
        获取目录列表

        :param file_path: 目录路径
        :param page: 页码
        :param num: 每页数量
        :param refresh: 是否刷新缓存
        :return:
        """
        return await self._request(
            Method.POST,
            OpenListNode.FILE_LIST.url(self._base_url),
            data={'path': file_path, 'page': page, 'per_page': num, 'refresh': refresh},
        )

    @assert_ok
    async def mkdir(self, path: str) -> dict[str, Any]:
        """
        创建目录

        :param path: 完整目录路径
        :return:
        """
        return await self._request(
            Method.POST,
            OpenListNode.FILE_MKDIR.url(self._base_url),
            data={'path': path},
        )

    @assert_ok
    async def remove(self, names: list[str], dir: str) -> dict[str, Any]:
        """
        删除文件或目录

        :param names: 文件名列表
        :param dir: 父目录路径
        :return:
        """
        return await self._request(
            Method.POST,
            OpenListNode.FILE_REMOVE.url(self._base_url),
            data={'names': names, 'dir': dir},
        )

    @assert_ok
    async def copy(self, src_dir: str, dst_dir: str, names: list[str]) -> dict[str, Any]:
        """
        复制文件或目录

        :param src_dir: 源目录路径
        :param dst_dir: 目标目录路径
        :param names: 文件名列表
        :return:
        """
        return await self._request(
            Method.POST,
            OpenListNode.FILE_COPY.url(self._base_url),
            data={'src_dir': src_dir, 'dst_dir': dst_dir, 'names': names, 'overwrite': True},
        )

    @assert_ok
    async def move(self, src_dir: str, dst_dir: str, names: list[str]) -> dict[str, Any]:
        """
        移动文件或目录

        :param src_dir: 源目录路径
        :param dst_dir: 目标目录路径
        :param names: 文件名列表
        :return:
        """
        return await self._request(
            Method.POST,
            OpenListNode.FILE_MOVE.url(self._base_url),
            data={'src_dir': src_dir, 'dst_dir': dst_dir, 'names': names, 'overwrite': True},
        )

    @assert_ok
    async def rename(self, path: str, name: str) -> dict[str, Any]:
        """
        重命名文件或目录

        :param path: 原始路径
        :param name: 新名称
        :return:
        """
        return await self._request(
            Method.POST,
            OpenListNode.FILE_RENAME.url(self._base_url),
            data={'path': path, 'name': name},
        )

    @assert_ok
    async def copy_task_info(self, task_id: str) -> dict[str, Any]:
        """
        获取复制任务详情

        :param task_id: OpenList 任务 ID
        :return:
        """
        return await self._request(
            Method.POST,
            OpenListNode.COPY_TASK_INFO.url(self._base_url),
            params={'tid': task_id},
        )

    @assert_ok
    async def copy_task_delete(self, task_id: str) -> dict[str, Any]:
        """
        删除复制任务记录

        :param task_id: OpenList 任务 ID
        :return:
        """
        return await self._request(
            Method.POST,
            OpenListNode.COPY_TASK_DELETE.url(self._base_url),
            params={'tid': task_id},
        )
