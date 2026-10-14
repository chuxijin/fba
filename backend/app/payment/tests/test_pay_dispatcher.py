#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import pytest

from backend.common.payment import dispatcher as dispatcher_module
from backend.common.payment import get_provider
from backend.common.payment.providers.hupijiao import hupijiao_pay_provider
from backend.common.payment.providers.wechat import wechat_pay_provider


class _FakeProvider:
    """仅接受固定报文的测试渠道。"""

    def __init__(self, marker: bytes) -> None:
        self._marker = marker
        self.calls = 0

    def decrypt_callback(self, *, headers: dict, body: bytes) -> dict:
        self.calls += 1
        if body != self._marker:
            raise ValueError('报文不属于该渠道')
        return {'channel': 'fake'}


def test_hupijiao_provider_is_registered() -> None:
    """虎皮椒渠道应注册到调度表。"""
    assert get_provider('hupijiao') is hupijiao_pay_provider


def test_wechat_providers_remain_registered() -> None:
    """原有微信渠道注册不受新增渠道影响。"""
    assert get_provider('jsapi') is wechat_pay_provider
    assert get_provider('h5') is wechat_pay_provider


def test_unknown_pay_type_raises() -> None:
    """未知支付方式应报错。"""
    with pytest.raises(ValueError):
        get_provider('not-exist')


def test_decrypt_callback_without_pay_type_keeps_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """未指定渠道时保留原有的遍历匹配行为。"""
    fake = _FakeProvider(b'fake-body')
    monkeypatch.setattr(dispatcher_module, '_PROVIDER_REGISTRY', {'hupijiao': hupijiao_pay_provider, 'fake': fake})

    data, provider = dispatcher_module.decrypt_callback({}, b'fake-body')

    assert provider is fake
    assert data == {'channel': 'fake'}


def test_decrypt_callback_with_pay_type_never_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    """指定渠道时不得回退到其他渠道验签。"""
    fake = _FakeProvider(b'fake-body')
    monkeypatch.setattr(dispatcher_module, '_PROVIDER_REGISTRY', {'hupijiao': hupijiao_pay_provider, 'fake': fake})

    with pytest.raises(Exception) as exc_info:
        dispatcher_module.decrypt_callback({}, b'fake-body', pay_type='hupijiao')

    assert fake.calls == 0
    assert '报文不属于该渠道' not in str(exc_info.value)


def test_decrypt_callback_with_pay_type_reports_unknown_channel(monkeypatch: pytest.MonkeyPatch) -> None:
    """指定未知渠道时应直接报错。"""
    monkeypatch.setattr(dispatcher_module, '_PROVIDER_REGISTRY', {'fake': _FakeProvider(b'fake-body')})

    with pytest.raises(ValueError):
        dispatcher_module.decrypt_callback({}, b'fake-body', pay_type='hupijiao')
