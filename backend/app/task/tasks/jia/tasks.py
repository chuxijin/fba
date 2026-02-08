#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import logging
from typing import Any

from celery import shared_task
from sqlalchemy import select

from backend.app.jia.model import JiaItem
from backend.database.db import async_db_session

logger = logging.getLogger(__name__)


@shared_task(name='update_jia_item_status')
async def update_jia_item_status() -> dict[str, Any]:
    """
    更新所有物品的状态

    根据数量、消耗周期、保质期重新计算每个物品的状态
    """
    try:
        async with async_db_session() as db:
            # 查询所有物品
            stmt = select(JiaItem)
            result = await db.execute(stmt)
            items = result.scalars().all()

            updated_count = 0
            status_stats = {
                '充足': 0,
                '待补货': 0,
                '即将用完': 0,
                '缺失': 0,
                '即将过期': 0,
                '已过期': 0,
            }

            for item in items:
                old_status = item.status
                new_status = item.calculate_status()

                if old_status != new_status:
                    item.status = new_status
                    updated_count += 1
                    logger.info(f'物品 [{item.name}] 状态变更: {old_status} -> {new_status}')

                # 统计状态
                if new_status in status_stats:
                    status_stats[new_status] += 1

            await db.commit()

            logger.info(f'物品状态更新完成: 共 {len(items)} 件, 变更 {updated_count} 件')

            return {
                'success': True,
                'total_count': len(items),
                'updated_count': updated_count,
                'status_stats': status_stats,
                'message': f'成功更新 {updated_count} 件物品状态',
            }

    except Exception as e:
        logger.error(f'更新物品状态失败: {e}')
        return {
            'success': False,
            'error': str(e),
            'message': f'更新失败: {e}',
        }
