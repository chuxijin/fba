#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json

from fastapi.concurrency import run_in_threadpool

from backend.common.log import log
from backend.common.payment.base import PaymentProvider
from backend.core.conf import settings


class WechatPayProvider(PaymentProvider):
    """微信支付 V3 实现"""

    def __init__(self) -> None:
        """初始化微信支付"""
        self._wxpay = None

    def _get_wxpay(self):
        """懒加载 WeChatPay 实例"""
        if self._wxpay is not None:
            return self._wxpay

        from wechatpayv3 import WeChatPay, WeChatPayType

        private_key_path = settings.WECHAT_PAY_PRIVATE_KEY_PATH
        cert_path = settings.WECHAT_PAY_CERT_PATH

        with open(private_key_path, 'r') as f:
            private_key = f.read()

        self._wxpay = WeChatPay(
            wechatpay_type=WeChatPayType.MINIPROG,
            mchid=settings.WECHAT_PAY_MCH_ID,
            private_key=private_key,
            cert_serial_no=settings.WECHAT_PAY_CERT_SERIAL_NO,
            apiv3_key=settings.WECHAT_PAY_API_V3_KEY,
            appid=settings.WX_MINIAPP_APPID,
            cert_dir=cert_path,
            notify_url=settings.WECHAT_PAY_NOTIFY_URL,
        )
        return self._wxpay

    async def prepay(self, *, order_no: str, total_fee: int, description: str, **kwargs) -> dict:
        """
        预下单

        :param order_no: 商户订单号
        :param total_fee: 总金额（单位：分）
        :param description: 商品描述
        :return:
        """
        pay_type = kwargs.get('pay_type', 'jsapi')
        wxpay = self._get_wxpay()

        if pay_type == 'jsapi':
            openid = kwargs.get('openid')
            if not openid:
                raise ValueError('JSAPI 支付必须提供 openid')

            code, result = await run_in_threadpool(
                wxpay.pay,
                description=description,
                out_trade_no=order_no,
                amount={'total': total_fee, 'currency': 'CNY'},
                payer={'openid': openid},
            )
        elif pay_type == 'h5':
            payer_ip = kwargs.get('payer_ip', '127.0.0.1')
            code, result = await run_in_threadpool(
                wxpay.pay,
                description=description,
                out_trade_no=order_no,
                amount={'total': total_fee, 'currency': 'CNY'},
                scene_info={
                    'payer_client_ip': payer_ip,
                    'h5_info': {'type': 'Wap'},
                },
                pay_type='h5',
            )
        else:
            raise ValueError(f'不支持的微信支付类型: {pay_type}')

        if code != 200:
            log.error(f'微信预下单失败: order_no={order_no}, code={code}, result={result}')
            raise RuntimeError(f'微信预下单失败: {result}')

        result_data = json.loads(result) if isinstance(result, str) else result
        log.info(f'微信预下单成功: order_no={order_no}, pay_type={pay_type}')
        return result_data

    async def query(self, *, order_no: str) -> dict:
        """
        查询订单支付状态

        :param order_no: 商户订单号
        :return:
        """
        wxpay = self._get_wxpay()
        code, result = await run_in_threadpool(wxpay.query, out_trade_no=order_no)

        if code != 200:
            log.error(f'微信查询订单失败: order_no={order_no}, code={code}')
            raise RuntimeError(f'微信查询订单失败: {result}')

        return json.loads(result) if isinstance(result, str) else result

    async def close(self, *, order_no: str) -> None:
        """
        关闭订单

        :param order_no: 商户订单号
        :return:
        """
        wxpay = self._get_wxpay()
        code, result = await run_in_threadpool(wxpay.close, out_trade_no=order_no)

        if code not in (200, 204):
            log.error(f'微信关闭订单失败: order_no={order_no}, code={code}')
            raise RuntimeError(f'微信关闭订单失败: {result}')

        log.info(f'微信关闭订单成功: order_no={order_no}')

    async def refund(
        self, *, order_no: str, refund_no: str, total_fee: int, refund_fee: int, reason: str | None = None
    ) -> dict:
        """
        申请退款

        :param order_no: 商户订单号
        :param refund_no: 商户退款单号
        :param total_fee: 原订单金额（单位：分）
        :param refund_fee: 退款金额（单位：分）
        :param reason: 退款原因
        :return:
        """
        wxpay = self._get_wxpay()
        refund_params = {
            'out_trade_no': order_no,
            'out_refund_no': refund_no,
            'amount': {
                'refund': refund_fee,
                'total': total_fee,
                'currency': 'CNY',
            },
        }
        if reason:
            refund_params['reason'] = reason
        if settings.WECHAT_PAY_REFUND_NOTIFY_URL:
            refund_params['notify_url'] = settings.WECHAT_PAY_REFUND_NOTIFY_URL

        code, result = await run_in_threadpool(wxpay.refund, **refund_params)

        if code != 200:
            log.error(f'微信退款失败: order_no={order_no}, code={code}, result={result}')
            raise RuntimeError(f'微信退款失败: {result}')

        result_data = json.loads(result) if isinstance(result, str) else result
        log.info(f'微信退款提交成功: order_no={order_no}, refund_no={refund_no}')
        return result_data

    def decrypt_callback(self, *, headers: dict, body: bytes) -> dict:
        """
        验签并解密回调通知

        :param headers: HTTP 请求头
        :param body: 请求体原始字节
        :return:
        """
        wxpay = self._get_wxpay()
        result = wxpay.callback(headers=headers, body=body.decode('utf-8'))

        if not result:
            raise ValueError('微信回调验签失败')

        return json.loads(result) if isinstance(result, str) else result


wechat_pay_provider: WechatPayProvider = WechatPayProvider()
