#!/usr/bin/env python3
from sqlalchemy import inspect

from backend.app.task.celery import celery_app
from backend.database.db import async_engine


@celery_app.task(name='payment:process_group_buy')
async def process_group_buy() -> dict:
    """开关只限制新收款；已存在的团和任务在关停活动后继续补偿。"""
    async with async_engine.connect() as connection:
        installed = await connection.run_sync(lambda conn: inspect(conn).has_table('pay_group_buy_task'))
    if not installed:
        return {'installed': False}
    from backend.app.payment.service.group_buy_worker import group_buy_worker

    before = await group_buy_worker.drain()
    expiry = await group_buy_worker.reconcile_due_teams()
    refunds = await group_buy_worker.reconcile_refunds()
    after = await group_buy_worker.drain()
    return {'processed': before['processed'] + after['processed'], **expiry, **refunds}
