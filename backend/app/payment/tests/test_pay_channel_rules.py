#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from decimal import Decimal
from types import SimpleNamespace

import pytest

from pydantic import ValidationError

from backend.app.payment.schema.pay import SubscriptionPrepayParam
from backend.app.payment.service.pay_service import PayService
from backend.common.exception import errors
from backend.common.payment.providers.hupijiao import hupijiao_pay_provider


def _txn(**overrides) -> SimpleNamespace:
    """构造支付记录替身。"""
    base = {
        'id': 1,
        'order_no': 'PO20261009001',
        'pay_type': 'hupijiao',
        'amount': Decimal('19.90'),
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_yuan_to_fen_converts_exact_amount() -> None:
    """金额精确转换为分。"""
    assert PayService._yuan_to_fen(Decimal('19.90')) == 1990
    assert PayService._yuan_to_fen(Decimal('0.01')) == 1


@pytest.mark.parametrize('amount', [Decimal('19.905'), Decimal(0), Decimal(-1)])
def test_yuan_to_fen_rejects_invalid_amount(amount: Decimal) -> None:
    """非法金额必须拒绝，避免精度丢失后按错误金额收款。"""
    with pytest.raises(errors.RequestError):
        PayService._yuan_to_fen(amount)


def test_validate_channel_result_accepts_matching_channel() -> None:
    """渠道、订单号与金额一致时通过校验。"""
    PayService._validate_channel_result(
        _txn(),
        {'order_no': 'PO20261009001', 'total_fee': 1990},
        hupijiao_pay_provider,
    )


def test_validate_channel_result_rejects_other_channel() -> None:
    """其他渠道的通知不得更新本订单。"""
    with pytest.raises(errors.RequestError):
        PayService._validate_channel_result(
            _txn(pay_type='virtual'),
            {'order_no': 'PO20261009001', 'total_fee': 1990},
            hupijiao_pay_provider,
        )


def test_validate_channel_result_rejects_order_no_mismatch() -> None:
    """订单号不一致必须拒绝。"""
    with pytest.raises(errors.RequestError):
        PayService._validate_channel_result(
            _txn(),
            {'order_no': 'PO20261009002', 'total_fee': 1990},
            hupijiao_pay_provider,
        )


def test_validate_channel_result_rejects_amount_mismatch() -> None:
    """金额不一致必须拒绝。"""
    with pytest.raises(errors.RequestError):
        PayService._validate_channel_result(
            _txn(),
            {'order_no': 'PO20261009001', 'total_fee': 1},
            hupijiao_pay_provider,
        )


def test_validate_channel_result_requires_amount_for_hupijiao() -> None:
    """虎皮椒支付结果必须携带有效金额。"""
    with pytest.raises(errors.RequestError):
        PayService._validate_channel_result(
            _txn(),
            {'order_no': 'PO20261009001'},
            hupijiao_pay_provider,
        )


def test_validate_channel_result_rejects_boolean_amount() -> None:
    """布尔值不是有效金额。"""
    with pytest.raises(errors.RequestError):
        PayService._validate_channel_result(
            _txn(),
            {'order_no': 'PO20261009001', 'total_fee': True},
            hupijiao_pay_provider,
        )


def test_subscription_param_allows_hupijiao_without_wx_code() -> None:
    """虎皮椒下单不依赖微信小程序登录 code。"""
    obj = SubscriptionPrepayParam(template_code='vip_month', pay_type='hupijiao')

    assert obj.wx_code is None
    assert obj.env == 0


def test_subscription_param_requires_wx_code_for_virtual() -> None:
    """虚拟支付必须提供微信登录 code。"""
    with pytest.raises(ValidationError):
        SubscriptionPrepayParam(template_code='vip_month', pay_type='virtual')


def test_subscription_param_rejects_sandbox_env_for_hupijiao() -> None:
    """虎皮椒不支持沙箱环境。"""
    with pytest.raises(ValidationError):
        SubscriptionPrepayParam(template_code='vip_month', pay_type='hupijiao', env=1)


def test_subscription_param_defaults_to_virtual() -> None:
    """默认支付方式保持原虚拟支付行为。"""
    obj = SubscriptionPrepayParam(template_code='vip_month', wx_code='wx-code')

    assert obj.pay_type == 'virtual'
