#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio
import hashlib

from typing import Self
from urllib.parse import urlencode

import pytest

from backend.common.exception import errors
from backend.common.payment.providers import hupijiao as hupijiao_module
from backend.common.payment.providers.hupijiao import HupijiaoPayProvider, hupijiao_pay_provider

APPID = '201906181755'
APPSECRET = 'b7f8f0b1d0b0c1a2e3f4051627384950'
NOTIFY_URL = 'https://pay.example.com/api/v1/payment/pay/hupijiao/notify'


@pytest.fixture
def configured(monkeypatch: pytest.MonkeyPatch) -> HupijiaoPayProvider:
    """配置渠道凭证与回调地址，隔离真实环境配置。"""
    monkeypatch.setattr(hupijiao_module.settings, 'HUPIJIAO_APPID', APPID, raising=False)
    monkeypatch.setattr(hupijiao_module.settings, 'HUPIJIAO_APPSECRET', APPSECRET, raising=False)
    monkeypatch.setattr(hupijiao_module.settings, 'HUPIJIAO_API_BASE_URL', 'https://api.xunhupay.com', raising=False)
    monkeypatch.setattr(hupijiao_module.settings, 'HUPIJIAO_NOTIFY_URL', NOTIFY_URL, raising=False)
    monkeypatch.setattr(hupijiao_module.settings, 'HUPIJIAO_RETURN_URL', '', raising=False)
    return hupijiao_pay_provider


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


class _FakeAsyncClient:
    def __init__(self, payload: dict, captured: dict) -> None:
        self._payload = payload
        self._captured = captured

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc_info: object) -> bool:
        return False

    async def post(self, url: str, **kwargs: object) -> _FakeResponse:
        self._captured['url'] = url
        self._captured['kwargs'] = kwargs
        return _FakeResponse(self._payload)


def _install_client(monkeypatch: pytest.MonkeyPatch, payload: dict, captured: dict) -> None:
    """替换 httpx 客户端，捕获请求参数并返回固定响应。"""

    def factory(**kwargs: object) -> _FakeAsyncClient:
        captured['client_kwargs'] = kwargs
        return _FakeAsyncClient(payload, captured)

    monkeypatch.setattr(hupijiao_module.httpx, 'AsyncClient', factory)


def _signed(payload: dict) -> dict:
    """按渠道规则为伪造响应补充签名。"""
    data = dict(payload)
    data['hash'] = hupijiao_pay_provider._sign(data, APPSECRET)
    return data


def _signed_form(params: dict) -> bytes:
    """构造带签名的回调表单。"""
    data = dict(params)
    data['hash'] = hupijiao_pay_provider._sign(data, APPSECRET)
    return urlencode(data).encode('utf-8')


FORM_HEADERS = {'content-type': 'application/x-www-form-urlencoded'}


def test_sign_sorts_keys_and_appends_secret_without_url_encoding() -> None:
    """签名按 ASCII 升序原值拼接，跳过 hash 与空值，末尾追加密钥。"""
    data = {'b': '2', 'a': '1', 'hash': 'ignored', 'empty': '', 'skip': None}
    expected = hashlib.md5(b'a=1&b=2' + APPSECRET.encode('utf-8')).hexdigest()
    assert hupijiao_pay_provider._sign(data, APPSECRET) == expected


def test_sign_treats_zero_as_non_empty() -> None:
    """官方规则只跳过 null 与空字符串，数字 0 必须参与签名。"""
    data = {'errcode': 0, 'errmsg': 'success!', 'url': 'https://api.xunhupay.com/pay'}
    expected = hashlib.md5(
        b'errcode=0&errmsg=success!&url=https://api.xunhupay.com/pay' + APPSECRET.encode('utf-8')
    ).hexdigest()
    assert hupijiao_pay_provider._sign(data, APPSECRET) == expected


def test_sign_keeps_allowed_order_no_characters() -> None:
    """订单号允许的字符原样参与签名，不做 URL 编码。"""
    data = {'trade_order_id': 'PO-2026*01', 'total_fee': '0.10'}
    expected = hashlib.md5(b'total_fee=0.10&trade_order_id=PO-2026*01' + APPSECRET.encode('utf-8')).hexdigest()
    assert hupijiao_pay_provider._sign(data, APPSECRET) == expected


def test_response_signature_covers_errcode_zero(
    configured: HupijiaoPayProvider, monkeypatch: pytest.MonkeyPatch
) -> None:
    """下单响应含 errcode=0，按官方规则独立计算的签名必须通过校验。"""
    captured: dict = {}
    qrcode = 'https://api.xunhupay.com/qr/abc.png'
    payload = {'errcode': 0, 'errmsg': 'success!', 'url_qrcode': qrcode}
    payload['hash'] = hashlib.md5(
        f'errcode=0&errmsg=success!&url_qrcode={qrcode}'.encode() + APPSECRET.encode('utf-8')
    ).hexdigest()
    _install_client(monkeypatch, payload, captured)

    result = asyncio.run(hupijiao_pay_provider.prepay(order_no='PO20261009001', total_fee=10, description='会员'))

    assert result['url_qrcode'] == qrcode


def test_prepay_requires_configured_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    """未配置凭证时应明确报错而不是发出无效请求。"""
    monkeypatch.setattr(hupijiao_module.settings, 'HUPIJIAO_APPID', '', raising=False)
    monkeypatch.setattr(hupijiao_module.settings, 'HUPIJIAO_APPSECRET', '', raising=False)

    with pytest.raises(errors.ServerError):
        asyncio.run(hupijiao_pay_provider.prepay(order_no='PO20261009001', total_fee=100, description='会员'))


def test_prepay_rejects_non_https_notify_url(configured: HupijiaoPayProvider, monkeypatch: pytest.MonkeyPatch) -> None:
    """回调地址必须为 HTTPS。"""
    monkeypatch.setattr(hupijiao_module.settings, 'HUPIJIAO_NOTIFY_URL', 'http://pay.example.com/notify', raising=False)

    with pytest.raises(errors.ServerError):
        asyncio.run(hupijiao_pay_provider.prepay(order_no='PO20261009001', total_fee=100, description='会员'))


def test_prepay_rejects_sandbox_env(configured: HupijiaoPayProvider) -> None:
    """虎皮椒不支持微信虚拟支付沙箱环境。"""
    with pytest.raises(errors.RequestError):
        asyncio.run(
            hupijiao_pay_provider.prepay(order_no='PO20261009001', total_fee=100, description='会员', env=1)
        )


def test_prepay_posts_json_and_returns_qrcode(configured: HupijiaoPayProvider, monkeypatch: pytest.MonkeyPatch) -> None:
    """下单使用 JSON 报文并将金额元转换为两位小数字符串。"""
    captured: dict = {}
    payload = _signed(
        {
            'errcode': 0,
            'errmsg': '',
            'url_qrcode': 'https://api.xunhupay.com/qrcode/abc.png',
            'url': 'https://api.xunhupay.com/pay/abc',
        }
    )
    _install_client(monkeypatch, payload, captured)

    result = asyncio.run(
        hupijiao_pay_provider.prepay(order_no='PO20261009001', total_fee=1990, description='年度会员')
    )

    assert result['url_qrcode'] == 'https://api.xunhupay.com/qrcode/abc.png'
    assert result['url'] == 'https://api.xunhupay.com/pay/abc'
    assert captured['url'] == 'https://api.xunhupay.com/payment/do.html'
    assert captured['client_kwargs']['follow_redirects'] is False
    body = captured['kwargs']['json']
    assert body['version'] == '1.1'
    assert body['trade_order_id'] == 'PO20261009001'
    assert body['total_fee'] == '19.90'
    assert body['title'] == '年度会员'
    assert body['notify_url'] == NOTIFY_URL
    assert body['appid'] == APPID
    assert isinstance(body['time'], int)
    assert body['hash'] == hupijiao_pay_provider._sign(body, APPSECRET)


def test_prepay_omits_blank_return_url(configured: HupijiaoPayProvider, monkeypatch: pytest.MonkeyPatch) -> None:
    """未配置跳转地址时不下发 return_url。"""
    captured: dict = {}
    _install_client(monkeypatch, _signed({'errcode': 0, 'errmsg': '', 'url': 'https://x/pay'}), captured)

    asyncio.run(hupijiao_pay_provider.prepay(order_no='PO20261009002', total_fee=100, description='会员'))

    assert 'return_url' not in captured['kwargs']['json']


def test_prepay_rejects_invalid_order_no(configured: HupijiaoPayProvider) -> None:
    """订单号需符合渠道字符与长度限制。"""
    for order_no in ('PO 2026', 'PO#2026', 'A' * 33):
        with pytest.raises(errors.RequestError):
            asyncio.run(hupijiao_pay_provider.prepay(order_no=order_no, total_fee=100, description='会员'))


def test_prepay_requires_positive_amount(configured: HupijiaoPayProvider) -> None:
    """金额必须大于零。"""
    with pytest.raises(errors.RequestError):
        asyncio.run(hupijiao_pay_provider.prepay(order_no='PO20261009001', total_fee=0, description='会员'))


def test_query_posts_form_with_out_trade_order(
    configured: HupijiaoPayProvider, monkeypatch: pytest.MonkeyPatch
) -> None:
    """查单使用表单参数 out_trade_order。"""
    captured: dict = {}
    payload = {
        'errcode': 0,
        'errmsg': '',
        'data': {'out_trade_order': 'PO20261009001', 'transaction_id': 'TX1', 'status': 'OD'},
    }
    _install_client(monkeypatch, payload, captured)

    result = asyncio.run(hupijiao_pay_provider.query(order_no='PO20261009001'))

    assert result == payload
    assert captured['url'] == 'https://api.xunhupay.com/payment/query.html'
    assert captured['kwargs']['data']['out_trade_order'] == 'PO20261009001'


def test_request_rejects_invalid_response_signature(
    configured: HupijiaoPayProvider, monkeypatch: pytest.MonkeyPatch
) -> None:
    """平面响应验签失败时必须拒绝。"""
    captured: dict = {}
    payload = {'errcode': 0, 'errmsg': '', 'url': 'https://x/pay', 'hash': '0' * 32}
    _install_client(monkeypatch, payload, captured)

    with pytest.raises(errors.GatewayError):
        asyncio.run(hupijiao_pay_provider.prepay(order_no='PO20261009001', total_fee=100, description='会员'))


def test_request_rejects_business_error_code(configured: HupijiaoPayProvider, monkeypatch: pytest.MonkeyPatch) -> None:
    """渠道返回非零 errcode 时抛出网关错误。"""
    captured: dict = {}
    _install_client(monkeypatch, _signed({'errcode': 40001, 'errmsg': '签名错误'}), captured)

    with pytest.raises(errors.GatewayError):
        asyncio.run(hupijiao_pay_provider.prepay(order_no='PO20261009001', total_fee=100, description='会员'))


def test_amount_to_fen_rejects_sub_cent_and_non_positive() -> None:
    """金额必须为精确到分的正数。"""
    for value in ('19.905', '0', '-1', 'abc', None):
        with pytest.raises(ValueError):
            HupijiaoPayProvider._amount_to_fen(value)


def test_amount_to_fen_parses_decimal_strings() -> None:
    """金额字符串精确转换为分。"""
    assert HupijiaoPayProvider._amount_to_fen('19.90') == 1990
    assert HupijiaoPayProvider._amount_to_fen(0.01) == 1


def test_decrypt_callback_accepts_signed_form(configured: HupijiaoPayProvider) -> None:
    """合法回调应返回平面参数。"""
    body = _signed_form(
        {
            'appid': APPID,
            'trade_order_id': 'PO20261009001',
            'transaction_id': 'TX1',
            'total_fee': '19.90',
            'status': 'OD',
        }
    )

    data = hupijiao_pay_provider.decrypt_callback(headers=FORM_HEADERS, body=body)

    assert data['trade_order_id'] == 'PO20261009001'
    assert data['status'] == 'OD'


def test_decrypt_callback_rejects_non_form_content_type(configured: HupijiaoPayProvider) -> None:
    """回调必须为 URL 编码表单。"""
    with pytest.raises(ValueError):
        hupijiao_pay_provider.decrypt_callback(
            headers={'content-type': 'application/json'},
            body=_signed_form({'appid': APPID, 'trade_order_id': 'PO1', 'status': 'OD'}),
        )


def test_decrypt_callback_rejects_appid_mismatch(configured: HupijiaoPayProvider) -> None:
    """回调 APPID 必须与配置一致。"""
    with pytest.raises(ValueError):
        hupijiao_pay_provider.decrypt_callback(
            headers=FORM_HEADERS,
            body=_signed_form({'appid': '9999', 'trade_order_id': 'PO1', 'status': 'OD'}),
        )


def test_decrypt_callback_rejects_tampered_signature(configured: HupijiaoPayProvider) -> None:
    """篡改金额后验签必须失败。"""
    body = _signed_form({'appid': APPID, 'trade_order_id': 'PO1', 'total_fee': '19.90', 'status': 'OD'})
    tampered = body.replace(b'19.90', b'0.01')

    with pytest.raises(ValueError):
        hupijiao_pay_provider.decrypt_callback(headers=FORM_HEADERS, body=tampered)


def test_decrypt_callback_rejects_duplicate_params(configured: HupijiaoPayProvider) -> None:
    """重复参数必须拒绝，避免解析歧义。"""
    body = _signed_form({'appid': APPID, 'trade_order_id': 'PO1', 'status': 'OD'})
    duplicated = body.replace(b'appid=', b'appid=dup&appid=', 1)

    with pytest.raises(ValueError):
        hupijiao_pay_provider.decrypt_callback(headers=FORM_HEADERS, body=duplicated)


def test_normalize_callback_data_maps_payment_success(configured: HupijiaoPayProvider) -> None:
    """支付成功回调归一化为统一字段。"""
    data = hupijiao_pay_provider.normalize_callback_data(
        {'trade_order_id': 'PO1', 'transaction_id': 'TX1', 'total_fee': '19.90', 'status': 'OD'}
    )

    assert data['order_no'] == 'PO1'
    assert data['trade_no'] == 'TX1'
    assert data['trade_state'] == 'SUCCESS'
    assert data['total_fee'] == 1990
    assert 'refund_status' not in data


@pytest.mark.parametrize(
    ['status', 'expected'],
    [['CD', 'SUCCESS'], ['RD', 'PROCESSING'], ['UD', 'FAILED']],
)
def test_normalize_callback_data_maps_refund_status(
    configured: HupijiaoPayProvider, status: str, expected: str
) -> None:
    """退款状态回调映射为统一退款状态。"""
    data = hupijiao_pay_provider.normalize_callback_data(
        {'trade_order_id': 'PO1', 'transaction_id': 'TX1', 'total_fee': '19.90', 'status': status}
    )

    assert data['refund_status'] == expected
    assert 'trade_state' not in data


def test_normalize_callback_data_rejects_unknown_status(configured: HupijiaoPayProvider) -> None:
    """未知状态必须拒绝，避免误判为已支付。"""
    with pytest.raises(ValueError):
        hupijiao_pay_provider.normalize_callback_data(
            {'trade_order_id': 'PO1', 'transaction_id': 'TX1', 'total_fee': '19.90', 'status': 'WP'}
        )


def test_normalize_callback_data_requires_trade_no(configured: HupijiaoPayProvider) -> None:
    """缺少交易号时不得确认支付。"""
    with pytest.raises(ValueError):
        hupijiao_pay_provider.normalize_callback_data(
            {'trade_order_id': 'PO1', 'total_fee': '19.90', 'status': 'OD'}
        )


def test_normalize_query_data_maps_paid_order(configured: HupijiaoPayProvider) -> None:
    """查单成功后归一化金额与交易号。"""
    query = {
        'errcode': 0,
        'errmsg': '',
        'data': {
            'out_trade_order': 'PO1',
            'appid': APPID,
            'transaction_id': 'TX1',
            'total_amount': '19.90',
            'status': 'OD',
        },
    }

    data = hupijiao_pay_provider.normalize_query_data(query, order_no='PO1')

    assert data['trade_state'] == 'SUCCESS'
    assert data['trade_no'] == 'TX1'
    assert data['total_fee'] == 1990


def test_normalize_query_data_maps_unpaid_order(configured: HupijiaoPayProvider) -> None:
    """未支付查单结果不返回金额。"""
    query = {'errcode': 0, 'errmsg': '', 'data': {'out_trade_order': 'PO1', 'appid': APPID, 'status': 'WP'}}

    data = hupijiao_pay_provider.normalize_query_data(query, order_no='PO1')

    assert data['trade_state'] == 'NOTPAY'
    assert 'total_fee' not in data


def test_normalize_query_data_maps_cancelled_order(configured: HupijiaoPayProvider) -> None:
    """查单 CD 表示已取消，与回调 CD（已退款）语义不同。"""
    query = {'errcode': 0, 'errmsg': '', 'data': {'out_trade_order': 'PO1', 'appid': APPID, 'status': 'CD'}}

    data = hupijiao_pay_provider.normalize_query_data(query, order_no='PO1')

    assert data['trade_state'] == 'CLOSED'


def test_normalize_query_data_rejects_order_mismatch(configured: HupijiaoPayProvider) -> None:
    """查单结果订单号必须与请求一致。"""
    query = {'errcode': 0, 'errmsg': '', 'data': {'out_trade_order': 'PO2', 'status': 'OD'}}

    with pytest.raises(errors.GatewayError):
        hupijiao_pay_provider.normalize_query_data(query, order_no='PO1')


def test_normalize_query_data_requires_nested_data(configured: HupijiaoPayProvider) -> None:
    """查单结果缺少订单数据时必须报错。"""
    with pytest.raises(errors.GatewayError):
        hupijiao_pay_provider.normalize_query_data({'errcode': 0, 'errmsg': ''}, order_no='PO1')


def test_refund_requires_full_amount(configured: HupijiaoPayProvider) -> None:
    """虎皮椒仅支持整单全额退款。"""
    with pytest.raises(errors.RequestError):
        asyncio.run(
            hupijiao_pay_provider.refund(
                order_no='PO1',
                refund_no='RF1',
                total_fee=1990,
                refund_fee=1000,
            )
        )


def test_refund_maps_success_and_returns_refund_no(
    configured: HupijiaoPayProvider, monkeypatch: pytest.MonkeyPatch
) -> None:
    """退款成功时返回渠道退款单号与统一状态。"""
    captured: dict = {}
    payload = _signed(
        {
            'errcode': 0,
            'errmsg': '',
            'trade_order_id': 'PO1',
            'refund_fee': '19.90',
            'refund_status': 'CD',
            'out_refund_no': 'R20261009',
        }
    )
    _install_client(monkeypatch, payload, captured)

    result = asyncio.run(
        hupijiao_pay_provider.refund(order_no='PO1', refund_no='RF1', total_fee=1990, refund_fee=1990)
    )

    assert result['status'] == 'SUCCESS'
    assert result['refund_no'] == 'R20261009'
    assert captured['url'] == 'https://api.xunhupay.com/payment/refund.html'
    assert captured['kwargs']['data']['trade_order_id'] == 'PO1'


def test_refund_rejects_amount_mismatch_in_response(
    configured: HupijiaoPayProvider, monkeypatch: pytest.MonkeyPatch
) -> None:
    """退款响应金额与请求不一致时必须拒绝。"""
    captured: dict = {}
    payload = _signed(
        {
            'errcode': 0,
            'errmsg': '',
            'trade_order_id': 'PO1',
            'refund_fee': '0.01',
            'refund_status': 'CD',
        }
    )
    _install_client(monkeypatch, payload, captured)

    with pytest.raises(errors.GatewayError):
        asyncio.run(hupijiao_pay_provider.refund(order_no='PO1', refund_no='RF1', total_fee=1990, refund_fee=1990))


def test_close_is_local_noop(configured: HupijiaoPayProvider) -> None:
    """渠道无远程关单接口，本地关闭不报错。"""
    assert asyncio.run(hupijiao_pay_provider.close(order_no='PO1')) is None
