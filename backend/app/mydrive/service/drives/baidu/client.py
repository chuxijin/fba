#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import re
import time
from base64 import standard_b64encode
from dataclasses import replace
from datetime import datetime
from hashlib import md5

from typing import Any

import httpx

from backend.app.mydrive.service.metrics import observe_provider_request
from backend.app.mydrive.service.filesystem.models import ShareLink
from backend.common.log import log

class BaiduRequestError(Exception):
    """百度网盘请求异常。"""

    def __init__(self, message: str, error_code: int | None = None) -> None:
        """
        初始化百度网盘请求异常。

        :param message: 异常信息
        :param error_code: 百度错误码
        """
        super().__init__(message)
        self.error_code = error_code


class BaiduRequest:
    """百度网盘请求封装。"""

    _PAN_BASE_URL = 'https://pan.baidu.com'
    _PCS_BASE_URL = 'https://pcs.baidu.com/rest/2.0/pcs'
    _PAN_APP_ID = '250528'
    _PCS_APP_ID = '778750'
    _PAN_USER_AGENT = (
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_6) '
        'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/77.0.3865.75 Safari/537.36'
    )

    def __init__(self, cookie: str, client: httpx.AsyncClient | None = None) -> None:
        """
        初始化百度网盘请求。

        :param cookie: 百度网盘 Cookie
        :param client: HTTP 客户端
        """
        if not cookie.strip():
            raise ValueError('百度网盘 Cookie 不能为空')
        self._cookie = cookie.strip()
        self._cookies = self._parse_cookie(self._cookie)
        self._log_id = self._build_log_id(self._cookies.get('BAIDUID'))
        self._bdstoken = ''
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            headers={'User-Agent': self._PAN_USER_AGENT, 'Cookie': self._cookie},
            cookies=self._cookies,
            timeout=httpx.Timeout(30),
            follow_redirects=True,
        )

    async def aclose(self) -> None:
        """关闭百度 HTTP 客户端。"""
        if self._owns_client:
            await self._client.aclose()

    async def get_user_info(self) -> dict[str, Any]:
        """获取百度账户信息。"""
        return await self._request(
            'GET',
            f'{self._PAN_BASE_URL}/rest/2.0/membership/user/info',
            params={'method': 'query', 'clienttype': '0', 'web': '1', 'app_id': self._PAN_APP_ID},
        )

    async def get_quota(self) -> dict[str, Any]:
        """获取百度容量信息。"""
        return await self._request(
            'GET',
            f'{self._PAN_BASE_URL}/api/quota',
            params={'clienttype': '0', 'web': '1', 'app_id': self._PAN_APP_ID},
        )

    async def list_files(self, path: str) -> list[dict[str, Any]]:
        """
        列出个人目录。

        :param path: 目录路径
        :return:
        """
        response = await self._request(
            'GET',
            f'{self._PAN_BASE_URL}/api/list',
            params={
                'clienttype': '0',
                'web': '1',
                'app_id': self._PAN_APP_ID,
                'order': 'name',
                'desc': '0',
                'dir': path,
                'num': '1000',
                'page': '1',
            },
        )
        return [item for item in response.get('list', []) if isinstance(item, dict)]

    async def get_file_metadata(self, file_id: str) -> dict[str, Any] | None:
        """
        获取百度文件元数据。

        :param file_id: 文件 ID
        :return:
        """
        response = await self._request(
            'GET',
            f'{self._PAN_BASE_URL}/api/filemetas',
            params={
                'clienttype': '0',
                'dlink': '0',
                'fsids': json.dumps([int(file_id)]),
                'web': '1',
                'app_id': self._PAN_APP_ID,
            },
        )
        files = response.get('info', [])
        if not isinstance(files, list) or not files or not isinstance(files[0], dict):
            return None
        return files[0]

    async def search_files(self, keyword: str, path: str, recursive: bool = False) -> list[dict[str, Any]]:
        """
        搜索个人目录文件。

        :param keyword: 搜索关键词
        :param path: 搜索目录路径
        :param recursive: 是否递归搜索
        :return:
        """
        response = await self._request(
            'GET',
            f'{self._PCS_BASE_URL}/file',
            params={
                'method': 'search',
                'path': path,
                'wd': keyword,
                're': '1' if recursive else '0',
                'app_id': self._PCS_APP_ID,
            },
        )
        return [item for item in response.get('list', []) if isinstance(item, dict)]

    async def make_directory(self, path: str) -> dict[str, Any]:
        """
        创建个人目录。

        :param path: 目录路径
        :return:
        """
        return await self._request('GET', f'{self._PCS_BASE_URL}/file', params={'method': 'mkdir', 'path': path, 'app_id': self._PCS_APP_ID})

    async def copy_files(self, paths: list[str], target_path: str) -> None:
        """
        在个人网盘内复制文件。

        :param paths: 源文件路径列表
        :param target_path: 目标目录路径
        :return:
        """
        await self._manage_files('copy', paths, target_path)

    async def move_files(self, paths: list[str], target_path: str) -> None:
        """
        在个人网盘内移动文件。

        :param paths: 源文件路径列表
        :param target_path: 目标目录路径
        :return:
        """
        await self._manage_files('move', paths, target_path)

    async def rename_file(self, path: str, new_path: str) -> None:
        """
        重命名个人文件。

        :param path: 原路径
        :param new_path: 新路径
        :return:
        """
        await self._operate_file('move', [{'from': path, 'to': new_path}])

    async def remove_files(self, paths: list[str]) -> None:
        """
        删除个人文件。

        :param paths: 文件路径列表
        :return:
        """
        await self._operate_file('delete', [{'path': path} for path in paths])

    async def create_share(
        self,
        file_ids: list[str],
        title: str,
        expires_in_days: int,
        password: str = '',
    ) -> ShareLink:
        """
        创建百度网盘分享链接。

        :param file_ids: 待分享文件 ID
        :param title: 分享标题
        :param expires_in_days: 有效期天数
        :param password: 分享提取码
        :return:
        """
        bdstoken = await self._get_bdstoken()
        response = await self._request(
            'POST',
            f'{self._PAN_BASE_URL}/share/pset',
            params={
                'channel': 'chunlei',
                'clienttype': '0',
                'web': '1',
                'bdstoken': bdstoken,
            },
            data={
                'fid_list': json.dumps([int(file_id) for file_id in file_ids]),
                'schannel': '4' if password else '0',
                'channel_list': '[]',
                'period': str(expires_in_days),
                'is_knowledge': '0',
                'public': '0',
                'eflag_disable': 'true',
                'linkOrQrcode': 'link',
                **({'pwd': password} if password else {}),
            },
        )
        expire_time = response.get('expiretime')
        expired_at = datetime.fromtimestamp(int(expire_time)) if expire_time else None
        return ShareLink(
            provider='baidu',
            share_id=str(response.get('shareid') or ''),
            title=title,
            url=str(response.get('link') or ''),
            password=str(response.get('passwd') or ''),
            expires_in_days=expires_in_days,
            expired_at=expired_at,
        )

    async def list_shares(self, page: int, per_page: int) -> tuple[list[ShareLink], int]:
        """
        获取百度网盘分享列表。

        :param page: 页码
        :param per_page: 每页数量
        :return:
        """
        response = await self._request(
            'GET', f'{self._PAN_BASE_URL}/share/record',
            params={
                'page': str(page), 'num': str(per_page), 'desc': '1', 'order': 'time',
                'web': '1', 'clienttype': '0', 'channel': 'chunlei', 'is_batch': '1',
            },
        )
        items = response.get('list', [])
        shares = [self._build_share_link(item) for item in items if isinstance(item, dict)]
        total = int(response.get('total') or response.get('count') or len(shares))
        return shares, total

    async def get_share(self, share_id: str) -> ShareLink | None:
        """
        获取百度网盘分享详情。

        :param share_id: 分享 ID
        :return:
        """
        shares, _ = await self.list_shares(1, 100)
        share = next((item for item in shares if item.share_id == share_id), None)
        if share is None:
            return None
        response = await self._request(
            'GET', f'{self._PAN_BASE_URL}/share/surlinfoinrecord',
            params={'shareid': share_id, 'sign': md5(f'{share_id}_sharesurlinfo!@#'.encode()).hexdigest()},
        )
        return replace(share, password=str(response.get('pwd') or ''))

    async def cancel_shares(self, share_ids: list[str]) -> None:
        """
        取消百度网盘分享链接。

        :param share_ids: 分享 ID 列表
        :return:
        """
        await self._request(
            'POST', f'{self._PAN_BASE_URL}/share/cancel', params={},
            data={'shareid_list': json.dumps([int(share_id) for share_id in share_ids])},
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
        )

    async def list_friends(self, start: int = 0, limit: int = 20) -> dict[str, Any]:
        """获取百度关注好友列表。"""
        return await self._request(
            'GET',
            f'{self._PAN_BASE_URL}/mbox/relation/getfollowlist',
            params={'start': str(start), 'limit': str(limit), 'clienttype': '0', 'web': '1'},
        )

    async def list_groups(self, start: int = 0, limit: int = 20) -> dict[str, Any]:
        """获取百度群组列表。"""
        return await self._request(
            'GET',
            f'{self._PAN_BASE_URL}/mbox/group/list',
            params={'start': str(start), 'limit': str(limit), 'type': '0', 'clienttype': '0', 'web': '1'},
        )

    async def list_friend_shares(self, friend_uk: str) -> dict[str, Any]:
        """获取好友分享消息列表。"""
        return await self._request(
            'POST',
            f'{self._PAN_BASE_URL}/mbox/msg/sessioninfo',
            params={'clienttype': '0', 'web': '1'},
            data={'type': '2', 'to_uk': friend_uk},
        )

    async def list_group_shares(self, group_id: str) -> dict[str, Any]:
        """获取群组分享消息列表。"""
        return await self._request(
            'GET',
            f'{self._PAN_BASE_URL}/mbox/group/listshare',
            params={
                'clienttype': '0', 'web': '1', 'type': '2', 'gid': group_id, 'limit': '50', 'desc': '1',
            },
        )

    async def list_relationship_share_files(
        self,
        *,
        space_type: str,
        source_id: str,
        from_uk: str,
        message_id: str,
        file_id: str,
        page: int = 1,
        per_page: int = 50,
    ) -> list[dict[str, Any]]:
        """获取好友或群组分享目录内容。"""
        current_uk = await self._get_current_user_id()
        params = {
            'from_uk': from_uk,
            'msg_id': message_id,
            'num': str(per_page),
            'page': str(page),
            'fs_id': file_id,
            'clienttype': '0',
            'web': '1',
        }
        if space_type == 'friend':
            params.update({'to_uk': current_uk, 'type': '1'})
        elif space_type == 'group':
            params.update({'gid': source_id, 'type': '2', 'limit': '50', 'desc': '1'})
        else:
            raise BaiduRequestError(f'不支持的关系空间类型: {space_type}')
        response = await self._request('POST', f'{self._PAN_BASE_URL}/mbox/msg/shareinfo', params=params)
        return [item for item in response.get('records', []) if isinstance(item, dict)]

    async def transfer_relationship_files(
        self,
        *,
        space_type: str,
        source_id: str,
        from_uk: str,
        message_id: str,
        file_ids: list[str],
        target_path: str,
    ) -> None:
        """转存好友或群组分享文件。"""
        current_uk = await self._get_current_user_id()
        bdstoken = await self._get_bdstoken()
        data = {
            'from_uk': from_uk,
            'to_uk': current_uk,
            'msg_id': message_id,
            'path': target_path,
            'ondup': 'newcopy',
            'async': '1',
            'fs_ids': json.dumps([str(file_id) for file_id in file_ids], separators=(',', ':')),
            'type': '1' if space_type == 'friend' else '2',
        }
        if space_type == 'group':
            data['gid'] = source_id
        elif space_type != 'friend':
            raise BaiduRequestError(f'不支持的关系空间类型: {space_type}')
        await self._request(
            'POST',
            f'{self._PAN_BASE_URL}/mbox/msg/transfer',
            params={'channel': 'chunlei', 'clienttype': '0', 'web': '1', 'logId': self._log_id, 'bdstoken': bdstoken},
            data=data,
        )

    async def get_share_root(self, url: str, passcode: str = '') -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """
        获取分享根目录与访问上下文。

        :param url: 分享链接
        :param passcode: 提取码
        :return:
        """
        if passcode:
            shorturl = self._extract_shorturl(url)
            response = await self._request_response(
                'POST',
                f'{self._PAN_BASE_URL}/share/verify',
                params={
                    'surl': shorturl,
                    't': str(int(time.time() * 1000)),
                    'bdstoken': 'null',
                    'channel': 'chunlei',
                    'web': '1',
                    'clienttype': '0',
                },
                data={'pwd': passcode, 'vcode': '', 'vcode_str': ''},
                headers={'Referer': f'{self._PAN_BASE_URL}/share/init?surl={shorturl}'},
            )
            self._validate_response_payload(response)
            self._update_cookie_header(response)
        shared_url = self._normalize_share_url(url)
        start_time = time.perf_counter()
        try:
            response = await self._client.get(shared_url)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            self._observe_request('GET', url, 'error', start_time)
            log.warning('百度网盘请求失败 method=GET path={} error={}', self._get_metric_path(url), exc)
            raise BaiduRequestError(f'百度网盘请求失败: {exc}') from exc
        self._observe_request('GET', url, 'success', start_time)
        self._update_cookie_header(response)
        match = re.search(r'(?:yunData\.setData|locals\.mset)\((.+?)\);', response.text)
        if match is None:
            raise BaiduRequestError('无法解析百度分享上下文')
        try:
            payload = json.loads(match.group(1))
        except ValueError as exc:
            raise BaiduRequestError('百度分享上下文格式错误') from exc
        file_list = payload.get('file_list', [])
        if isinstance(file_list, dict):
            file_list = file_list.get('list', [])
        if not isinstance(file_list, list):
            file_list = []
        context = {
            'uk': payload.get('share_uk') or payload.get('uk'),
            'share_id': payload.get('shareid'),
            'bdstoken': payload.get('bdstoken'),
            'sekey': self._get_share_sekey(),
            'url': shared_url,
        }
        return context, [item for item in file_list if isinstance(item, dict)]

    async def list_share_files(self, context: dict[str, Any], path: str) -> list[dict[str, Any]]:
        """
        列出分享子目录。

        :param context: 分享访问上下文
        :param path: 分享目录路径
        :return:
        """
        response = await self._request(
            'GET',
            f'{self._PAN_BASE_URL}/share/list',
            params={
                'channel': 'chunlei',
                'clienttype': '0',
                'web': '1',
                'page': '1',
                'num': '100',
                'dir': path,
                't': str(time.time()),
                'uk': str(context['uk']),
                'shareid': str(context['share_id']),
                'desc': '1',
                'order': 'other',
                'bdstoken': 'null',
                'showempty': '0',
                'app_id': self._PAN_APP_ID,
            },
            headers={'Referer': str(context['url'])},
        )
        return [item for item in response.get('list', []) if isinstance(item, dict)]

    async def save_share_files(self, context: dict[str, Any], file_ids: list[str], target_path: str) -> None:
        """
        保存分享文件到个人网盘。

        :param context: 分享访问上下文
        :param file_ids: 分享文件 ID 列表
        :param target_path: 目标目录路径
        :return:
        """
        await self._request(
            'POST',
            f'{self._PAN_BASE_URL}/share/transfer',
            params={
                'shareid': str(context['share_id']),
                'from': str(context['uk']),
                'bdstoken': str(context.get('bdstoken') or 'null'),
                'channel': 'chunlei',
                'clienttype': '0',
                'web': '1',
                'app_id': self._PAN_APP_ID,
            },
            data={'fsidlist': json.dumps([int(file_id) for file_id in file_ids]), 'path': target_path},
            headers={'X-Requested-With': 'XMLHttpRequest', 'Origin': self._PAN_BASE_URL, 'Referer': str(context['url'])},
        )

    async def _manage_files(self, operation: str, paths: list[str], target_path: str) -> None:
        """
        执行个人盘复制或移动。

        :param operation: 操作类型
        :param paths: 源路径列表
        :param target_path: 目标目录路径
        :return:
        """
        items = [{'from': path, 'to': f'{target_path.rstrip("/")}/{path.rsplit("/", 1)[-1]}'} for path in paths]
        await self._operate_file(operation, items)

    async def _get_bdstoken(self) -> str:
        """获取百度网盘操作令牌。"""
        if self._bdstoken:
            return self._bdstoken
        start_time = time.perf_counter()
        url = 'http://pan.baidu.com/disk/home'
        try:
            response = await self._client.get(url, params={'app_id': self._PAN_APP_ID})
            response.raise_for_status()
        except httpx.HTTPError as exc:
            self._observe_request('GET', url, 'error', start_time)
            log.warning('百度网盘请求失败 method=GET path={} error={}', self._get_metric_path(url), exc)
            raise BaiduRequestError(f'获取百度网盘操作令牌失败: {exc}') from exc
        self._observe_request('GET', url, 'success', start_time)
        match = re.search(r"\bbdstoken\b\s*['\"]?[:=]\s*['\"]?([0-9a-f]{32})", response.text, re.IGNORECASE)
        if match is None:
            raise BaiduRequestError('未能从百度网盘页面获取 bdstoken，请重新同步账户 Cookie')
        self._bdstoken = match.group(1)
        return self._bdstoken

    async def _get_current_user_id(self) -> str:
        """获取当前登录百度账户标识。"""
        response = await self.get_user_info()
        user_id = str(response.get('user_info', {}).get('uk') or '')
        if not user_id:
            raise BaiduRequestError('未能获取当前百度账户标识')
        return user_id

    async def _operate_file(self, operation: str, items: list[dict[str, str]]) -> None:
        """
        调用百度文件操作接口。

        :param operation: 操作类型
        :param items: 操作对象列表
        :return:
        """
        await self._request(
            'POST',
            f'{self._PCS_BASE_URL}/file',
            params={'method': operation, 'app_id': self._PCS_APP_ID},
            data={'param': json.dumps({'list': items}, separators=(',', ':'))},
        )

    async def _request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, str],
        data: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """
        发送百度网盘请求。

        :param method: HTTP 方法
        :param url: 请求地址
        :param params: 查询参数
        :param data: 表单请求体
        :param headers: 请求头
        :return:
        """
        response = await self._request_response(method, url, params=params, data=data, headers=headers)
        return self._validate_response_payload(response)

    def _validate_response_payload(self, response: httpx.Response) -> dict[str, Any]:
        """解析并验证百度网盘 JSON 响应。"""
        try:
            payload = response.json()
        except ValueError as exc:
            raise BaiduRequestError(f'百度网盘请求失败: {exc}') from exc
        if not isinstance(payload, dict):
            raise BaiduRequestError('百度网盘返回了非法响应')
        if payload.get('errno', 0) != 0 or payload.get('error_code', 0) != 0:
            raw_error_code = payload.get('errno') or payload.get('error_code')
            try:
                error_code = int(raw_error_code)
            except (TypeError, ValueError):
                error_code = None
            message = str(payload.get('errmsg') or payload.get('error_msg') or '百度网盘请求失败')
            raise BaiduRequestError(f'{message}，错误码：{raw_error_code}', error_code=error_code)
        return payload

    async def _request_response(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, str],
        data: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        """发送百度网盘请求并返回原始响应。"""
        start_time = time.perf_counter()
        try:
            response = await self._client.request(method, url, params=params, data=data, headers=headers)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            self._observe_request(method, url, 'error', start_time)
            log.warning('百度网盘请求失败 method={} path={} error={}', method, self._get_metric_path(url), exc)
            raise BaiduRequestError(f'百度网盘请求失败: {exc}') from exc
        self._observe_request(method, url, 'success', start_time)
        return response

    @staticmethod
    def _observe_request(method: str, url: str, outcome: str, start_time: float) -> None:
        """记录百度网盘请求指标。"""
        observe_provider_request(
            provider='baidu',
            method=method,
            path=BaiduRequest._get_metric_path(url),
            outcome=outcome,
            elapsed=(time.perf_counter() - start_time) * 1000,
        )

    @staticmethod
    def _get_metric_path(url: str) -> str:
        """提取不含查询参数的指标路径。"""
        return httpx.URL(url).path

    @staticmethod
    def _build_share_link(value: dict[str, Any]) -> ShareLink:
        """转换百度分享记录。"""
        paths = value.get('paths') or [value.get('typicalPath')]
        title = str(next((path for path in paths if path), '百度分享')).rsplit('/', 1)[-1]
        return ShareLink(
            provider='baidu', share_id=str(value.get('share_id') or value.get('shareId') or value.get('shareid') or ''),
            title=title, url=str(value.get('link') or value.get('shortlink') or ''),
            password=str(value.get('password') or ''), expires_in_days=0,
        )

    @staticmethod
    def _extract_shorturl(url: str) -> str:
        """
        提取百度分享短链接标识。

        :param url: 分享链接
        :return:
        """
        match = re.search(r'/s/1?([^?#/]+)', url)
        if match is None:
            raise BaiduRequestError('无效的百度分享链接')
        return match.group(1)

    @staticmethod
    def _normalize_share_url(url: str) -> str:
        """移除提取码等查询参数，构建已验证分享页地址。"""
        parsed_url = httpx.URL(url)
        return str(parsed_url.copy_with(query=None))

    @staticmethod
    def _parse_cookie(cookie: str) -> dict[str, str]:
        """
        解析 Cookie 字符串。

        :param cookie: Cookie 字符串
        :return:
        """
        pairs = [part.strip().split('=', 1) for part in cookie.split(';') if '=' in part]
        return {key.strip(): value.strip() for key, value in pairs if key.strip()}

    @staticmethod
    def _build_log_id(baiduid: str | None) -> str:
        """按百度 Web 端格式构建 logId。"""
        if not baiduid:
            return ''
        try:
            return standard_b64encode(baiduid.encode('ascii')).decode('utf-8')
        except UnicodeEncodeError:
            return ''

    def _get_share_sekey(self) -> str:
        """获取分享页面生成的访问密钥。"""
        cookies = [cookie for cookie in self._client.cookies.jar if cookie.name == 'BDCLND']
        domain_cookie = next((cookie for cookie in cookies if cookie.domain.endswith('pan.baidu.com')), None)
        if domain_cookie is not None:
            return domain_cookie.value
        return cookies[0].value if cookies else ''

    def _update_cookie_header(self, response: httpx.Response) -> None:
        """合并分享流程中返回的临时 Cookie。"""
        cookies = self._parse_cookie(self._cookie)
        cookies.update(response.cookies)
        self._cookie = '; '.join(f'{key}={value}' for key, value in cookies.items())
        self._client.headers['Cookie'] = self._cookie
