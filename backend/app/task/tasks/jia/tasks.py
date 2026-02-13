#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from celery import shared_task

from backend.app.jia.service import item_service
from backend.database.db import async_db_session


@shared_task(name='update_jia_item_status')
async def update_jia_item_status() -> dict:
    """更新所有物品的状态，状态变更时推送通知"""
    async with async_db_session.begin() as db:
        return await item_service.update_all_status(db=db)
