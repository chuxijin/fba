#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import logging

from typing import Any

from backend.app.payment.service.pay_service import pay_service
from backend.app.task.celery import celery_app
from backend.database.db import async_db_session

logger = logging.getLogger(__name__)


@celery_app.task(name='close_timeout_pending_pay_orders')
async def close_timeout_pending_pay_orders() -> dict[str, Any]:
    """批量关闭超时未支付的业务订单"""
    async with async_db_session() as db:
        summary = await pay_service.close_timeout_pending_orders(db=db)

    logger.info(
        '超时支付订单关闭完成: '
        f'scanned={summary["scanned_count"]} '
        f'closed={summary["closed_count"]} '
        f'skipped={summary["skipped_count"]} '
        f'failed={summary["failed_count"]}'
    )
    return summary
