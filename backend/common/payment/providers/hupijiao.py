import hashlib
import hmac
import math
import re
import secrets
import time

from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import parse_qsl, urlsplit

import httpx

from backend.common.exception import errors
from backend.common.log import log
from backend.common.payment.base import PaymentProvider
from backend.core.conf import settings


class HupijiaoPayProvider(PaymentProvider):
    """虎皮椒 API 1.1 支付渠道，收款方式由配置的 APPID 决定。"""

    @staticmethod
    def _credentials() -> tuple[str, str]:
        """获取渠道凭证，在使用时校验以允许配置留空。"""
        appid = settings.HUPIJIAO_APPID.strip()
        secret = settings.HUPIJIAO_APPSECRET.strip()
        if not appid or not secret:
            raise errors.ServerError(msg='虎皮椒 APPID 或 APPSECRET 未配置')
        return appid, secret

    @staticmethod
    def _sign(data: dict[str, Any], secret: str) -> str:
        """
        按官方规则签名：非空参数按 ASCII 排序，原值拼接后直接追加密钥。

        :param data: 请求、响应或回调参数
        :param secret: 渠道密钥
        :return:
        """
        parts = []
        for key in sorted(data):
            value = data[key]
            if key == 'hash' or value is None or value == '':
                continue
            if isinstance(value, bool) or not isinstance(value, str | int | float):
                raise ValueError('虎皮椒签名参数必须为字符串或数字')
            if isinstance(value, float):
                if not math.isfinite(value):
                    raise ValueError('虎皮椒签名参数包含无效数字')
                value = format(value, '.15g')
            parts.append(f'{key}={value}')
        # MD5 是虎皮椒接口规定的签名算法，参数值不进行 URL 编码。
        return hashlib.md5(('&'.join(parts) + secret).encode('utf-8')).hexdigest()

    @classmethod
    def _verify_signature(cls, data: dict[str, Any], secret: str) -> None:
        """验证完整的平面参数签名，包含渠道新增的扩展字段。"""
        signature = data.get('hash')
        if not isinstance(signature, str) or not re.fullmatch(r'[0-9a-f]{32}', signature):
            raise ValueError('虎皮椒签名缺失或格式错误')
        if not hmac.compare_digest(signature, cls._sign(data, secret)):
            raise ValueError('虎皮椒签名验证失败')

    @staticmethod
    def _https_url(value: str, name: str) -> str:
        """校验由服务端配置的 HTTPS 地址。"""
        parts = urlsplit(value)
        if parts.scheme != 'https' or not parts.hostname or parts.username or parts.password or parts.fragment:
            raise errors.ServerError(msg=f'{name}必须配置为有效的 HTTPS 地址')
        return value

    @staticmethod
    def _validate_order_no(order_no: str) -> None:
        """校验虎皮椒的商户订单号限制。"""
        if not re.fullmatch(r'[A-Za-z0-9_*-]{1,32}', order_no):
            raise errors.RequestError(msg='虎皮椒订单号需为 1～32 位字母、数字、下划线、星号或短横线')

    @staticmethod
    def _amount_to_fen(value: Any) -> int:
        """将渠道金额精确转换为分，拒绝缺失、非正数和小数分。"""
        try:
            amount = Decimal(str(value))
        except InvalidOperation as exc:
            raise ValueError('虎皮椒金额格式错误') from exc
        if not amount.is_finite() or amount <= 0 or amount * 100 != (amount * 100).to_integral_value():
            raise ValueError('虎皮椒金额必须为精确到分的正数')
        return int(amount * 100)

    async def _request(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        """
        调用虎皮椒服务端接口。

        :param endpoint: do / query / refund
        :param payload: 业务参数
        :return:
        """
        appid, secret = self._credentials()
        base_url = self._https_url(settings.HUPIJIAO_API_BASE_URL.rstrip('/'), '虎皮椒支付网关')
        if urlsplit(base_url).query:
            raise errors.ServerError(msg='虎皮椒支付网关不能包含查询参数')
        params = {
            **payload,
            'appid': appid,
            'time': int(time.time()),
            'nonce_str': secrets.token_hex(16),
        }
        params['hash'] = self._sign(params, secret)
        url = f'{base_url}/payment/{endpoint}.html'
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=False) as client:
                if endpoint == 'do':
                    response = await client.post(url, json=params)
                else:
                    response = await client.post(url, data=params)
                response.raise_for_status()
            result = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise errors.GatewayError(msg='虎皮椒接口请求失败，请稍后重试') from exc
        if not isinstance(result, dict):
            raise errors.GatewayError(msg='虎皮椒接口返回格式错误')

        # 官方查询 SDK 返回嵌套 data，未定义该对象的签名序列化规则；
        # 与官方 SDK 一致，查单只接受本方法的 HTTPS 直连响应，保留 TLS 证书校验且禁止重定向。
        # 下单、退款的平面响应以及公网回调必须验签。
        if endpoint != 'query':
            try:
                self._verify_signature(result, secret)
            except ValueError as exc:
                raise errors.GatewayError(msg='虎皮椒响应签名验证失败') from exc
        if result.get('errcode') not in (0, '0'):
            raise errors.GatewayError(msg=f'虎皮椒请求失败: {result.get("errmsg") or "未知错误"}')
        if result.get('appid') is not None and str(result['appid']) != appid:
            raise errors.GatewayError(msg='虎皮椒响应 APPID 不匹配')
        return result

    async def prepay(self, *, order_no: str, total_fee: int, description: str, **kwargs: Any) -> dict[str, Any]:
        """
        预下单，返回二维码图片地址及移动端支付链接。

        :param order_no: 商户订单号
        :param total_fee: 总金额（分）
        :param description: 商品描述
        :return:
        """
        self._validate_order_no(order_no)
        if total_fee <= 0:
            raise errors.RequestError(msg='虎皮椒支付金额必须大于零')
        if kwargs.get('env', 0) != 0:
            raise errors.RequestError(msg='虎皮椒不支持微信虚拟支付沙箱环境')
        notify_url = self._https_url(settings.HUPIJIAO_NOTIFY_URL, '虎皮椒回调地址')
        if len(notify_url.encode('utf-8')) > 128:
            raise errors.ServerError(msg='虎皮椒回调地址不能超过 128 字节')

        # 渠道标题最多 127 字节，过滤其不支持的百分号、补充平面表情和控制字符。
        title = ''.join(char for char in description if char != '%' and 32 <= ord(char) <= 0xFFFF)
        title = title.encode('utf-8').decode('utf-8') if title else '订单支付'
        title = title.encode('utf-8')[:127].decode('utf-8', errors='ignore')
        payload = {
            'version': '1.1',
            'trade_order_id': order_no,
            'total_fee': format(Decimal(total_fee) / 100, '.2f'),
            'title': title,
            'notify_url': notify_url,
        }
        if settings.HUPIJIAO_RETURN_URL:
            return_url = self._https_url(settings.HUPIJIAO_RETURN_URL, '虎皮椒支付完成跳转地址')
            if len(return_url.encode('utf-8')) > 128:
                raise errors.ServerError(msg='虎皮椒支付完成跳转地址不能超过 128 字节')
            payload['return_url'] = return_url
        result = await self._request('do', payload)
        qrcode = result.get('url_qrcode') or ''
        pay_url = result.get('url') or ''
        if not isinstance(qrcode, str) or not isinstance(pay_url, str) or not (qrcode or pay_url):
            raise errors.GatewayError(msg='虎皮椒未返回有效的支付二维码或链接')
        return {'url_qrcode': qrcode, 'url': pay_url, 'expires_in': 300}

    async def query(self, *, order_no: str, **kwargs: Any) -> dict[str, Any]:
        """按商户订单号查询支付状态。"""
        self._validate_order_no(order_no)
        return await self._request('query', {'out_trade_order': order_no})

    def normalize_query_data(self, query_data: dict, *, order_no: str) -> dict[str, Any]:
        """将查单结果转换为统一支付数据，成功状态必须包含有效金额和交易号。"""
        data = query_data.get('data')
        if not isinstance(data, dict):
            raise errors.GatewayError(msg='虎皮椒查询结果缺少订单数据')
        actual_order_no = data.get('out_trade_order') or data.get('trade_order_id') or order_no
        if str(actual_order_no) != order_no:
            raise errors.GatewayError(msg='虎皮椒查询结果订单号不匹配')
        if data.get('appid') is not None and str(data['appid']) != self._credentials()[0]:
            raise errors.GatewayError(msg='虎皮椒查询结果 APPID 不匹配')
        state = {'OD': 'SUCCESS', 'WP': 'NOTPAY', 'CD': 'CLOSED'}.get(data.get('status'), 'UNKNOWN')
        normalized = {
            'order_no': order_no,
            'trade_no': str(data.get('transaction_id') or data.get('open_order_id') or ''),
            'trade_state': state,
            'raw_data': query_data,
        }
        if state == 'SUCCESS':
            if not normalized['trade_no']:
                raise errors.GatewayError(msg='虎皮椒查询结果缺少交易号')
            try:
                normalized['total_fee'] = self._amount_to_fen(data.get('total_amount', data.get('total_fee')))
            except ValueError as exc:
                raise errors.GatewayError(msg='虎皮椒查询结果金额无效') from exc
        return normalized

    def decrypt_callback(self, *, headers: dict, body: bytes) -> dict[str, str]:
        """解析表单回调并验证 APPID 和签名，拒绝重复参数。"""
        appid, secret = self._credentials()
        content_type = headers.get('content-type', headers.get('Content-Type', '')).split(';')[0].strip().lower()
        if content_type != 'application/x-www-form-urlencoded':
            raise ValueError('虎皮椒回调必须为 URL 编码表单')
        pairs = parse_qsl(
            body.decode('utf-8'),
            keep_blank_values=True,
            strict_parsing=True,
            encoding='utf-8',
            errors='strict',
            max_num_fields=64,
        )
        data = dict(pairs)
        if len(data) != len(pairs):
            raise ValueError('虎皮椒回调包含重复参数')
        if data.get('appid') != appid:
            raise ValueError('虎皮椒回调 APPID 不匹配')
        self._verify_signature(data, secret)
        return data

    def normalize_callback_data(self, callback_data: dict, *, event: str = 'payment') -> dict[str, Any]:
        """虎皮椒在同一通知地址推送支付及退款状态。"""
        order_no = callback_data.get('trade_order_id')
        trade_no = callback_data.get('transaction_id') or callback_data.get('open_order_id')
        status = callback_data.get('status')
        if not order_no or not trade_no or status not in ('OD', 'CD', 'RD', 'UD'):
            raise ValueError('虎皮椒回调缺少订单、交易号或有效状态')
        normalized = {
            'order_no': str(order_no),
            'trade_no': str(trade_no),
            'total_fee': self._amount_to_fen(callback_data.get('total_fee')),
            'raw_data': callback_data,
        }
        if event == 'refund' or status != 'OD':
            normalized['refund_status'] = {'CD': 'SUCCESS', 'RD': 'PROCESSING', 'UD': 'FAILED'}.get(status, '')
        else:
            normalized['trade_state'] = 'SUCCESS'
        return normalized

    async def close(self, *, order_no: str, **kwargs: Any) -> None:
        """官方未提供主动关单接口，二维码自然过期；延迟到账仍由统一回调处理。"""
        log.info(f'虎皮椒无远程关单接口，等待二维码过期: order_no={order_no}')

    async def refund(
        self,
        *,
        order_no: str,
        refund_no: str,
        total_fee: int,
        refund_fee: int,
        reason: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        按官方接口整单退款，退款单号由虎皮椒生成。

        :param order_no: 商户订单号
        :param refund_no: 内部退款单号
        :param total_fee: 原订单金额（分）
        :param refund_fee: 退款金额（分）
        :param reason: 退款原因
        :return:
        """
        self._validate_order_no(order_no)
        if total_fee <= 0 or refund_fee != total_fee:
            raise errors.RequestError(msg='虎皮椒仅支持整单全额退款')
        payload = {'trade_order_id': order_no}
        if reason:
            payload['reason'] = reason.encode('utf-8')[:80].decode('utf-8', errors='ignore')
        result = await self._request('refund', payload)
        if result.get('trade_order_id') != order_no:
            raise errors.GatewayError(msg='虎皮椒退款响应订单号不匹配')
        if self._amount_to_fen(result.get('refund_fee')) != refund_fee:
            raise errors.GatewayError(msg='虎皮椒退款响应金额不匹配')
        status = {'CD': 'SUCCESS', 'RD': 'PROCESSING'}.get(result.get('refund_status'))
        if status is None:
            raise errors.GatewayError(msg='虎皮椒退款未成功受理')
        return {
            'status': status,
            'refund_no': str(result.get('out_refund_no') or refund_no),
            'raw_data': result,
        }


hupijiao_pay_provider = HupijiaoPayProvider()
