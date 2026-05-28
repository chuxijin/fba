#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio

from collections import defaultdict
from collections.abc import AsyncIterator

from backend.plugin.agents.schema import AgentEvent, EventType


class EventBus:
    """SSE 事件总线"""

    def __init__(self, queue_maxsize: int = 500) -> None:
        self._subscribers: dict[int, set[asyncio.Queue[AgentEvent | None]]] = defaultdict(set)
        self._lock = asyncio.Lock()
        self._queue_maxsize = queue_maxsize

    async def publish(self, event: AgentEvent) -> None:
        """
        向某 task 的所有订阅者推送事件, 慢订阅者会被丢弃事件

        :param event: 推送事件
        :return:
        """
        async with self._lock:
            subscribers = list(self._subscribers.get(event.task_id, set()))
        for queue in subscribers:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                continue

    async def subscribe(self, task_id: int) -> AsyncIterator[AgentEvent]:
        """
        订阅某 task 的事件流, 收到 completed/failed 后退出

        :param task_id: 任务 ID
        :return:
        """
        queue: asyncio.Queue[AgentEvent | None] = asyncio.Queue(maxsize=self._queue_maxsize)
        async with self._lock:
            self._subscribers[task_id].add(queue)
        try:
            while True:
                event = await queue.get()
                if event is None:
                    break
                yield event
                if event.event_type in (EventType.completed, EventType.failed):
                    break
        finally:
            async with self._lock:
                self._subscribers[task_id].discard(queue)
                if not self._subscribers[task_id]:
                    self._subscribers.pop(task_id, None)

    async def close(self, task_id: int) -> None:
        """
        关闭某 task 的所有订阅, 用于任务异常终止或服务停机

        :param task_id: 任务 ID
        :return:
        """
        async with self._lock:
            subscribers = self._subscribers.pop(task_id, set())
        for queue in subscribers:
            try:
                queue.put_nowait(None)
            except asyncio.QueueFull:
                continue


event_bus: EventBus = EventBus()
