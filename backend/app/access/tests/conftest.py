#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from types import SimpleNamespace
from typing import Any

import pytest

from backend.app.access.constants import GrantMode
from backend.app.access.schema.engine import AccessContext


class FakeSnapshot:
    """轻量级 UserGrantSnapshot 替身, 不依赖 ORM"""

    def __init__(
        self,
        *,
        entitlements: dict[str, int] | None = None,
        direct_codes: list[str] | None = None,
    ) -> None:
        self._entitlements = dict(entitlements or {})
        self._direct = set(direct_codes or [])

    @property
    def subscriptions(self) -> list[Any]:
        """订阅列表(测试中不关心)"""
        return []

    @property
    def direct_grants(self) -> list[Any]:
        """直接授予列表"""
        return [SimpleNamespace(entitlement_code=code) for code in self._direct]

    @property
    def entitlement_codes(self) -> set[str]:
        """订阅持有的权益编码集合"""
        return set(self._entitlements.keys())

    def has_subscription_entitlement(self, code: str) -> bool:
        """
        判断订阅权益

        :param code: 权益编码
        :return:
        """
        return code in self._entitlements

    def get_subscription_value(self, code: str) -> int:
        """
        获取订阅权益数值

        :param code: 权益编码
        :return:
        """
        return int(self._entitlements.get(code, 0))

    def has_direct_grant(self, code: str) -> bool:
        """
        判断直接授予

        :param code: 权益编码
        :return:
        """
        return code in self._direct


def make_rule(
    grant_mode: GrantMode,
    *,
    entitlement_code: str = 'qbank.kaoyan.access',
    rule_id: int = 1,
    priority: int = 0,
    metadata_: dict[str, Any] | None = None,
) -> SimpleNamespace:
    """
    构造测试用 ResourceRule 替身

    :param grant_mode: 授权模式
    :param entitlement_code: 权益编码
    :param rule_id: 规则 ID
    :param priority: 优先级
    :param metadata_: 规则扩展元数据
    :return:
    """
    return SimpleNamespace(
        id=rule_id,
        resource_type='qbank',
        resource_id=42,
        entitlement_code=entitlement_code,
        grant_mode=grant_mode,
        priority=priority,
        metadata_=metadata_ or {},
    )


def make_ctx(
    *,
    user_id: int = 42,
    resource_type: str = 'qbank',
    resource_id: int = 42,
    consume_trial: bool = True,
    scope_key: str = 'global',
    source_ref: str | None = None,
) -> AccessContext:
    """
    构造测试用 AccessContext

    :param user_id: 用户 ID
    :param resource_type: 资源类型
    :param resource_id: 资源 ID
    :param consume_trial: 是否允许扣减试看
    :param scope_key: 配额范围键
    :param source_ref: 扣减来源引用
    :return:
    """
    return AccessContext(
        user_id=user_id,
        resource_type=resource_type,
        resource_id=resource_id,
        consume_trial=consume_trial,
        scope_key=scope_key,
        source_ref=source_ref,
    )


@pytest.fixture
def empty_snapshot() -> FakeSnapshot:
    """空快照: 用户无任何订阅 / 直接授予"""
    return FakeSnapshot()


@pytest.fixture
def vip_kaoyan_snapshot() -> FakeSnapshot:
    """考研 VIP 快照: 持有考研类访问 + 内容查看"""
    return FakeSnapshot(
        entitlements={
            'qbank.kaoyan.access': 1,
            'content.kaoyan.view': 1,
            'qbank.advanced_filter': 1,
        }
    )


@pytest.fixture
def all_in_one_svip_snapshot() -> FakeSnapshot:
    """全家桶 SVIP 快照"""
    return FakeSnapshot(
        entitlements={
            'qbank.kaoyan.access': 1,
            'qbank.kaogong.access': 1,
            'qbank.cet.access': 1,
            'qbank.jiaozi.access': 1,
            'content.kaoyan.view': 1,
            'content.kaogong.view': 1,
            'ai.essay.grade.quota': 50,
        }
    )


@pytest.fixture
def direct_grant_snapshot() -> FakeSnapshot:
    """有直接授予的快照(运营补偿/活动赠送)"""
    return FakeSnapshot(direct_codes=['qbank.kaoyan.access'])
