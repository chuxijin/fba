#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio

import httpx

from backend.app.mydrive.service.drives.baidu.client import BaiduRequest


def test_baidu_request_extracts_bdstoken_from_page_assignment() -> None:
    """百度操作令牌应支持页面变量赋值格式。"""
    requests: list[httpx.Request] = []

    def handle_request(request: httpx.Request) -> httpx.Response:
        """返回百度首页令牌替身响应。"""
        requests.append(request)
        return httpx.Response(200, text='window.bdstoken = "0123456789abcdef0123456789abcdef";')

    client = httpx.AsyncClient(transport=httpx.MockTransport(
        handle_request
    ))
    request = BaiduRequest('STOKEN=value', client=client)

    token = asyncio.run(request._get_bdstoken())
    asyncio.run(client.aclose())

    assert token == '0123456789abcdef0123456789abcdef'
    assert str(requests[0].url).startswith('http://pan.baidu.com/disk/home')
    assert requests[0].url.params['app_id'] == '250528'


def test_baidu_relationship_transfer_matches_coulddrive_parameters() -> None:
    """百度群组转存参数应对齐 CouldDrive 已验证实现。"""
    requests: list[httpx.Request] = []

    def handle_request(request: httpx.Request) -> httpx.Response:
        """返回百度群组转存替身响应。"""
        requests.append(request)
        if request.url.path == '/rest/2.0/membership/user/info':
            return httpx.Response(200, json={'errno': 0, 'user_info': {'uk': '100'}})
        if request.url.path == '/disk/home':
            return httpx.Response(200, text='bdstoken":"0123456789abcdef0123456789abcdef')
        return httpx.Response(200, json={'errno': 0})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handle_request))
    request = BaiduRequest('BDUSS=value; STOKEN=value; BAIDUID=abc123', client=client)

    asyncio.run(request.transfer_relationship_files(
        space_type='group',
        source_id='group-1',
        from_uk='200',
        message_id='msg-1',
        file_ids=['300'],
        target_path='/courses',
    ))
    asyncio.run(client.aclose())

    transfer_request = requests[2]
    assert transfer_request.url.path == '/mbox/msg/transfer'
    assert transfer_request.url.params['bdstoken'] == '0123456789abcdef0123456789abcdef'
    assert transfer_request.url.params['logId'] == 'YWJjMTIz'
    assert b'fs_ids=%5B%22300%22%5D' in transfer_request.content
    assert b'gid=group-1' in transfer_request.content
