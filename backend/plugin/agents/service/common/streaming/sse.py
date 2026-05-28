#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import AsyncGenerator

from backend.plugin.agents.schema import AgentEvent
from backend.plugin.agents.service.common.streaming.bus import EventBus


def format_sse_event(event: AgentEvent) -> str:
    """
    格式化为 SSE 数据帧

    :param event: 事件对象
    :return:
    """
    payload = event.model_dump_json()
    return f'event: {event.event_type}\ndata: {payload}\n\n'


async def sse_stream(bus: EventBus, task_id: int) -> AsyncGenerator[str, None]:
    """
    从 EventBus 订阅事件并格式化为 SSE 数据帧流

    :param bus: 事件总线
    :param task_id: 任务 ID
    :return:
    """
    async for event in bus.subscribe(task_id):
        yield format_sse_event(event)
