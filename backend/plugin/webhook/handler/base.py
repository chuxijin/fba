#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from abc import ABC, abstractmethod
from typing import Any

from backend.common.log import log


class EventHandler(ABC):
    """事件处理器基类"""

    @abstractmethod
    async def handle(self, event_type: str, data: dict[str, Any] | None, subject: str | None) -> None:
        """
        处理事件

        :param event_type: CloudEvents type
        :param data: CloudEvents data
        :param subject: CloudEvents subject
        """
        ...


class HandlerRegistry:
    """事件处理器注册表"""

    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = {}

    def register(self, event_type: str):
        """
        注册事件处理器装饰器

        :param event_type: 事件类型 (支持精确匹配和通配符)
        :return:
        """

        def decorator(handler_cls: type[EventHandler]) -> type[EventHandler]:
            instance = handler_cls()
            self._handlers.setdefault(event_type, []).append(instance)
            log.info(f'事件处理器已注册: {event_type} → {handler_cls.__name__}')
            return handler_cls

        return decorator

    def register_func(self, event_type: str):
        """
        注册函数式事件处理器装饰器

        :param event_type: 事件类型
        :return:
        """

        def decorator(func):
            wrapper = _FunctionHandler(func)
            self._handlers.setdefault(event_type, []).append(wrapper)
            log.info(f'事件处理器已注册: {event_type} → {func.__qualname__}')
            return func

        return decorator

    async def dispatch(self, event_type: str, data: dict[str, Any] | None, subject: str | None) -> list[str]:
        """
        分发事件到匹配的处理器

        支持精确匹配 + 通配符匹配:
        - "com.fba.order.created" 精确匹配
        - "com.fba.order.*" 匹配所有 order 事件
        - "*" 全局匹配

        :param event_type: 事件类型
        :param data: 事件数据
        :param subject: 关联资源标识
        :return: 已执行的处理器列表
        """
        executed: list[str] = []

        for pattern, handlers in self._handlers.items():
            if self._match(pattern, event_type):
                for handler in handlers:
                    try:
                        await handler.handle(event_type, data, subject)
                        executed.append(type(handler).__qualname__)
                    except Exception as e:
                        log.error(f'事件处理器执行失败: {type(handler).__qualname__} event={event_type} error={e}')

        return executed

    @staticmethod
    def _match(pattern: str, event_type: str) -> bool:
        """
        通配符匹配

        :param pattern: 订阅模式
        :param event_type: 实际事件类型
        :return:
        """
        if pattern == event_type:
            return True
        if pattern.endswith('.*'):
            prefix = pattern[:-2]
            return event_type.startswith(prefix + '.')
        if pattern == '*':
            return True
        return False


class _FunctionHandler(EventHandler):
    """函数式处理器包装器"""

    def __init__(self, func) -> None:
        self._func = func

    async def handle(self, event_type: str, data: dict[str, Any] | None, subject: str | None) -> None:
        await self._func(event_type=event_type, data=data, subject=subject)
