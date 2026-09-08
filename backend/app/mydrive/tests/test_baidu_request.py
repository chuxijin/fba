#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio

import httpx
import pytest

from backend.app.mydrive.service.drives.baidu.client import BaiduRequest, BaiduRequestError


def test_baidu_request_parses_legacy_share_page_context() -> None:
    """旧版分享页应继续从 locals.mset 中解析分享上下文。"""
    page = (
        '<html><body><script>'
        'locals.mset({"share_uk":1099884833520,"shareid":6322382938,"bdstoken":"legacy-token",'
        '"file_list":[{"fs_id":3,"path":"/sharelink1099884833520-1/course","server_filename":"course","isdir":0,"size":1024}]});'
        '</script></body></html>'
    )
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200, text=page)))
    request = BaiduRequest('BDUSS=value', client=client)

    context, files = asyncio.run(request.get_share_root('https://pan.baidu.com/s/1share?pwd=code'))
    asyncio.run(client.aclose())

    assert context['uk'] == 1099884833520
    assert context['share_id'] == 6322382938
    assert context['bdstoken'] == 'legacy-token'
    assert context['url'] == 'https://pan.baidu.com/s/1share'
    assert files[0]['fs_id'] == 3


def test_baidu_request_parses_v2_share_page_locals_data() -> None:
    """新版分享页应从 locals-data JSON 中解析分享上下文。"""
    page = (
        '<!doctype html><html><head></head><body>'
        '<script id="locals-data" type="application/json">\n'
        '{"uk":1103411849043,"share_uk":1099884833520,"shareid":6322382938,'
        '"bdstoken":"0ae2fa08318797fc440488a386aacf65","loginstate":1,'
        '"file_list":[{"fs_id":123,"path":"/sharelink1099884833520-456/course",'
        '"server_filename":"course","isdir":1,"size":0}]}\n'
        '</script></body></html>'
    )
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200, text=page)))
    request = BaiduRequest('BDUSS=value', client=client)

    context, files = asyncio.run(request.get_share_root('https://pan.baidu.com/s/1share'))
    asyncio.run(client.aclose())

    assert context['uk'] == 1099884833520
    assert context['share_id'] == 6322382938
    assert context['bdstoken'] == '0ae2fa08318797fc440488a386aacf65'
    assert not context['sekey']
    assert files[0]['fs_id'] == 123
    assert files[0]['server_filename'] == 'course'


def test_baidu_request_rejects_unknown_share_page() -> None:
    """无法识别的分享页面应抛出解析异常。"""
    page = '<!doctype html><html><head></head><body>disk-share-v2</body></html>'
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200, text=page)))
    request = BaiduRequest('BDUSS=value', client=client)

    with pytest.raises(BaiduRequestError, match='无法解析百度分享上下文'):
        asyncio.run(request.get_share_root('https://pan.baidu.com/s/1share'))
    asyncio.run(client.aclose())


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
