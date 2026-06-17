#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import hashlib
import hmac
import json


from backend.common.log import log
from backend.common.payment.base import PaymentProvider
from backend.core.conf import settings


class VirtualPayProvider(PaymentProvider):
    """微信小程序虚拟支付实现"""

    API_BASE = 'https://api.weixin.qq.com'

    def __init__(self) -> None:
        self._session = None

    async def _get_session(self):
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
        if env == 1:
            return settings.VIRTUAL_PAY_SANDBOX_APPKEY
        return settings.VIRTUAL_PAY_APPKEY

    async def _call_xpay_api(self, uri: str, body: dict, env: int = 0) -> dict:
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

        url = f'{self.API_BASE}{uri}?pay_sig={pay_sig}'

        async with session.post(url, data=body_str, headers={'Content-Type': 'application/json'}) as resp:
            result = await resp.json()
            return result

    async def prepay(self, *, order_no: str, total_fee: int, description: str, **kwargs) -> dict:
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
        env = kwargs.get('env', 0)

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
            'productId': order_no,
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

        log.info(f'虚拟支付预下单成功: order_no={order_no}')
        return {
            'offerId': offerid,
            'buyQuantity': 1,
            'env': env,
            'currencyType': 'CNY',
            'productId': order_no,
            'goodsPrice': total_fee,
            'outTradeNo': order_no,
            'attach': description,
            'paySig': pay_sig,
            'signature': signature,
            'signData': sign_data,
        }

    async def query(self, *, order_no: str) -> dict:
        """
        查询虚拟支付订单状态

        :param order_no: 商户订单号
        :return:
        """
        body = {
            'app_id': settings.WX_MINIAPP_APPID,
            'out_trade_no': order_no,
        }
        result = await self._call_xpay_api('/xpay/query_order', body)

        if result.get('errcode', 0) != 0:
            log.error(f'虚拟支付查询失败: order_no={order_no}, result={result}')
            raise RuntimeError(f'虚拟支付查询失败: {result.get("errmsg", "unknown")}')

        log.info(f'虚拟支付查询成功: order_no={order_no}')
        return result

    async def close(self, *, order_no: str) -> None:
        """
        关闭虚拟支付订单

        虚拟支付无独立关闭接口，通过查询确认订单状态即可。

        :param order_no: 商户订单号
        :return:
        """
        log.info(f'虚拟支付关闭（跳过）: order_no={order_no}')

    async def refund(
        self, *, order_no: str, refund_no: str, total_fee: int, refund_fee: int, reason: str | None = None
    ) -> dict:
        """
        虚拟支付退款

        :param order_no: 商户订单号
        :param refund_no: 商户退款单号
        :param total_fee: 原订单金额（单位：分）
        :param refund_fee: 退款金额（单位：分）
        :param reason: 退款原因
        :return:
        """
        body = {
            'app_id': settings.WX_MINIAPP_APPID,
            'out_trade_no': order_no,
            'out_refund_no': refund_no,
            'total_fee': total_fee,
            'refund_fee': refund_fee,
        }
        if reason:
            body['refund_reason'] = reason

        result = await self._call_xpay_api('/xpay/refund_order', body)

        if result.get('errcode', 0) != 0:
            log.error(f'虚拟支付退款失败: order_no={order_no}, result={result}')
            raise RuntimeError(f'虚拟支付退款失败: {result.get("errmsg", "unknown")}')

        log.info(f'虚拟支付退款提交成功: order_no={order_no}, refund_no={refund_no}')
        return result

    @staticmethod
    def _parse_xml_element(element) -> dict:
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

    def decrypt_callback(self, *, headers: dict, body: bytes) -> dict:
        """
        解密虚拟支付回调通知

        虚拟支付回调为 XML 格式，无需验签解密（通过 HTTPS 保证安全）。

        :param headers: HTTP 请求头
        :param body: 请求体原始字节
        :return:
        """
        import xml.etree.ElementTree as ET

        try:
            root = ET.fromstring(body.decode('utf-8'))
            return self._parse_xml_element(root)
        except ET.ParseError as e:
            raise ValueError(f'虚拟支付回调 XML 解析失败: {e}')

    def normalize_callback_data(self, callback_data: dict, *, event: str = 'payment') -> dict:
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
        if isinstance(wechat_pay_info, dict):
            trade_no = wechat_pay_info.get('TransactionId', '')
        else:
            trade_no = ''
        return {
            'order_no': callback_data.get('OutTradeNo', ''),
            'trade_no': trade_no,
            'trade_state': 'SUCCESS',
        }

    async def notify_provide_goods(self, *, order_no: str, env: int = 0) -> dict:
        """
        通知已发货（现金单）

        :param order_no: 商户订单号
        :param env: 环境
        :return:
        """
        body = {
            'app_id': settings.WX_MINIAPP_APPID,
            'out_trade_no': order_no,
        }
        result = await self._call_xpay_api('/xpay/notify_provide_goods', body, env=env)

        if result.get('errcode', 0) != 0:
            log.error(f'虚拟支付发货通知失败: order_no={order_no}, result={result}')
            raise RuntimeError(f'虚拟支付发货通知失败: {result.get("errmsg", "unknown")}')

        log.info(f'虚拟支付发货通知成功: order_no={order_no}')
        return result


virtual_pay_provider: VirtualPayProvider = VirtualPayProvider()
