#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio
import logging
import random

from datetime import timedelta
from typing import Any, Dict, List

from backend.app.coulddrive.crud.crud_resource import resource_dao
from backend.app.task.celery import celery_app
from backend.database.db import async_db_session
from backend.utils.timezone import timezone

logger = logging.getLogger(__name__)


@celery_app.task(name='resource:check_and_refresh_expiring_resources')
async def check_and_refresh_expiring_resources() -> Dict[str, Any]:
    """
    检查即将过期的资源并重新分享

    扫描yp_resource表中以下两种情况的记录：
    1. 距离过期时间小于24小时的资源
    2. 已经过期的资源

    重新创建分享链接并更新数据库

    :return: 执行结果统计
    """
    try:
        async with async_db_session() as db:
            from backend.app.coulddrive.service.resource_service import resource_service

            result = await resource_service.refresh_expiring_resources(
                db=db, hours=24, expired_type=7, include_expired=True
            )

            logger.info(f'资源过期检查完成: 检查{result["checked_resources"]}个，刷新{result["refreshed_resources"]}个')
            return _compact_resource_result(result)

    except Exception as e:
        logger.error(f'资源过期检查失败: {str(e)}')
        return {
            'checked_resources': 0,
            'refreshed_resources': 0,
            'failed_resources': 0,
            'skipped_resources': 0,
            'refresh_details': [],
            'error': str(e),
        }


@celery_app.task(name='resource:refresh_resources_with_update_mode')
async def refresh_resources_with_update_mode() -> Dict[str, Any]:
    """
    刷新临时处理模式为 3（定时更新）的资源分享信息

    :return: 执行结果统计
    """
    summary = {
        'checked_resources': 0,
        'refreshed_resources': 0,
        'failed_resources': 0,
        'skipped_resources': 0,
        'details': [],
    }

    try:
        async with async_db_session() as db:
            resources = await resource_dao.get_resources_by_temp_mode(db, temp_mode=3)
            summary['checked_resources'] = len(resources)

            from backend.app.coulddrive.service.resource_service import resource_service

            for res in resources:
                try:
                    if res.is_deleted or res.status != 1:
                        summary['skipped_resources'] += 1
                        summary['details'].append({
                            'resource_id': res.id,
                            'status': 'skipped',
                            'reason': '资源已删除或停用',
                        })
                        continue

                    # 复用服务层的刷新逻辑（等价于 @resource.py 的 refresh_share_info）
                    await resource_service.refresh_share_info(
                        db=db, resource_id=res.id, updated_by=res.updated_by or res.created_by
                    )
                    summary['refreshed_resources'] += 1
                    summary['details'].append({
                        'resource_id': res.id,
                        'status': 'success',
                    })

                    # 随机间隔，避免频繁请求
                    wait_time = random.randint(3, 6)
                    await asyncio.sleep(wait_time)

                except Exception as e:
                    logger.error(f'更新模式资源 {res.id} 刷新失败: {str(e)}')
                    summary['failed_resources'] += 1
                    summary['details'].append({
                        'resource_id': res.id,
                        'status': 'error',
                        'error': str(e),
                    })
    except Exception as e:
        logger.error(f'刷新更新模式资源时发生错误: {str(e)}')
        summary['error'] = str(e)

    return _compact_resource_result(summary)


@celery_app.task(name='resource:refresh_category_mode2_to_permanent')
async def refresh_category_mode2_to_permanent(category_id: int) -> Dict[str, Any]:
    """
    将指定分类下临时处理模式为 2 的资源刷新为永久分享链接

    :param category_id: 分类ID
    :return: 执行结果统计
    """
    try:
        async with async_db_session() as db:
            from backend.app.coulddrive.service.resource_service import resource_service

            result = await resource_service.refresh_to_permanent(db=db, category_id=category_id)
            return _compact_resource_result(result)

    except Exception as e:
        logger.error(f'按分类刷新永久链接失败: {str(e)}')
        return {
            'checked_resources': 0,
            'refreshed_resources': 0,
            'failed_resources': 0,
            'skipped_resources': 0,
            'details': [],
            'error': str(e),
            'category_id': category_id,
        }


@celery_app.task(name='resource:get_expiring_resources')
async def get_expiring_resources(hours: int = 24) -> List[Dict[str, Any]]:
    """
    获取即将过期的资源列表

    :param hours: 过期时间阈值（小时）
    :return: 即将过期的资源列表
    """
    try:
        async with async_db_session() as db:
            current_time = timezone.now()
            expiring_threshold = current_time + timedelta(hours=hours)

            expiring_resources = await resource_dao.get_expiring_resources(
                db, current_time=current_time, expiring_threshold=expiring_threshold
            )

            result = []
            for resource in expiring_resources:
                resource_title = resource.remark or resource.title or f'资源 {resource.id}'
                result.append({
                    'id': resource.id,
                    'resource_title': resource_title,
                    'title': resource.title,
                    'remark': resource.remark,
                    'org_name': resource.org_name,
                    'url': resource.url,
                    'expired_at': resource.expired_at.isoformat() if resource.expired_at else None,
                    'expired_type': resource.expired_type,
                    'user_id': resource.user_id,
                    'status': resource.status,
                    'is_deleted': resource.is_deleted,
                })

            return result

    except Exception as e:
        logger.error(f'获取即将过期的资源列表时发生错误: {str(e)}')
        return []


@celery_app.task(name='resource:cleanup_expired_local_shares')
async def cleanup_expired_local_shares() -> Dict[str, Any]:
    """
    清理本地失效分享

    遍历数据库中的网盘账户，获取他们的本地分享列表，
    找出过期的分享并批量取消

    :return: 执行结果统计
    """
    try:
        from backend.app.coulddrive.service.share_cleanup_service import share_cleanup_service

        result = await share_cleanup_service.cleanup_expired_local_shares()
        logger.info(f'本地分享清理完成: 检查{result["checked_accounts"]}个账户，清理{result["cleaned_shares"]}个分享')
        return _compact_resource_result(result)

    except Exception as e:
        logger.error(f'本地分享清理失败: {str(e)}')
        return {
            'checked_accounts': 0,
            'cleaned_shares': 0,
            'failed_accounts': 0,
            'cleanup_details': [],
            'error': str(e),
        }


@celery_app.task(name='resource:sync_resource_hot_scores')
async def sync_resource_hot_scores() -> Dict[str, Any]:
    """
    同步资源热度评分到数据库（离线快照）

    :return: 执行结果统计
    """
    try:
        async with async_db_session() as db:
            from backend.app.coulddrive.service.hot_score_service import hot_score_service

            updated = await hot_score_service.sync_hot_to_db(db)
            logger.info(f'热度快照同步完成，更新 {updated} 个资源')
            return {
                'updated_count': updated,
                'status': 'success',
            }

    except Exception as e:
        logger.error(f'热度快照同步失败: {str(e)}')
        return {
            'updated_count': 0,
            'status': 'error',
            'error': str(e),
        }


def _compact_resource_result(result: Dict[str, Any]) -> Dict[str, Any]:
    """
    压缩资源任务成功返回，避免 Celery 日志输出明细列表。

    :param result: 原始资源任务结果
    :return:
    """
    return {
        key: value
        for key, value in result.items()
        if key not in {'cleanup_details', 'details', 'refresh_details'}
    }
