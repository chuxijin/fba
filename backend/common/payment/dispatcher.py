#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from backend.common.payment.base import PaymentProvider
from backend.common.payment.providers.wechat import wechat_pay_provider

# 支付方式 → Provider 实例的注册表
_PROVIDER_REGISTRY: dict[str, PaymentProvider] = {
    'jsapi': wechat_pay_provider,
    'h5': wechat_pay_provider,
    # 'alipay': alipay_provider,  # 未来扩展
}


def get_provider(pay_type: str) -> PaymentProvider:
    """
    根据支付方式获取对应的 Provider

    :param pay_type: 支付方式
    :return:
    """
    provider = _PROVIDER_REGISTRY.get(pay_type)
    if not provider:
        raise ValueError(f'不支持的支付方式: {pay_type}')
    return provider


def register_provider(pay_type: str, provider: PaymentProvider) -> None:
    """
    注册自定义支付渠道

    :param pay_type: 支付方式
    :param provider: Provider 实例
    :return:
    """
    _PROVIDER_REGISTRY[pay_type] = provider
