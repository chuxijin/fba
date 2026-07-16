#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""领域事件相关 Celery 任务"""

import logging

from backend.app.task.celery import celery_app
from backend.app.task.tasks.common import subscriber_registry  # noqa: F401  触发 @subscribe 注册
from backend.common.events import dispatch_locally

logger = logging.getLogger(__name__)


@celery_app.task(name='common:dispatch_domain_event')
async def dispatch_domain_event(event: str, payload: dict) -> dict:
    """
    分发领域事件到所有订阅者

    :param event: 事件名
    :param payload: 事件载荷
    :return:
    """
    result = await dispatch_locally(event, payload or {})
    if result['failures']:
        logger.warning(f'事件分发存在失败 event={event} failures={result["failures"]}')
    else:
        logger.info(f'事件分发完成 event={event} handlers={result["handlers"]} success={result["success"]}')
    return result
