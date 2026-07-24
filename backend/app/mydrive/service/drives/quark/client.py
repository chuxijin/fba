#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio
import re
import time

from datetime import datetime
from typing import Any

import httpx

from backend.app.mydrive.service.filesystem.exceptions import (
    AccountAuthExpiredError,
    ShareAccessDeniedError,
    ShareExpiredError,
    TransferBatchLimitError,
)
from backend.app.mydrive.service.filesystem.models import ShareLink
from backend.app.mydrive.service.metrics import observe_provider_request
from backend.common.log import log


class QuarkRequestError(Exception):
    """夸克网盘请求异常。"""

    def __init__(self, message: str, error_code: int | str | None = None) -> None:
        self.error_code = error_code
        super().__init__(message)


QUARK_SEMANTIC_ERRORS: dict[int | str, type[Exception]] = {
    41019: ShareExpiredError,
    41035: TransferBatchLimitError,
    401: AccountAuthExpiredError,
    403: ShareAccessDeniedError,
}


class QuarkRequest:
    """夸克网盘请求封装。"""

    _TASK_POLL_ATTEMPTS = 60
    _TASK_POLL_INTERVAL_SECONDS = 3
    _PAN_BASE_URL = 'https://pan.quark.cn'
    _DRIVE_BASE_URL = 'https://drive-pc.quark.cn/1/clouddrive'
    _SHARE_BASE_URL = 'https://drive-h.quark.cn/1/clouddrive'
    _USER_AGENT = (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/91.0.4472.124 Safari/537.36'
    )

    def __init__(self, cookie: str, client: httpx.AsyncClient | None = None) -> None:
        """
        初始化夸克网盘请求。

        :param cookie: 夸克网盘 Cookie
        :param client: HTTP 客户端
        """
        if not cookie.strip():
            raise ValueError('夸克网盘 Cookie 不能为空')
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            headers={'User-Agent': self._USER_AGENT},
            cookies=self._parse_cookie(cookie),
            timeout=httpx.Timeout(30),
        )

    async def aclose(self) -> None:
        """关闭夸克 HTTP 客户端。"""
        if self._owns_client:
            await self._client.aclose()

    async def get_account_info(self) -> dict[str, Any]:
        """获取夸克账户信息。"""
        last_error: QuarkRequestError | None = None
        for _ in range(2):
            try:
                return await self._request(
                    'GET',
                    self._PAN_BASE_URL,
                    '/account/info',
                    params={'fr': 'pc', 'platform': 'pc'},
                )
            except QuarkRequestError as exc:
                last_error = exc
                await asyncio.sleep(0.3)
        raise last_error or QuarkRequestError('夸克账户信息获取失败')

    async def get_member_info(self) -> dict[str, Any]:
        """获取夸克会员信息。"""
        return await self._request(
            'GET',
            self._DRIVE_BASE_URL,
            '/member',
            params={'pr': 'ucpro', 'fr': 'pc', 'fetch_subscribe': 'true', 'fetch_identity': 'true', '_ch': 'home'},
        )

    async def list_files(self, parent_id: str) -> list[dict[str, Any]]:
        """
        获取目录下所有文件。

        :param parent_id: 父目录 ID
        :return: 原始文件列表
        """
        page = 1
        page_size = 100
        files: list[dict[str, Any]] = []

        while True:
            response = await self._request(
                'GET',
                self._DRIVE_BASE_URL,
                '/file/sort',
                params={
                    'pr': 'ucpro',
                    'fr': 'pc',
                    'pdir_fid': parent_id,
                    '_page': str(page),
                    '_size': str(page_size),
                    '_fetch_total': '1',
                    '_sort': 'file_type:asc,file_name:asc',
                },
            )
            data = response.get('data', {})
            items = data.get('list', [])
            files.extend(item for item in items if isinstance(item, dict))

            total = response.get('metadata', {}).get('_total', 0)
            if len(items) < page_size or len(files) >= total:
                return files
            page += 1

    async def get_file_info(self, file_path: str) -> dict[str, Any] | None:
        """
        根据路径获取文件信息。

        :param file_path: 文件完整路径
        :return: 原始文件信息
        """
        response = await self._request(
            'POST',
            self._DRIVE_BASE_URL,
            '/file/info/path_list',
            params={'pr': 'ucpro', 'fr': 'pc'},
            data={'file_path': [file_path]},
        )
        items = response.get('data', [])
        if not items:
            return None
        first_item = items[0]
        return first_item if isinstance(first_item, dict) else None

    async def search_files(self, keyword: str, page: int = 1, page_size: int = 50) -> list[dict[str, Any]]:
        """
        搜索个人空间文件。

        :param keyword: 搜索关键词
        :param page: 页码
        :param page_size: 每页数量
        :return:
        """
        response = await self._request(
            'GET',
            self._DRIVE_BASE_URL,
            '/file/search',
            params={
                'pr': 'ucpro',
                'fr': 'pc',
                'uc_param_str': '',
                'q': keyword,
                '_page': str(page),
                '_size': str(page_size),
                '_fetch_total': '1',
                '_sort': 'file_type:desc,updated_at:desc',
                '_is_hl': '1',
            },
        )
        items = response.get('data', {}).get('list', [])
        return [item for item in items if isinstance(item, dict)]

    async def make_directory(self, parent_id: str, name: str) -> dict[str, Any]:
        """
        创建目录。

        :param parent_id: 父目录 ID
        :param name: 目录名称
        :return: 原始目录信息
        """
        response = await self._request(
            'POST',
            self._DRIVE_BASE_URL,
            '/file',
            params={'pr': 'ucpro', 'fr': 'pc'},
            data={'pdir_fid': parent_id, 'file_name': name, 'dir_path': '', 'dir_init_lock': False},
        )
        return response.get('data', {})

    async def copy_files(self, file_ids: list[str], target_id: str) -> None:
        """
        复制文件或目录。

        :param file_ids: 待复制文件 ID 列表
        :param target_id: 目标目录 ID
        :return:
        """
        await self._operate_files('/file/copy', file_ids, target_id)

    async def move_files(self, file_ids: list[str], target_id: str) -> None:
        """
        移动文件或目录。

        :param file_ids: 待移动文件 ID 列表
        :param target_id: 目标目录 ID
        :return:
        """
        await self._operate_files('/file/move', file_ids, target_id)

    async def get_share_token(self, share_id: str, passcode: str = '') -> str:
        """
        获取夸克分享访问令牌。

        :param share_id: 分享标识
        :param passcode: 提取码
        :return:
        """
        raw_share_id = share_id
        share_id = self.normalize_share_id(share_id)
        response = await self._request_share_endpoint(
            'POST',
            '/share/sharepage/token',
            params={
                'pr': 'ucpro',
                'fr': 'pc',
                'uc_param_str': '',
                '__dt': '653',
                '__t': str(int(time.time() * 1000)),
            },
            data={'pwd_id': share_id, 'passcode': passcode, 'support_visit_limit_private_share': True},
        )
        token = str(response.get('data', {}).get('stoken') or '')
        if not token:
            raise QuarkRequestError('未能获取夸克分享访问令牌')
        return token

    async def list_share_files(self, share_id: str, token: str, parent_id: str = '0') -> list[dict[str, Any]]:
        """
        获取分享目录下所有文件。

        :param share_id: 分享标识
        :param token: 分享访问令牌
        :param parent_id: 父目录 ID
        :return:
        """
        page = 1
        page_size = 100
        files: list[dict[str, Any]] = []

        while True:
            response = await self._request_share_endpoint(
                'GET',
                '/share/sharepage/detail',
                params={
                    'pr': 'ucpro',
                    'fr': 'pc',
                    'uc_param_str': '',
                    'pwd_id': share_id,
                    'stoken': token,
                    'pdir_fid': parent_id,
                    'force': '0',
                    '_page': str(page),
                    '_size': str(page_size),
                    '_fetch_banner': '1',
                    '_fetch_share': '1',
                    '_fetch_total': '1',
                    '_sort': 'file_type:asc,file_name:asc',
                    '__dt': '887',
                    '__t': str(int(time.time() * 1000)),
                },
            )
            data = response.get('data', {})
            items = data.get('list', [])
            files.extend(item for item in items if isinstance(item, dict))

            total = data.get('metadata', {}).get('_total', 0)
            if len(items) < page_size or len(files) >= total:
                return files
            page += 1

    async def save_share_files(
        self,
        share_id: str,
        token: str,
        parent_id: str,
        file_ids: list[str],
        file_tokens: list[str],
        target_id: str,
    ) -> None:
        """
        将分享文件保存到个人网盘。

        :param share_id: 分享标识
        :param token: 分享访问令牌
        :param parent_id: 分享父目录 ID
        :param file_ids: 分享文件 ID 列表
        :param file_tokens: 分享文件访问令牌列表
        :param target_id: 目标目录 ID
        :return:
        """
        response = await self._request(
            'POST',
            self._DRIVE_BASE_URL,
            '/share/sharepage/save',
            params={'pr': 'ucpro', 'fr': 'pc'},
            data={
                'fid_list': file_ids,
                'fid_token_list': file_tokens,
                'to_pdir_fid': target_id,
                'pdir_fid': parent_id,
                'pdir_save_all': False,
                'pwd_id': share_id,
                'scene': 'link',
                'stoken': token,
                'exclude_fids': [],
            },
        )
        task_id = str(response.get('data', {}).get('task_id') or '')
        if task_id:
            await self._wait_task(task_id)

    async def rename_file(self, file_id: str, new_name: str) -> None:
        """
        重命名文件或目录。

        :param file_id: 文件 ID
        :param new_name: 新名称
        :return:
        """
        await self._request(
            'POST',
            self._DRIVE_BASE_URL,
            '/file/rename',
            params={'pr': 'ucpro', 'fr': 'pc'},
            data={'fid': file_id, 'file_name': new_name},
        )

    async def remove_files(self, file_ids: list[str]) -> None:
        """
        删除文件或目录。

        :param file_ids: 文件 ID 列表
        :return:
        """
        await self._request(
            'POST',
            self._DRIVE_BASE_URL,
            '/file/delete',
            params={'pr': 'ucpro', 'fr': 'pc'},
            data={'action_type': 2, 'filelist': file_ids, 'exclude_fids': []},
        )

    async def create_share(self, file_ids: list[str], title: str, expires_in_days: int) -> ShareLink:
        """
        创建夸克网盘分享链接。

        :param file_ids: 待分享文件 ID
        :param title: 分享标题
        :param expires_in_days: 有效期天数
        :return:
        """
        expired_type = {0: 1, 1: 2, 7: 3, 30: 4}[expires_in_days]
        response = await self._request(
            'POST',
            self._DRIVE_BASE_URL,
            '/share',
            params={'pr': 'ucpro', 'fr': 'pc'},
            data={'fid_list': file_ids, 'title': title, 'url_type': 1, 'expired_type': expired_type},
        )
        task_id = str(response.get('data', {}).get('task_id') or '')
        if not task_id:
            raise QuarkRequestError('创建夸克分享任务失败')
        share_id = await self._wait_share_task(task_id)
        share_info = await self._request(
            'POST',
            self._DRIVE_BASE_URL,
            '/share/password',
            params={'pr': 'ucpro', 'fr': 'pc'},
            data={'share_id': share_id},
        )
        data = share_info.get('data', {})
        expired_at_value = data.get('expired_at')
        expired_at = datetime.fromtimestamp(int(expired_at_value) / 1000) if expired_at_value else None
        return ShareLink(
            provider='quark',
            share_id=share_id,
            title=str(data.get('title') or title),
            url=str(data.get('share_url') or ''),
            password=str(data.get('passcode') or ''),
            expires_in_days=expires_in_days,
            expired_at=expired_at,
        )

    async def list_shares(self, page: int, per_page: int) -> tuple[list[ShareLink], int]:
        """
        获取夸克网盘分享列表。

        :param page: 页码
        :param per_page: 每页数量
        :return:
        """
        response = await self._request(
            'GET', self._DRIVE_BASE_URL, '/share/mypage/detail',
            params={
                'pr': 'ucpro', 'fr': 'pc', 'uc_param_str': '', '_page': str(page), '_size': str(per_page),
                '_order_field': 'created_at', '_order_type': 'desc', '_fetch_total': '1', '_fetch_notify_follow': '1',
            },
        )
        data = response.get('data', {})
        items = data.get('list', [])
        shares = [self._build_share_link(item) for item in items if isinstance(item, dict)]
        total = int(data.get('metadata', {}).get('_total') or len(shares))
        return shares, total

    async def get_share(self, share_id: str) -> ShareLink | None:
        """
        获取夸克网盘分享详情。

        :param share_id: 分享 ID
        :return:
        """
        page = 1
        per_page = 100
        while True:
            response = await self._request(
                'GET',
                self._DRIVE_BASE_URL,
                '/share/mypage/detail',
                params={
                    'pr': 'ucpro', 'fr': 'pc', 'uc_param_str': '', '_page': str(page), '_size': str(per_page),
                    '_order_field': 'created_at', '_order_type': 'desc', '_fetch_total': '1', '_fetch_notify_follow': '1',
                },
            )
            data = response.get('data', {})
            items = [item for item in data.get('list', []) if isinstance(item, dict)]
            for item in items:
                if share_id in {str(item.get('share_id') or ''), str(item.get('pwd_id') or '')}:
                    return self._build_share_link(item)
            total = int(data.get('metadata', {}).get('_total') or 0)
            if page * per_page >= total or len(items) < per_page:
                return None
            page += 1

    async def cancel_shares(self, share_ids: list[str]) -> None:
        """
        取消夸克网盘分享链接。

        :param share_ids: 分享 ID 列表
        :return:
        """
        try:
            await self._request(
                'POST',
                self._DRIVE_BASE_URL,
                '/share/delete',
                params={'pr': 'ucpro', 'fr': 'pc', 'uc_param_str': ''},
                data={'share_ids': share_ids},
            )
        except QuarkRequestError as exc:
            if exc.error_code == 15000:
                raise QuarkRequestError('夸克未能取消该分享，链接可能不属于当前账户或已失效', error_code=15000) from exc
            raise

    async def _operate_files(self, path: str, file_ids: list[str], target_id: str) -> None:
        """
        执行夸克盘内复制或移动。

        :param path: 操作接口路径
        :param file_ids: 待操作文件 ID 列表
        :param target_id: 目标目录 ID
        :return:
        """
        await self._request(
            'POST',
            self._DRIVE_BASE_URL,
            path,
            params={'pr': 'ucpro', 'fr': 'pc'},
            data={'action_type': 1, 'filelist': file_ids, 'to_pdir_fid': target_id, 'exclude_fids': []},
        )

    async def _wait_task(self, task_id: str) -> None:
        """
        等待夸克后台任务完成。

        :param task_id: 后台任务 ID
        :return:
        """
        for _ in range(self._TASK_POLL_ATTEMPTS):
            response = await self._request(
                'GET',
                self._DRIVE_BASE_URL,
                '/task',
                params={'pr': 'ucpro', 'fr': 'pc', 'task_id': task_id, 'retry_index': '0'},
            )
            status = response.get('data', {}).get('status')
            if status == 2:
                return
            if status == 3:
                raise QuarkRequestError(str(response.get('message') or '夸克转存任务失败'))
            await asyncio.sleep(self._TASK_POLL_INTERVAL_SECONDS)
        raise QuarkRequestError('夸克转存任务超时')

    async def _wait_share_task(self, task_id: str) -> str:
        """等待夸克创建分享任务完成。"""
        for retry_index in range(10):
            response = await self._request(
                'GET',
                self._DRIVE_BASE_URL,
                '/task',
                params={'pr': 'ucpro', 'fr': 'pc', 'task_id': task_id, 'retry_index': str(retry_index)},
            )
            data = response.get('data', {})
            if data.get('status') == 2:
                share_id = str(data.get('share_id') or '')
                if share_id:
                    return share_id
                raise QuarkRequestError('夸克分享任务未返回分享标识')
            if data.get('status') == 3:
                raise QuarkRequestError(str(data.get('message') or '夸克分享任务失败'))
            await asyncio.sleep(1)
        raise QuarkRequestError('夸克分享任务超时')

    async def _request(
        self,
        method: str,
        base_url: str,
        path: str,
        *,
        params: dict[str, str],
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        发送夸克网盘请求。

        :param method: HTTP 方法
        :param base_url: API 服务地址
        :param path: 接口路径
        :param params: 查询参数
        :param data: JSON 请求体
        :return:
        """
        start_time = time.perf_counter()
        try:
            response = await self._client.request(method, f'{base_url}{path}', params=params, json=data)
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPStatusError as exc:
            self._observe_request(method, path, 'error', start_time)
            payload = _get_error_payload(exc.response)
            error_code = payload.get('code')
            error_message = str(payload.get('message') or f'夸克网盘请求失败（{method} {path}）')
            log.warning(
                '夸克网盘 HTTP 响应失败 method={} path={} status={} code={} message={}',
                method,
                path,
                exc.response.status_code,
                error_code,
                error_message,
            )
            raise _build_quark_error(error_message, error_code) from exc
        except (httpx.HTTPError, ValueError) as exc:
            self._observe_request(method, path, 'error', start_time)
            log.warning('夸克网盘请求失败 method={} path={} error={}', method, path, exc)
            raise QuarkRequestError(f'夸克网盘请求失败（{method} {path}）') from exc

        if not isinstance(payload, dict):
            self._observe_request(method, path, 'invalid_response', start_time)
            raise QuarkRequestError('夸克网盘返回了非法响应')
        if payload.get('code') not in {None, 0, '0', 'OK'}:
            self._observe_request(method, path, 'provider_error', start_time)
            log.warning(
                '夸克网盘响应失败 method={} path={} code={} message={} data_keys={}',
                method,
                path,
                payload.get('code'),
                payload.get('message'),
                sorted((payload.get('data') or {}).keys()) if isinstance(payload.get('data'), dict) else [],
            )
            raise _build_quark_error(str(payload.get('message') or '夸克网盘请求失败'), payload.get('code'))
        self._observe_request(method, path, 'success', start_time)
        return payload

    async def _request_share_endpoint(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str],
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        请求分享页接口，H 节点失败时切换 PC 节点。

        :param method: HTTP 方法
        :param path: 接口路径
        :param params: 查询参数
        :param data: JSON 请求体
        :return:
        """
        last_error: QuarkRequestError | None = None
        for base_url in [self._SHARE_BASE_URL, self._DRIVE_BASE_URL]:
            try:
                return await self._request(method, base_url, path, params=params, data=data)
            except QuarkRequestError as exc:
                last_error = exc
                log.warning('夸克分享页节点请求失败，将尝试下一个节点 base_url={} path={}', base_url, path)
        raise last_error or QuarkRequestError(f'夸克分享页请求失败（{method} {path}）')

    @staticmethod
    def _observe_request(method: str, path: str, outcome: str, start_time: float) -> None:
        """记录夸克网盘请求指标。"""
        observe_provider_request(
            provider='quark',
            method=method,
            path=path,
            outcome=outcome,
            elapsed=(time.perf_counter() - start_time) * 1000,
        )

    @staticmethod
    def normalize_share_id(value: str) -> str:
        """
        规范化夸克分享标识。

        :param value: 分享 ID 或分享链接
        :return:
        """
        source = value.strip()
        if not source:
            raise QuarkRequestError('夸克分享链接或分享 ID 不能为空')
        if 'pan.quark.cn' not in source and not source.startswith(('http://', 'https://')):
            return source
        match = re.search(r'pan\.quark\.cn/s/([^?#/]+)', source)
        if match:
            return match.group(1)
        raise QuarkRequestError('无法从夸克分享链接中提取分享 ID')

    @staticmethod
    def _parse_cookie(cookie: str) -> dict[str, str]:
        """
        解析 Cookie 字符串。

        :param cookie: Cookie 字符串
        :return:
        """
        pairs = [part.strip().split('=', 1) for part in cookie.split(';') if '=' in part]
        return {
            key.strip().encode('latin-1', errors='ignore').decode('latin-1'): value.strip().encode(
                'latin-1',
                errors='ignore',
            ).decode('latin-1')
            for key, value in pairs
            if key.strip()
        }

    @staticmethod
    def _build_share_link(value: dict[str, Any]) -> ShareLink:
        """转换夸克分享记录。"""
        expired_at_value = value.get('expired_at')
        expired_at = datetime.fromtimestamp(int(expired_at_value) / 1000) if expired_at_value else None
        return ShareLink(
            provider='quark', share_id=str(value.get('share_id') or ''), title=str(value.get('title') or ''),
            url=str(value.get('share_url') or ''), password=str(value.get('passcode') or ''),
            expires_in_days=0, expired_at=expired_at,
        )


def _get_error_payload(response: httpx.Response) -> dict[str, Any]:
    """解析夸克错误响应内容。"""
    try:
        payload = response.json()
    except ValueError:
        return {}
    if isinstance(payload, dict):
        return payload
    return {}


def _build_quark_error(message: str, error_code: int | str | None) -> Exception:
    """
    将夸克原始错误码映射为 MyDrive 领域异常。

    :param message: 网盘错误信息
    :param error_code: 夸克错误码
    :return:
    """
    error_type = QUARK_SEMANTIC_ERRORS.get(error_code)
    if error_type is None:
        error_type = QUARK_SEMANTIC_ERRORS.get(_normalize_quark_error_code(error_code))
    if error_type is not None:
        return error_type(message)
    return QuarkRequestError(message, error_code=error_code)


def _normalize_quark_error_code(error_code: int | str | None) -> int | str | None:
    """规范化夸克错误码。"""
    if isinstance(error_code, str) and error_code.isdigit():
        return int(error_code)
    return error_code
