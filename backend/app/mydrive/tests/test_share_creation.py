#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio

import httpx
import pytest

from backend.app.mydrive.service.drives.baidu.client import BaiduRequest, BaiduRequestError
from backend.app.mydrive.service.filesystem.models import FileObject, SpaceLocator, SpaceType
from backend.app.mydrive.service.drives.quark.client import QuarkRequest
from backend.app.mydrive.service.drives.quark.personal_space import QuarkPersonalSpace


def test_baidu_create_share_requests_token_and_share_endpoint() -> None:
    """百度创建分享应先获取操作令牌再提交文件 ID。"""
    requests: list[httpx.Request] = []

    def handle_request(request: httpx.Request) -> httpx.Response:
        """返回百度分享请求替身响应。"""
        requests.append(request)
        if request.url.path == '/disk/home':
            return httpx.Response(200, text='bdstoken":"0123456789abcdef0123456789abcdef')
        return httpx.Response(200, json={'shareid': 12, 'link': 'https://pan.baidu.com/s/share', 'passwd': 'abcd'})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handle_request))
    request = BaiduRequest('BDUSS=value; STOKEN=value', client=client)

    share_link = asyncio.run(request.create_share(['1'], '课程资料', 7, 'abcd'))
    asyncio.run(client.aclose())

    assert share_link.share_id == '12'
    assert share_link.password == 'abcd'
    assert requests[1].url.path == '/share/pset'
    assert requests[1].url.params['bdstoken'] == '0123456789abcdef0123456789abcdef'
    assert b'fid_list=%5B1%5D' in requests[1].content


def test_quark_create_share_polls_task_and_returns_share_info() -> None:
    """夸克创建分享应轮询任务并读取最终分享信息。"""
    requests: list[httpx.Request] = []

    def handle_request(request: httpx.Request) -> httpx.Response:
        """返回夸克分享请求替身响应。"""
        requests.append(request)
        if request.url.path == '/1/clouddrive/share':
            return httpx.Response(200, json={'code': 0, 'data': {'task_id': 'task-1'}})
        if request.url.path == '/1/clouddrive/task':
            return httpx.Response(200, json={'code': 0, 'data': {'status': 2, 'share_id': 'share-1'}})
        return httpx.Response(
            200,
            json={
                'code': 0,
                'data': {'title': '课程资料', 'share_url': 'https://pan.quark.cn/s/share-1', 'passcode': 'wxyz'},
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handle_request))
    request = QuarkRequest('cookie=value', client=client)

    share_link = asyncio.run(request.create_share(['file-1'], '课程资料', 7))
    asyncio.run(client.aclose())

    assert share_link.share_id == 'share-1'
    assert share_link.password == 'wxyz'
    assert [request.url.path for request in requests] == [
        '/1/clouddrive/share',
        '/1/clouddrive/task',
        '/1/clouddrive/share/password',
    ]


def test_quark_personal_space_rejects_custom_share_password() -> None:
    """夸克个人空间不应接受无法由上游设置的提取码。"""
    space = QuarkPersonalSpace(account_id=1, cookie='cookie', client=FakeQuarkShareRequest())
    file = FileObject(
        space=SpaceLocator(provider='quark', space_type=SpaceType.PERSONAL),
        file_id='file-1',
        name='course.pdf',
        path='/course.pdf',
    )

    with pytest.raises(ValueError, match='不支持指定提取码'):
        asyncio.run(space.create_share([file], '课程资料', 7, 'abcd'))


def test_baidu_list_shares_maps_provider_records() -> None:
    """百度分享记录应转换为统一分享对象。"""

    def handle_request(request: httpx.Request) -> httpx.Response:
        """返回百度分享列表替身响应。"""
        assert request.url.path == '/share/record'
        return httpx.Response(
            200,
            json={
                'total': 2,
                'list': [
                    {
                        'shareid': 12,
                        'link': 'https://pan.baidu.com/s/share',
                        'typicalPath': '/课程/资料.pdf',
                    }
                ],
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handle_request))
    request = BaiduRequest('BDUSS=value; STOKEN=value', client=client)

    shares, total = asyncio.run(request.list_shares(1, 20))
    asyncio.run(client.aclose())

    assert total == 2
    assert shares[0].share_id == '12'
    assert shares[0].title == '资料.pdf'


def test_quark_list_shares_uses_mypage_detail_endpoint() -> None:
    """夸克分享列表应使用 CouldDrive 已验证的分享记录接口。"""
    requests: list[httpx.Request] = []

    def handle_request(request: httpx.Request) -> httpx.Response:
        """返回夸克分享列表替身响应。"""
        requests.append(request)
        return httpx.Response(
            200,
            json={
                'code': 0,
                'data': {
                    'list': [
                        {
                            'share_id': 'share-1',
                            'share_url': 'https://pan.quark.cn/s/share-1',
                            'title': '课程资料',
                        }
                    ],
                    'metadata': {'_total': 3},
                },
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handle_request))
    request = QuarkRequest('cookie=value', client=client)

    shares, total = asyncio.run(request.list_shares(1, 20))
    asyncio.run(client.aclose())

    assert total == 3
    assert shares[0].share_id == 'share-1'
    assert requests[0].url.path == '/1/clouddrive/share/mypage/detail'
    assert requests[0].url.params['uc_param_str'] == ''


def test_baidu_list_share_files_uses_page_session_context() -> None:
    """百度分享目录请求应携带分享页会话参数。"""
    requests: list[httpx.Request] = []

    def handle_request(request: httpx.Request) -> httpx.Response:
        """返回百度分享目录响应。"""
        requests.append(request)
        return httpx.Response(200, json={'errno': 0, 'list': []})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handle_request))
    request = BaiduRequest('BDUSS=value; STOKEN=value', client=client)
    context = {
        'uk': '1',
        'share_id': '2',
        'bdstoken': 'share-token',
        'sekey': 'share-session',
        'url': 'https://pan.baidu.com/s/share',
    }

    files = asyncio.run(request.list_share_files(context, '/sharelink1/course'))
    asyncio.run(client.aclose())

    assert files == []
    assert requests[0].url.path == '/share/list'
    assert 'is_from_web' not in requests[0].url.params
    assert 'sekey' not in requests[0].url.params
    assert requests[0].url.params['bdstoken'] == 'null'
    assert requests[0].url.params['dir'] == '/sharelink1/course'
    assert requests[0].headers['referer'] == 'https://pan.baidu.com/s/share'


def test_baidu_request_error_includes_provider_error_code() -> None:
    """百度接口异常应保留上游错误码便于排查。"""
    client = httpx.AsyncClient(transport=httpx.MockTransport(
        lambda request: httpx.Response(200, json={'errno': -9, 'errmsg': '百度网盘请求失败'})
    ))
    request = BaiduRequest('BDUSS=value; STOKEN=value', client=client)

    with pytest.raises(BaiduRequestError, match='错误码：-9'):
        asyncio.run(request.list_share_files({'uk': '1', 'share_id': '2', 'url': 'https://pan.baidu.com/s/share'}, '/'))
    asyncio.run(client.aclose())


def test_baidu_get_share_root_verifies_passcode_with_share_context() -> None:
    """百度分享提取码校验应使用分享页面上下文。"""
    requests: list[httpx.Request] = []

    def handle_request(request: httpx.Request) -> httpx.Response:
        """返回分享页初始化响应。"""
        requests.append(request)
        if request.url.path == '/share/verify':
            return httpx.Response(200, json={'errno': 0})
        return httpx.Response(
            200,
            text=(
                'yunData.setData({"share_uk":"1","shareid":"2","file_list":[]});'
            ),
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handle_request))
    request = BaiduRequest('BDUSS=value; STOKEN=value', client=client)

    context, files = asyncio.run(request.get_share_root('https://pan.baidu.com/s/1share?pwd=code', 'code'))
    asyncio.run(client.aclose())

    assert files == []
    assert context['bdstoken'] is None
    assert requests[0].url.path == '/share/verify'
    assert requests[0].url.params['bdstoken'] == 'null'


def test_baidu_save_share_files_uses_transfer_parameters() -> None:
    """百度转存应携带异步去重参数并提交数值文件 ID。"""
    requests: list[httpx.Request] = []

    def handle_request(request: httpx.Request) -> httpx.Response:
        """返回百度转存响应。"""
        requests.append(request)
        return httpx.Response(200, json={'errno': 0})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handle_request))
    request = BaiduRequest('BDUSS=value; STOKEN=value', client=client)
    context = {'share_id': '2', 'uk': '1', 'bdstoken': 'account-token', 'url': 'https://pan.baidu.com/s/share'}

    asyncio.run(request.save_share_files(context, ['3'], '/courses'))
    asyncio.run(client.aclose())

    assert requests[0].url.path == '/share/transfer'
    assert b'fsidlist=%5B3%5D' in requests[0].content


def test_baidu_share_sekey_prefers_pan_domain_cookie() -> None:
    """百度分享会话密钥应优先使用百度网盘域 Cookie。"""
    client = httpx.AsyncClient()
    client.cookies.set('BDCLND', 'generic-session')
    client.cookies.set('BDCLND', 'pan-session', domain='.pan.baidu.com', path='/')
    request = BaiduRequest('BDUSS=value', client=client)

    sekey = request._get_share_sekey()
    asyncio.run(client.aclose())

    assert sekey == 'pan-session'


def test_baidu_normalize_share_url_removes_query_parameters() -> None:
    """百度分享页访问应去除已校验的提取码查询参数。"""
    assert BaiduRequest._normalize_share_url('https://pan.baidu.com/s/1share?pwd=code') == 'https://pan.baidu.com/s/1share'


def test_baidu_request_uses_compatible_pan_user_agent() -> None:
    """百度分享页面请求应使用 CouldDrive 已验证的 Web User-Agent。"""
    request = BaiduRequest('BDUSS=value')

    assert request._client.headers['user-agent'] == request._PAN_USER_AGENT
    assert 'referer' not in request._client.headers
    assert request._client.headers['cookie'] == 'BDUSS=value'

    asyncio.run(request.aclose())


def test_quark_cancel_shares_sends_selected_share_ids() -> None:
    """夸克取消分享应只提交选择的分享 ID。"""
    requests: list[httpx.Request] = []

    def handle_request(request: httpx.Request) -> httpx.Response:
        """返回夸克取消分享替身响应。"""
        requests.append(request)
        return httpx.Response(200, json={'code': 0, 'data': {}})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handle_request))
    request = QuarkRequest('cookie=value', client=client)

    asyncio.run(request.cancel_shares(['share-1', 'share-2']))
    asyncio.run(client.aclose())

    assert requests[0].url.path == '/1/clouddrive/share/delete'
    assert requests[0].url.params['uc_param_str'] == ''
    assert b'"share_ids":["share-1","share-2"]' in requests[0].content


class FakeQuarkShareRequest:
    """夸克分享请求替身。"""

    async def aclose(self) -> None:
        """关闭替身。"""
