#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections import defaultdict
from typing import Any, Awaitable, Callable

from backend.common.log import log

EventHandler = Callable[..., Awaitable[Any]]

_REGISTRY: dict[str, list[EventHandler]] = defaultdict(list)


def subscribe(event_name: str) -> Callable[[EventHandler], EventHandler]:
    """
    订阅领域事件

    :param event_name: 事件名
    :return:
    """

    def decorator(handler: EventHandler) -> EventHandler:
        _REGISTRY[event_name].append(handler)
        return handler

    return decorator


async def publish(event_name: str, **payload: Any) -> None:
    """
    发布领域事件, 异步分发到所有订阅者

    :param event_name: 事件名
    :return:
    """
    from backend.app.task.celery import celery_app

    celery_app.send_task(
        'dispatch_domain_event',
        kwargs={'event': event_name, 'payload': payload},
    )


async def dispatch_locally(event_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    """
    在当前进程内分发事件给已注册订阅者, 供 Celery 任务调用

    :param event_name: 事件名
    :param payload: 事件载荷
    :return:
    """
    handlers = _REGISTRY.get(event_name, [])
    if not handlers:
        return {'event': event_name, 'handlers': 0, 'success': 0, 'failures': []}

    success = 0
    failures: list[str] = []
    for handler in handlers:
        try:
            await handler(**payload)
            success += 1
        except Exception as exc:
            handler_name = getattr(handler, '__qualname__', repr(handler))
            failures.append(f'{handler_name}: {exc}')
            log.warning(f'事件订阅器执行失败 event={event_name} handler={handler_name} error={exc}')

    return {
        'event': event_name,
        'handlers': len(handlers),
        'success': success,
        'failures': failures,
    }
