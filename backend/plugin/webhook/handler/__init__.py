#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from backend.plugin.webhook.handler.base import EventHandler, HandlerRegistry

# 全局事件处理器注册表
registry = HandlerRegistry()

# 导入示例 Handler 以触发注册
# 新增 Handler 时在此处导入即可
from backend.plugin.webhook.handler import example_handler  # noqa: F401

__all__ = ['EventHandler', 'HandlerRegistry', 'registry']
