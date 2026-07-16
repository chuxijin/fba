#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from collections.abc import Callable

from backend.app.mydrive.service.filesystem.spaces import FileSpace

SpaceFactory = Callable[..., FileSpace]


class DriverRegistry:
    """文件空间驱动注册表。"""

    def __init__(self) -> None:
        """初始化驱动注册表。"""
        self._factories: dict[str, SpaceFactory] = {}

    def register(self, provider: str) -> Callable[[SpaceFactory], SpaceFactory]:
        """
        注册文件空间工厂。

        :param provider: 驱动标识
        :return: 注册装饰器
        """
        normalized_provider = provider.strip().lower()
        if not normalized_provider:
            raise ValueError('驱动标识不能为空')

        def decorator(factory: SpaceFactory) -> SpaceFactory:
            if normalized_provider in self._factories:
                raise ValueError(f'驱动已注册: {normalized_provider}')
            self._factories[normalized_provider] = factory
            return factory

        return decorator

    def get(self, provider: str) -> SpaceFactory | None:
        """
        获取文件空间工厂。

        :param provider: 驱动标识
        :return: 文件空间工厂，不存在时返回空
        """
        return self._factories.get(provider.strip().lower())

    def providers(self) -> frozenset[str]:
        """获取已注册的驱动标识。"""
        return frozenset(self._factories)


_driver_registry = DriverRegistry()


def get_driver_registry() -> DriverRegistry:
    """获取全局文件空间驱动注册表。"""
    return _driver_registry
