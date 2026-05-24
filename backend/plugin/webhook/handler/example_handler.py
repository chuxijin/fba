#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""示例事件处理器 — 展示如何注册和使用 Handler"""

from typing import Any

from backend.common.log import log
from backend.plugin.webhook.handler import registry
from backend.plugin.webhook.handler.base import EventHandler


@registry.register('test.ping')
class TestPingHandler(EventHandler):
    """测试事件处理器"""

    async def handle(self, event_type: str, data: dict[str, Any] | None, subject: str | None) -> None:
        log.info(f'[TestPingHandler] 收到测试事件: data={data}')


@registry.register('com.fba.order.*')
class OrderEventHandler(EventHandler):
    """订单事件处理器 (匹配所有 order 下的事件)"""

    async def handle(self, event_type: str, data: dict[str, Any] | None, subject: str | None) -> None:
        log.info(f'[OrderEventHandler] 订单事件: {event_type} subject={subject}')
        # 在此添加订单相关业务逻辑


@registry.register_func('com.fba.payment.completed')
async def on_payment_completed(*, event_type: str, data: dict[str, Any] | None, subject: str | None) -> None:
    """支付完成事件处理 (函数式写法)"""
    log.info(f'[on_payment_completed] 支付完成: subject={subject} data={data}')
    # 在此添加支付完成后的业务逻辑
