#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import hashlib
import hmac
import json
import time

from typing import Any
from xml.etree.ElementTree import Element, ParseError, fromstring

from backend.common.log import log
from backend.common.payment.base import PaymentProvider
from backend.core.conf import settings
from backend.database.redis import redis_client


class VirtualPayProvider(PaymentProvider):
    """微信小程序虚拟支付实现"""

    API_BASE = 'https://api.weixin.qq.com'
    ACCESS_TOKEN_CACHE_KEY = 'fba:payment:virtual_pay:access_token'

    def __init__(self) -> None:
        self._session = None
        self._access_token: str | None = None
        self._access_token_expire_at: float = 0

    async def _get_session(self) -> Any:
        """懒加载 aiohttp ClientSession"""
        if self._session is not None:
            return self._session

        import aiohttp

        self._session = aiohttp.ClientSession()
        return self._session

    @staticmethod
    def _calc_pay_sig(uri: str, body: str, appkey: str) -> str:
        """
        计算支付签名

        :param uri: 接口路径（如 /xpay/query_order）或客户端固定值 requestVirtualPayment
        :param body: POST body 原文
        :param appkey: 签名密钥
        :return:
        """
        need_sign_msg = f'{uri}&{body}'
        return hmac.new(
            key=appkey.encode('utf-8'),
            msg=need_sign_msg.encode('utf-8'),
            digestmod=hashlib.sha256,
        ).hexdigest()

    @staticmethod
    def _calc_signature(sign_data: str, session_key: str) -> str:
        """
        计算用户态签名

        :param sign_data: 签名数据
        :param session_key: 用户 session_key
        :return:
        """
        return hmac.new(
            key=session_key.encode('utf-8'),
            msg=sign_data.encode('utf-8'),
            digestmod=hashlib.sha256,
        ).hexdigest()

    def _get_appkey(self, env: int = 0) -> str:
        """
        获取对应环境的 appkey

        :param env: 0=现网, 1=沙箱
        :return:
        """
        appkey = settings.VIRTUAL_PAY_SANDBOX_APPKEY if env == 1 else settings.VIRTUAL_PAY_APPKEY
        if not appkey:
            raise ValueError('微信虚拟支付 AppKey 未配置')
        return appkey

    async def _get_access_token(self, *, force_refresh: bool = False) -> str:
        """
        获取小程序接口调用凭证

        :param force_refresh: 是否强制刷新
        :return:
        """
        now = time.time()
        if not force_refresh and self._access_token and now < self._access_token_expire_at:
            return self._access_token

        if not force_refresh:
            try:
                cached_token = await redis_client.get(self.ACCESS_TOKEN_CACHE_KEY)
                if cached_token:
                    self._access_token = str(cached_token)
                    self._access_token_expire_at = now + 300
                    return self._access_token
            except Exception as e:
                log.warning(f'读取微信 access_token 缓存失败: {e}')

        appid = settings.WX_MINIAPP_APPID
        secret = settings.WX_MINIAPP_SECRET
        if not appid or not secret:
            raise ValueError('微信小程序 AppID 或 AppSecret 未配置')

        session = await self._get_session()
        async with session.get(
            f'{self.API_BASE}/cgi-bin/token',
            params={
                'grant_type': 'client_credential',
                'appid': appid,
                'secret': secret,
            },
        ) as resp:
            result = await resp.json()

        access_token = result.get('access_token')
        if not access_token:
            log.error(f'获取微信 access_token 失败: {result}')
            raise RuntimeError(f'获取微信 access_token 失败: {result.get("errmsg", "unknown")}')

        expires_in = int(result.get('expires_in') or 7200)
        ttl = max(60, expires_in - 300)
        self._access_token = str(access_token)
        self._access_token_expire_at = now + ttl

        try:
            await redis_client.set(self.ACCESS_TOKEN_CACHE_KEY, self._access_token, ex=ttl)
        except Exception as e:
            log.warning(f'缓存微信 access_token 失败: {e}')

        return self._access_token

    async def _call_xpay_api(self, uri: str, body: dict[str, Any], env: int = 0) -> dict[str, Any]:
        """
        调用微信虚拟支付服务端 API

        :param uri: 接口路径（如 /xpay/query_order）
        :param body: 请求体字典
        :param env: 环境
        :return:
        """
        session = await self._get_session()
        appkey = self._get_appkey(env)
        body_str = json.dumps(body, separators=(',', ':'))
        pay_sig = self._calc_pay_sig(uri, body_str, appkey)
        access_token = await self._get_access_token()

        async with session.post(
            f'{self.API_BASE}{uri}',
            params={'access_token': access_token, 'pay_sig': pay_sig},
            data=body_str,
            headers={'Content-Type': 'application/json'},
        ) as resp:
            response_text = await resp.text()

        if not response_text.strip():
            return {'errcode': 0}

        result = json.loads(response_text)
        if result.get('errcode') in (40001, 40014, 42001):
            access_token = await self._get_access_token(force_refresh=True)
            async with session.post(
                f'{self.API_BASE}{uri}',
                params={'access_token': access_token, 'pay_sig': pay_sig},
                data=body_str,
                headers={'Content-Type': 'application/json'},
            ) as resp:
                response_text = await resp.text()
            if not response_text.strip():
                return {'errcode': 0}
            result = json.loads(response_text)

        return result

    async def prepay(self, *, order_no: str, total_fee: int, description: str, **kwargs) -> dict[str, Any]:
        """
        虚拟支付预下单（返回客户端签名参数）

        虚拟支付的下单由客户端 wx.requestVirtualPayment 完成，
        服务端只需返回签名参数供客户端使用。

        :param order_no: 商户订单号
        :param total_fee: 总金额（单位：分）
        :param description: 商品描述
        :return: 客户端拉起支付所需参数
        """
        offerid = settings.VIRTUAL_PAY_OFFERID
        openid = kwargs.get('openid')
        session_key = kwargs.get('session_key')
        product_id = str(kwargs.get('product_id') or order_no)
        env = kwargs.get('env', 0)

        if not offerid:
            raise ValueError('微信虚拟支付 OfferID 未配置')
        if not openid:
            raise ValueError('虚拟支付必须提供 openid')
        if not session_key:
            raise ValueError('虚拟支付必须提供 session_key')

        # 构造 signData（客户端 wx.requestVirtualPayment 的参数）
        sign_data_dict = {
            'offerId': offerid,
            'buyQuantity': 1,
            'env': env,
            'currencyType': 'CNY',
            'productId': product_id,
            'goodsPrice': total_fee,
            'outTradeNo': order_no,
            'attach': description,
        }
        sign_data = json.dumps(sign_data_dict, separators=(',', ':'))

        appkey = self._get_appkey(env)

        # paySig: 客户端 API uri 固定为 requestVirtualPayment
        pay_sig = self._calc_pay_sig('requestVirtualPayment', sign_data, appkey)

        # signature: 用户态签名
        signature = self._calc_signature(sign_data, session_key)

        log.info(
            '虚拟支付预下单成功: '
            f'order_no={order_no}, product_id={product_id}, env={env}, total_fee={total_fee}, '
            f'offerid={offerid}, appkey_len={len(appkey)}, appkey_tail={appkey[-4:]}'
        )
        return {
            'mode': 'short_series_goods',
            'offerId': offerid,
            'buyQuantity': 1,
            'env': env,
            'currencyType': 'CNY',
            'productId': product_id,
            'goodsPrice': total_fee,
            'outTradeNo': order_no,
            'attach': description,
            'paySig': pay_sig,
            'signature': signature,
            'signData': sign_data,
        }

    async def query(self, *, order_no: str, **kwargs) -> dict[str, Any]:
        """
        查询虚拟支付订单状态

        :param order_no: 商户订单号
        :return:
        """
        env = int(kwargs.get('env') or 0)
        openid = kwargs.get('openid')
        if not openid:
            raise ValueError('虚拟支付查询必须提供 openid')

        body = {
            'openid': openid,
            'env': env,
            'order_id': order_no,
        }
        result = await self._call_xpay_api('/xpay/query_order', body, env=env)

        if result.get('errcode', 0) != 0:
            log.error(f'虚拟支付查询失败: order_no={order_no}, result={result}')
            raise RuntimeError(f'虚拟支付查询失败: {result.get("errmsg", "unknown")}')

        log.info(f'虚拟支付查询成功: order_no={order_no}')
        return result

    def normalize_query_data(self, query_data: dict, *, order_no: str) -> dict[str, Any]:
        """
        将虚拟支付查询结果归一化为标准格式

        :param query_data: 查询结果
        :param order_no: 业务订单号
        :return:
        """
        order = query_data.get('order') or {}
        if not isinstance(order, dict):
            order = {}

        status = order.get('status')
        try:
            status_value = int(status)
        except (TypeError, ValueError):
            status_value = -1
        trade_state = 'SUCCESS' if status_value in (2, 3, 4) else str(status or '')
        return {
            'order_no': order.get('order_id') or order_no,
            'trade_no': order.get('wxpay_order_id') or order.get('channel_order_id') or order.get('wx_order_id') or '',
            'trade_state': trade_state,
            'paid_time': order.get('paid_time') or None,
            'raw_data': query_data,
        }

    async def close(self, *, order_no: str, **kwargs) -> None:
        """
        关闭虚拟支付订单

        虚拟支付无独立关闭接口，通过查询确认订单状态即可。

        :param order_no: 商户订单号
        :return:
        """
        log.info(f'虚拟支付关闭（跳过）: order_no={order_no}')

    async def refund(
        self,
        *,
        order_no: str,
        refund_no: str,
        total_fee: int,
        refund_fee: int,
        reason: str | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """
        虚拟支付退款

        :param order_no: 商户订单号
        :param refund_no: 商户退款单号
        :param total_fee: 原订单金额（单位：分）
        :param refund_fee: 退款金额（单位：分）
        :param reason: 退款原因
        :return:
        """
        env = int(kwargs.get('env') or 0)
        body = {
            'app_id': settings.WX_MINIAPP_APPID,
            'out_trade_no': order_no,
            'out_refund_no': refund_no,
            'total_fee': total_fee,
            'refund_fee': refund_fee,
            'env': env,
        }
        if reason:
            body['refund_reason'] = reason

        result = await self._call_xpay_api('/xpay/refund_order', body, env=env)

        if result.get('errcode', 0) != 0:
            log.error(f'虚拟支付退款失败: order_no={order_no}, result={result}')
            raise RuntimeError(f'虚拟支付退款失败: {result.get("errmsg", "unknown")}')

        log.info(f'虚拟支付退款提交成功: order_no={order_no}, refund_no={refund_no}')
        return result

    @staticmethod
    def _parse_xml_element(element: Element) -> dict[str, Any]:
        """
        递归解析 XML 元素（处理嵌套结构）

        :param element: XML 元素
        :return:
        """
        data = {}
        for child in element:
            if len(child):
                data[child.tag] = VirtualPayProvider._parse_xml_element(child)
            else:
                data[child.tag] = child.text
        return data

    def decrypt_callback(self, *, headers: dict, body: bytes) -> dict[str, Any]:
        """
        解密虚拟支付回调通知

        虚拟支付回调为 XML 格式，无需验签解密（通过 HTTPS 保证安全）。

        :param headers: HTTP 请求头
        :param body: 请求体原始字节
        :return:
        """
        body_text = body.decode('utf-8')
        if body_text.lstrip().startswith('{'):
            data = json.loads(body_text)
            if not isinstance(data, dict):
                raise ValueError('虚拟支付 JSON 回调格式错误')
            return data

        try:
            root = fromstring(body_text)
            return self._parse_xml_element(root)
        except ParseError as e:
            raise ValueError(f'虚拟支付回调 XML 解析失败: {e}')

    def normalize_callback_data(self, callback_data: dict, *, event: str = 'payment') -> dict[str, Any]:
        """
        将虚拟支付回调数据归一化为标准格式

        :param callback_data: 原始 XML 解析数据
        :param event: 事件类型 (payment / refund)
        :return:
        """
        if event == 'refund':
            return {
                'order_no': callback_data.get('OutTradeNo') or callback_data.get('MchOrderId', ''),
                'trade_no': callback_data.get('WxpayRefundTransactionId', ''),
                'refund_status': 'SUCCESS' if callback_data.get('RetCode') == '0' else 'FAIL',
            }
        # payment
        wechat_pay_info = callback_data.get('WeChatPayInfo', {})
        trade_no = wechat_pay_info.get('TransactionId', '') if isinstance(wechat_pay_info, dict) else ''
        paid_time = wechat_pay_info.get('PaidTime') if isinstance(wechat_pay_info, dict) else None
        return {
            'order_no': callback_data.get('OutTradeNo', ''),
            'trade_no': trade_no,
            'trade_state': 'SUCCESS',
            'paid_time': paid_time,
        }

    async def notify_provide_goods(self, *, order_no: str, env: int = 0) -> dict[str, Any]:
        """
        通知已发货（现金单）

        :param order_no: 商户订单号
        :param env: 环境
        :return:
        """
        body = {
            'order_id': order_no,
            'env': env,
        }
        result = await self._call_xpay_api('/xpay/notify_provide_goods', body, env=env)

        if result.get('errcode', 0) != 0:
            log.error(f'虚拟支付发货通知失败: order_no={order_no}, result={result}')
            raise RuntimeError(f'虚拟支付发货通知失败: {result.get("errmsg", "unknown")}')

        log.info(f'虚拟支付发货通知成功: order_no={order_no}')
        return result


virtual_pay_provider: VirtualPayProvider = VirtualPayProvider()
