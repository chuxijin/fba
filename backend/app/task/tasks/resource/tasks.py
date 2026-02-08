#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio
import logging
import random
from datetime import datetime, timedelta
from typing import Dict, Any, List

from backend.app.coulddrive.crud.crud_resource import resource_dao
from backend.app.coulddrive.crud.crud_drive_account import drive_account_dao
from backend.app.coulddrive.service.coulddrive_service import CouldDriveService
from backend.app.coulddrive.schema.file import ShareParam, ListShareInfoParam
from backend.app.coulddrive.schema.enum import DriveType
from backend.app.task.celery import celery_app
from backend.database.db import async_db_session

logger = logging.getLogger(__name__)


@celery_app.task(name='check_and_refresh_expiring_resources')
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
                db=db,
                hours=24,
                expired_type=7,
                include_expired=True
            )

            logger.info(f"资源过期检查完成: 检查{result['checked_resources']}个，刷新{result['refreshed_resources']}个")
            return result

    except Exception as e:
        logger.error(f"资源过期检查失败: {str(e)}")
        return {
            "checked_resources": 0,
            "refreshed_resources": 0,
            "failed_resources": 0,
            "skipped_resources": 0,
            "refresh_details": [],
            "error": str(e)
        }



@celery_app.task(name='refresh_resources_with_update_mode')
async def refresh_resources_with_update_mode() -> Dict[str, Any]:
    """
    刷新临时处理模式为 3（定时更新）的资源分享信息

    :return: 执行结果统计
    """
    summary = {
        "checked_resources": 0,
        "refreshed_resources": 0,
        "failed_resources": 0,
        "skipped_resources": 0,
        "details": [],
    }

    try:
        async with async_db_session() as db:
            resources = await resource_dao.get_resources_by_temp_mode(db, temp_mode=3)
            summary["checked_resources"] = len(resources)

            from backend.app.coulddrive.service.resource_service import resource_service

            for res in resources:
                try:
                    if res.is_deleted or res.status != 1:
                        summary["skipped_resources"] += 1
                        summary["details"].append({
                            "resource_id": res.id,
                            "status": "skipped",
                            "reason": "资源已删除或停用",
                        })
                        continue

                    # 复用服务层的刷新逻辑（等价于 @resource.py 的 refresh_share_info）
                    await resource_service.refresh_share_info(db=db, resource_id=res.id, updated_by=res.updated_by or res.created_by)
                    summary["refreshed_resources"] += 1
                    summary["details"].append({
                        "resource_id": res.id,
                        "status": "success",
                    })

                    # 随机间隔，避免频繁请求
                    wait_time = random.randint(3, 6)
                    await asyncio.sleep(wait_time)

                except Exception as e:
                    logger.error(f"更新模式资源 {res.id} 刷新失败: {str(e)}")
                    summary["failed_resources"] += 1
                    summary["details"].append({
                        "resource_id": res.id,
                        "status": "error",
                        "error": str(e),
                    })
    except Exception as e:
        logger.error(f"刷新更新模式资源时发生错误: {str(e)}")
        summary["error"] = str(e)

    return summary


@celery_app.task(name='refresh_category_mode2_to_permanent')
async def refresh_category_mode2_to_permanent(category_id: int) -> Dict[str, Any]:
    """
    将指定分类下临时处理模式为 2 的资源刷新为永久分享链接

    :param category_id: 分类ID
    :return: 执行结果统计
    """
    try:
        async with async_db_session() as db:
            from backend.app.coulddrive.service.resource_service import resource_service

            return await resource_service.refresh_to_permanent(
                db=db,
                category_id=category_id
            )

    except Exception as e:
        logger.error(f"按分类刷新永久链接失败: {str(e)}")
        return {
            "checked_resources": 0,
            "refreshed_resources": 0,
            "failed_resources": 0,
            "skipped_resources": 0,
            "details": [],
            "error": str(e),
            "category_id": category_id,
        }


@celery_app.task(name='get_expiring_resources')
async def get_expiring_resources(hours: int = 24) -> List[Dict[str, Any]]:
    """
    获取即将过期的资源列表

    :param hours: 过期时间阈值（小时）
    :return: 即将过期的资源列表
    """
    try:
        async with async_db_session() as db:
            current_time = datetime.now()
            expiring_threshold = current_time + timedelta(hours=hours)

            expiring_resources = await resource_dao.get_expiring_resources(
                db,
                current_time=current_time,
                expiring_threshold=expiring_threshold
            )

            result = []
            for resource in expiring_resources:
                result.append({
                    "id": resource.id,
                    "resource_title": resource.title or resource.main_name,
                    "main_name": resource.main_name,
                    "title": resource.title,
                    "url": resource.url,
                    "expired_at": resource.expired_at.isoformat() if resource.expired_at else None,
                    "expired_type": resource.expired_type,
                    "user_id": resource.user_id,
                    "status": resource.status,
                    "is_deleted": resource.is_deleted
                })

            return result

    except Exception as e:
        logger.error(f"获取即将过期的资源列表时发生错误: {str(e)}")
        return []


@celery_app.task(name='cleanup_expired_local_shares')
async def cleanup_expired_local_shares() -> Dict[str, Any]:
    """
    清理本地失效分享
    
    遍历数据库中的网盘账户，获取他们的本地分享列表，
    找出过期的分享并批量取消
    
    :return: 执行结果统计
    """
    try:
        result = await _cleanup_expired_local_shares()
        logger.info(f"本地分享清理完成: 检查{result['checked_accounts']}个账户，清理{result['cleaned_shares']}个分享")
        return result
            
    except Exception as e:
        logger.error(f"本地分享清理失败: {str(e)}")
        return {
            "checked_accounts": 0,
            "cleaned_shares": 0,
            "failed_accounts": 0,
            "cleanup_details": [],
            "error": str(e)
        }


async def _cleanup_expired_local_shares() -> Dict[str, Any]:
    """
    清理本地失效分享的异步实现
    
    :return: 执行结果统计
    """
    result = {
        "checked_accounts": 0,
        "cleaned_shares": 0,
        "failed_accounts": 0,
        "cleanup_details": []
    }
    
    try:
        async with async_db_session() as db:
            # 获取所有有效的网盘账户
            drive_accounts = await drive_account_dao.get_list_with_pagination(db, is_valid=True)
            
            result["checked_accounts"] = len(drive_accounts)

            for account in drive_accounts:
                try:
                    # 跳过无效账户
                    if not account.is_valid or not account.cookies:
                        result["cleanup_details"].append({
                            "account_id": account.id,
                            "account_type": account.type,
                            "status": "skipped",
                            "reason": "账户无效或缺少认证信息"
                        })
                        continue

                    logger.info(f"开始检查账户 {account.id} ({account.type}) 的本地分享")

                    # 直接使用外部模式创建服务实例（避免重复查询数据库）
                    service = CouldDriveService(auth_data=account.cookies, drive_type=DriveType(account.type))

                    # 获取该账户的所有本地分享（自动翻页）
                    all_expired_shares = []
                    page = 1
                    
                    while True:
                        try:
                            from backend.app.coulddrive.schema.file import ListShareInfoParam
                            from backend.app.coulddrive.schema.enum import DriveType
                            
                            # 构建查询参数
                            share_info_params = ListShareInfoParam(
                                drive_type=DriveType(account.type),
                                source_type="local",
                                source_id="",  # local类型时可为空
                                page=page,
                                size=100,  # 每页100条
                                order_field="created_at",
                                order_type="desc"
                            )

                            # 获取分享信息
                            share_info_response = await service.get_share_info(params=share_info_params)
                            
                            # 处理返回的字典格式，提取实际的分享列表
                            if isinstance(share_info_response, dict) and 'list' in share_info_response:
                                share_info_list = share_info_response['list']
                            elif isinstance(share_info_response, list):
                                share_info_list = share_info_response
                            else:
                                share_info_list = []
                            
                            # 如果没有更多数据，退出循环
                            if not share_info_list:
                                break
                            
                            # 筛选过期的分享
                            expired_shares_in_page = []
                            for share_info in share_info_list:
                                # 判断是否过期
                                is_expired = False
                                
                                # 判断逻辑1: expired_type为-1表示过期
                                if share_info.expired_type == -1:
                                    is_expired = True
                                # 判断逻辑2: expired_left为负数表示过期（跳过None值）
                                elif share_info.expired_left is not None and share_info.expired_left < 0:
                                    is_expired = True
                                
                                if is_expired:
                                    expired_shares_in_page.append(share_info.share_id)
                            
                            all_expired_shares.extend(expired_shares_in_page)
                            
                            # 如果本页数据少于100条，说明已经是最后一页
                            if len(share_info_list) < 100:
                                break
                            
                            page += 1
                            
                            # 翻页间隔5-8秒
                            wait_time = random.randint(5, 8)
                            logger.debug(f"账户 {account.id} 翻页间隔，等待{wait_time}秒...")
                            await asyncio.sleep(wait_time)
                            
                        except Exception as e:
                            logger.error(f"获取账户 {account.id} 第{page}页分享信息失败: {str(e)}")
                            break

                    # 如果有过期的分享，分批取消（每批最多40个）
                    if all_expired_shares:
                        try:
                            from backend.app.coulddrive.schema.file import CancelShareParam

                            # 分批处理，每批40个
                            batch_size = 40
                            total_shares = len(all_expired_shares)
                            successful_batches = 0
                            failed_batches = 0
                            total_cleaned = 0

                            logger.info(f"账户 {account.id} 共有 {total_shares} 个过期分享，将分 {(total_shares + batch_size - 1) // batch_size} 批处理")

                            for i in range(0, total_shares, batch_size):
                                batch_shares = all_expired_shares[i:i + batch_size]
                                batch_num = (i // batch_size) + 1

                                try:
                                    cancel_params = CancelShareParam(
                                        drive_type=DriveType(account.type),
                                        shareid_list=batch_shares
                                    )

                                    # 批量取消分享
                                    success = await service.cancel_share(params=cancel_params)

                                    if success:
                                        successful_batches += 1
                                        total_cleaned += len(batch_shares)
                                        logger.info(f"账户 {account.id} 第{batch_num}批成功清理 {len(batch_shares)} 个过期分享")
                                    else:
                                        failed_batches += 1
                                        logger.error(f"账户 {account.id} 第{batch_num}批取消分享失败")

                                    # 批次间隔3-5秒
                                    if i + batch_size < total_shares:
                                        wait_time = random.randint(3, 5)
                                        logger.debug(f"批次间隔���等待{wait_time}秒...")
                                        await asyncio.sleep(wait_time)

                                except Exception as e:
                                    failed_batches += 1
                                    logger.error(f"账户 {account.id} 第{batch_num}批取消分享时发生错误: {str(e)}")

                            # 记录清理结果
                            if total_cleaned > 0:
                                result["cleaned_shares"] += total_cleaned
                                result["cleanup_details"].append({
                                    "account_id": account.id,
                                    "account_type": account.type,
                                    "status": "success",
                                    "cleaned_count": total_cleaned,
                                    "total_count": total_shares,
                                    "successful_batches": successful_batches,
                                    "failed_batches": failed_batches
                                })
                                logger.info(f"账户 {account.id} 成功清理 {total_cleaned}/{total_shares} 个过期分享")

                            if failed_batches > 0 and total_cleaned == 0:
                                result["failed_accounts"] += 1
                                result["cleanup_details"].append({
                                    "account_id": account.id,
                                    "account_type": account.type,
                                    "status": "failed",
                                    "reason": "所有批次取消分享均失败",
                                    "expired_count": total_shares,
                                    "failed_batches": failed_batches
                                })

                        except Exception as e:
                            result["failed_accounts"] += 1
                            result["cleanup_details"].append({
                                "account_id": account.id,
                                "account_type": account.type,
                                "status": "error",
                                "error": str(e),
                                "expired_count": len(all_expired_shares)
                            })
                            logger.error(f"账户 {account.id} 取消分享时发生错误: {str(e)}")
                    
                    else:
                        result["cleanup_details"].append({
                            "account_id": account.id,
                            "account_type": account.type,
                            "status": "no_expired",
                            "reason": "没有找到过期的分享"
                        })
                        logger.info(f"账户 {account.id} 没有过期的分享需要清理")
                    
                    # 每个账号间隔30-40秒
                    wait_time = random.randint(30, 40)
                    logger.debug(f"账户 {account.id} 处理完成，等待{wait_time}秒后处理下一个账户...")
                    await asyncio.sleep(wait_time)
                
                except Exception as e:
                    logger.error(f"处理账户 {account.id} 时发生错误: {str(e)}")
                    result["failed_accounts"] += 1
                    result["cleanup_details"].append({
                        "account_id": account.id,
                        "account_type": account.type,
                        "status": "error",
                        "error": str(e)
                    })
    
    except Exception as e:
        logger.error(f"清理本地分享时发生错误: {str(e)}")
        result["error"] = str(e)
    
    return result 