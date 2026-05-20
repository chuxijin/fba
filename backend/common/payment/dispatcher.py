#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from backend.common.payment.base import PaymentProvider
from backend.common.payment.providers.wechat import wechat_pay_provider

# 支付方式 → Provider 实例的注册表
_PROVIDER_REGISTRY: dict[str, PaymentProvider] = {
    'jsapi': wechat_pay_provider,
    'h5': wechat_pay_provider,
}


def _ensure_virtual_provider() -> None:
    """延迟注册虚拟支付 Provider（避免未配置时导入报错）"""
    if 'virtual' not in _PROVIDER_REGISTRY:
        from backend.common.payment.providers.virtual import virtual_pay_provider
        _PROVIDER_REGISTRY['virtual'] = virtual_pay_provider


_ensure_virtual_provider()


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


def decrypt_callback(headers: dict, body: bytes) -> tuple[dict, PaymentProvider]:
    """
    解密支付回调通知（遍历去重 Provider 实例尝试解密）

    :param headers: HTTP 请求头
    :param body: 请求体原始字节
    :return: (回调数据, 使用的 Provider)
    """
    seen: set[int] = set()
    errors_list: list[str] = []
    for provider in _PROVIDER_REGISTRY.values():
        provider_id = id(provider)
        if provider_id in seen:
            continue
        seen.add(provider_id)
        try:
            data = provider.decrypt_callback(headers=headers, body=body)
            return data, provider
        except Exception as e:
            errors_list.append(f'{type(provider).__name__}: {e}')
    raise ValueError(f'所有支付渠道回调解密失败: {"; ".join(errors_list)}')
