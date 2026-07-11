#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping

from backend.app.access.constants import ReasonCode


@dataclass(frozen=True)
class AccessProfile:
    """资源权益档案"""

    code: str
    resource_type: str
    resource_id: int
    action: str = 'access'
    scope_key: str = 'global'
    deny_messages: Mapping[ReasonCode, str] = field(default_factory=dict)
    default_deny_message: str = '权益校验未通过'
    refund_reason: str = 'resource access refunded'

    def __post_init__(self) -> None:
        object.__setattr__(self, 'deny_messages', MappingProxyType(dict(self.deny_messages)))


class AccessProfileRegistry:
    """资源权益档案注册表"""

    def __init__(self) -> None:
        self._profiles: dict[str, AccessProfile] = {}

    def register(self, profile: AccessProfile) -> AccessProfile:
        """
        注册资源权益档案

        :param profile: 资源权益档案
        :return:
        """
        existing = self._profiles.get(profile.code)
        if existing is not None:
            if existing != profile:
                raise ValueError(f'资源权益档案已存在且配置不一致: {profile.code}')
            return existing

        self._profiles[profile.code] = profile
        return profile

    def get(self, code: str) -> AccessProfile | None:
        """
        获取资源权益档案

        :param code: 档案编码
        :return:
        """
        return self._profiles.get(code)

    def list_profiles(self) -> tuple[AccessProfile, ...]:
        """获取全部已注册档案"""
        return tuple(self._profiles.values())


access_profile_registry: AccessProfileRegistry = AccessProfileRegistry()
