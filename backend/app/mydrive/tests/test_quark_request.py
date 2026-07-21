#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio

import httpx

from backend.app.mydrive.service.filesystem.exceptions import ShareExpiredError, TransferBatchLimitError
from backend.app.mydrive.service.drives.quark.client import QuarkRequest


def test_quark_request_parses_cookie_when_creating_client() -> None:
    """夸克请求客户端应能在初始化时解析 Cookie。"""
    request = QuarkRequest('first=value; second=another')
    assert request._client.cookies.get('first') == 'value'
    assert request._client.cookies.get('second') == 'another'
    asyncio.run(request.aclose())


def test_quark_request_calls_personal_disk_endpoint_directly() -> None:
    """夸克请求层应直接调用个人盘接口。"""
    requests: list[httpx.Request] = []

    def handle_request(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={'code': 0, 'data': {'list': []}, 'metadata': {'_total': 0}})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handle_request))
    request = QuarkRequest('cookie=value', client=client)

    files = asyncio.run(request.list_files('0'))
    asyncio.run(client.aclose())

    assert files == []
    assert requests[0].url.path == '/1/clouddrive/file/sort'
    assert requests[0].url.params['pdir_fid'] == '0'


def test_quark_share_requests_include_sharepage_parameters() -> None:
    """夸克分享页请求应携带 CouldDrive 已验证参数。"""
    requests: list[httpx.Request] = []

    def handle_request(request: httpx.Request) -> httpx.Response:
        """返回夸克分享页替身响应。"""
        requests.append(request)
        if request.url.path.endswith('/token'):
            return httpx.Response(200, json={'code': 0, 'data': {'stoken': 'share-token'}})
        return httpx.Response(200, json={'code': 0, 'data': {'list': [], 'metadata': {'_total': 0}}})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handle_request))
    request = QuarkRequest('cookie=value', client=client)

    token = asyncio.run(request.get_share_token('share-1', 'abcd'))
    files = asyncio.run(request.list_share_files('share-1', token))
    asyncio.run(client.aclose())

    assert files == []
    assert requests[0].url.path == '/1/clouddrive/share/sharepage/token'
    assert requests[0].url.params['uc_param_str'] == ''
    assert requests[0].url.params['__dt'] == '653'
    assert requests[0].url.params['__t']
    assert requests[1].url.path == '/1/clouddrive/share/sharepage/detail'
    assert requests[1].url.params['force'] == '0'
    assert requests[1].url.params['_fetch_banner'] == '1'
    assert requests[1].url.params['_fetch_share'] == '1'
    assert requests[1].url.params['__dt'] == '887'
    assert requests[1].url.params['__t']


def test_quark_share_token_falls_back_to_pc_endpoint() -> None:
    """夸克 H 节点分享 token 失败时应尝试 PC 节点。"""
    requests: list[httpx.Request] = []

    def handle_request(request: httpx.Request) -> httpx.Response:
        """返回分享 token 节点替身响应。"""
        requests.append(request)
        if request.url.host == 'drive-h.quark.cn':
            return httpx.Response(404, json={})
        return httpx.Response(200, json={'code': 0, 'data': {'stoken': 'share-token'}})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handle_request))
    request = QuarkRequest('cookie=value', client=client)

    token = asyncio.run(request.get_share_token('https://pan.quark.cn/s/share-1'))
    asyncio.run(client.aclose())

    assert token == 'share-token'
    assert requests[0].url.host == 'drive-h.quark.cn'
    assert requests[1].url.host == 'drive-pc.quark.cn'
    assert requests[1].url.path == '/1/clouddrive/share/sharepage/token'


def test_quark_share_token_maps_expired_code_to_domain_error() -> None:
    """夸克过期分享应映射为 MyDrive 领域异常。"""
    def handle_request(request: httpx.Request) -> httpx.Response:
        """返回过期分享替身响应。"""
        return httpx.Response(200, json={'code': 41019, 'message': '分享地址已过期'})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handle_request))
    request = QuarkRequest('cookie=value', client=client)

    try:
        asyncio.run(request.get_share_token('share-1'))
    except ShareExpiredError as exc:
        assert str(exc) == '分享地址已过期'
    else:
        raise AssertionError('预期抛出夸克分享过期异常')
    finally:
        asyncio.run(client.aclose())


def test_quark_transfer_task_maps_batch_limit_code_to_domain_error() -> None:
    """夸克转存数量限制应映射为 MyDrive 领域异常。"""
    def handle_request(request: httpx.Request) -> httpx.Response:
        """返回转存任务数量限制替身响应。"""
        if request.url.path.endswith('/share/sharepage/save'):
            return httpx.Response(200, json={'code': 0, 'data': {'task_id': 'task-1'}})
        return httpx.Response(200, json={'code': 41035, 'message': '单次转存文件个数超出用户等级限制'})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handle_request))
    request = QuarkRequest('cookie=value', client=client)

    try:
        asyncio.run(request.save_share_files('share-1', 'token', '0', ['file-1'], ['token-1'], '0'))
    except TransferBatchLimitError as exc:
        assert str(exc) == '单次转存文件个数超出用户等级限制'
    else:
        raise AssertionError('预期抛出夸克转存数量限制异常')
    finally:
        asyncio.run(client.aclose())


def test_quark_request_normalizes_share_url_to_share_id() -> None:
    """夸克分享链接应转换为 API 所需的分享 ID。"""
    assert QuarkRequest.normalize_share_id('https://pan.quark.cn/s/share-1#/list/share') == 'share-1'
    assert QuarkRequest.normalize_share_id('share-1') == 'share-1'


def test_quark_get_share_resolves_local_share_id_by_pwd_id() -> None:
    """夸克外链 pwd_id 应能定位到本地分享记录的 share_id。"""
    def handle_request(request: httpx.Request) -> httpx.Response:
        """返回本地分享记录替身响应。"""
        return httpx.Response(200, json={
            'code': 0,
            'data': {
                'list': [{
                    'share_id': 'local-share-id',
                    'pwd_id': 'external-pwd-id',
                    'share_url': 'https://pan.quark.cn/s/external-pwd-id',
                    'title': '测试分享',
                }],
                'metadata': {'_total': 1},
            },
        })

    client = httpx.AsyncClient(transport=httpx.MockTransport(handle_request))
    request = QuarkRequest('cookie=value', client=client)

    share = asyncio.run(request.get_share('external-pwd-id'))
    asyncio.run(client.aclose())

    assert share is not None
    assert share.share_id == 'local-share-id'
