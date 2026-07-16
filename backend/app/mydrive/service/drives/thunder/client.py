#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import time
from hashlib import md5

from typing import Any

import httpx


class ThunderRequestError(Exception):
    """迅雷网盘请求异常。"""


class ThunderRequest:
    """迅雷网盘请求封装。"""

    _DRIVE_BASE_URL = 'https://api-pan.xunleix.com/drive/v1'
    _USER_BASE_URL = 'https://xluser-ssl.xunleix.com/v1'
    _CLIENT_ID = 'ZQL_zwA4qhHcoe_2'
    _CLIENT_SECRET = 'Og9Vr1L8Ee6bh0olFxFDRg'
    _CLIENT_VERSION = '1.06.0.2132'
    _PACKAGE_NAME = 'com.thunder.downloader'

    def __init__(self, credential: dict[str, Any], client: httpx.AsyncClient | None = None) -> None:
        """
        初始化迅雷网盘请求。

        :param credential: 迅雷授权凭证
        :param client: HTTP 客户端
        """
        self._credential = credential
        self._refresh_token = str(credential.get('refresh_token') or '').strip()
        if not self._refresh_token:
            raise ValueError('迅雷授权凭证缺少 refresh_token')
        self._device_id = str(credential.get('device_id') or '').strip()
        if not self._device_id:
            self._device_id = md5(self._refresh_token.encode()).hexdigest()
        self._captcha_token = str(credential.get('captcha_token') or '')
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(timeout=httpx.Timeout(30))
        self._access_token = ''
        self._token_expires_at = 0.0
        self._user_id = ''

    async def aclose(self) -> None:
        """关闭迅雷 HTTP 客户端。"""
        if self._owns_client:
            await self._client.aclose()

    @property
    def refreshed_credential(self) -> dict[str, str]:
        """获取刷新后的授权凭证。"""
        result = {'refresh_token': self._refresh_token, 'device_id': self._device_id}
        if self._captcha_token:
            result['captcha_token'] = self._captcha_token
        return result

    async def get_about(self) -> dict[str, Any]:
        """获取迅雷容量信息。"""
        return await self._request('GET', '/about')

    async def get_user(self) -> dict[str, Any]:
        """获取迅雷账户信息。"""
        return await self._request('GET', '/user/me', user_api=True)

    async def list_files(self, parent_id: str) -> list[dict[str, Any]]:
        """
        列出迅雷目录内容。

        :param parent_id: 父目录 ID
        :return:
        """
        files: list[dict[str, Any]] = []
        page_token = ''
        while True:
            response = await self._request(
                'GET',
                '/files',
                params={
                    'space': '',
                    '__type': 'drive',
                    'refresh': 'true',
                    '__sync': 'true',
                    'parent_id': parent_id,
                    'page_token': page_token,
                    'with_audit': 'true',
                    'limit': '100',
                    'filters': '{"phase":{"eq":"PHASE_TYPE_COMPLETE"},"trashed":{"eq":false}}',
                },
            )
            files.extend(item for item in response.get('files', []) if isinstance(item, dict))
            page_token = str(response.get('next_page_token') or '')
            if not page_token:
                return files

    async def make_directory(self, parent_id: str, name: str) -> dict[str, Any]:
        """
        创建迅雷目录。

        :param parent_id: 父目录 ID
        :param name: 目录名称
        :return:
        """
        return await self._request('POST', '/files', data={'kind': 'drive#folder', 'name': name, 'parent_id': parent_id})

    async def copy_files(self, file_ids: list[str], target_id: str) -> None:
        """
        在迅雷个人盘内复制文件。

        :param file_ids: 文件 ID 列表
        :param target_id: 目标目录 ID
        :return:
        """
        await self._request('POST', '/files:batchCopy', data={'to': {'parent_id': target_id}, 'ids': file_ids})

    async def move_files(self, file_ids: list[str], target_id: str) -> None:
        """
        在迅雷个人盘内移动文件。

        :param file_ids: 文件 ID 列表
        :param target_id: 目标目录 ID
        :return:
        """
        await self._request('POST', '/files:batchMove', data={'to': {'parent_id': target_id}, 'ids': file_ids})

    async def rename_file(self, file_id: str, name: str) -> None:
        """
        重命名迅雷文件。

        :param file_id: 文件 ID
        :param name: 新名称
        :return:
        """
        await self._request('PATCH', f'/files/{file_id}', data={'name': name})

    async def remove_files(self, file_ids: list[str]) -> None:
        """
        将迅雷文件移入回收站。

        :param file_ids: 文件 ID 列表
        :return:
        """
        for file_id in file_ids:
            await self._request('PATCH', f'/files/{file_id}/trash', data={})

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        data: dict[str, Any] | None = None,
        user_api: bool = False,
    ) -> dict[str, Any]:
        """
        发送迅雷认证请求。

        :param method: HTTP 方法
        :param path: 接口路径
        :param params: 查询参数
        :param data: JSON 请求体
        :param user_api: 是否使用用户服务地址
        :return:
        """
        await self._ensure_token()
        base_url = self._USER_BASE_URL if user_api else self._DRIVE_BASE_URL
        headers = {
            'Authorization': f'Bearer {self._access_token}',
            'Accept': 'application/json;charset=UTF-8',
            'x-device-id': self._device_id,
            'x-client-id': self._CLIENT_ID,
            'x-client-version': self._CLIENT_VERSION,
        }
        if self._captcha_token:
            headers['X-Captcha-Token'] = self._captcha_token
        try:
            response = await self._client.request(method, f'{base_url}{path}', params=params, json=data, headers=headers)
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ThunderRequestError(f'迅雷网盘请求失败: {exc}') from exc
        if not isinstance(payload, dict):
            raise ThunderRequestError('迅雷网盘返回了非法响应')
        if payload.get('error_code', 0) or payload.get('error') or payload.get('error_description'):
            raise ThunderRequestError(str(payload.get('error_description') or payload.get('error') or '迅雷网盘请求失败'))
        return payload

    async def _ensure_token(self) -> None:
        """刷新迅雷访问令牌。"""
        if self._access_token and time.monotonic() < self._token_expires_at:
            return
        try:
            response = await self._client.post(
                f'{self._USER_BASE_URL}/auth/token',
                json={
                    'grant_type': 'refresh_token',
                    'refresh_token': self._refresh_token,
                    'client_id': self._CLIENT_ID,
                    'client_secret': self._CLIENT_SECRET,
                },
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ThunderRequestError(f'刷新迅雷授权失败: {exc}') from exc
        access_token = str(payload.get('access_token') or '')
        refresh_token = str(payload.get('refresh_token') or '')
        if not access_token or not refresh_token:
            raise ThunderRequestError(str(payload.get('error_description') or '迅雷授权响应无效'))
        self._access_token = access_token
        self._refresh_token = refresh_token
        self._user_id = str(payload.get('sub') or payload.get('user_id') or '')
        expires_in = int(payload.get('expires_in') or 0)
        self._token_expires_at = time.monotonic() + max(expires_in - 60, 0)
