#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio
import logging
import random
from datetime import datetime, timedelta
from typing import Dict, Any, List

from backend.app.coulddrive.crud.crud_resource import resource_dao
from backend.app.coulddrive.crud.crud_drive_account import drive_account_dao
from backend.app.coulddrive.service.yp_service import get_drive_manager
from backend.app.coulddrive.schema.file import ShareParam, ListShareInfoParam
from backend.app.coulddrive.schema.enum import DriveType
from backend.app.task.celery import celery_app
from backend.database.db import async_db_session

logger = logging.getLogger(__name__)


@celery_app.task(name='check_and_refresh_expiring_resources')
async def check_and_refresh_expiring_resources() -> Dict[str, Any]:
    """
    检查即将过期的资源并重新分享
    
    扫描yp_resource表中距离过期时间小于24小时的记录，
    重新创建分享链接并更新数据库
    
    :return: 执行结果统计
    """
    try:
        result = await _check_and_refresh_expiring_resources()
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


async def _check_and_refresh_expiring_resources() -> Dict[str, Any]:
    """
    检查即将过期的资源并重新分享的异步实现
    
    :return: 执行结果统计
    """
    result = {
        "checked_resources": 0,
        "refreshed_resources": 0,
        "failed_resources": 0,
        "skipped_resources": 0,
        "refresh_details": []
    }
    
    try:
        async with async_db_session() as db:
            # 获取即将过期的资源（24小时内过期）
            current_time = datetime.now()
            expiring_threshold = current_time + timedelta(hours=24)
            
            # 查询即将过期的资源
            expiring_resources = await resource_dao.get_expiring_resources(
                db, 
                current_time=current_time,
                expiring_threshold=expiring_threshold
            )
            
            result["checked_resources"] = len(expiring_resources)
            
            drive_manager = get_drive_manager()
            
            for resource in expiring_resources:
                try:
                    # 跳过已删除或停用的资源
                    if resource.is_deleted or resource.status != 1:
                        result["skipped_resources"] += 1
                        result["refresh_details"].append({
                            "resource_id": resource.id,
                            "status": "skipped",
                            "reason": "资源已删除或停用"
                        })
                        continue
                    
                    # 跳过永久分享的资源（expired_type = 0）
                    if resource.expired_type == 0:
                        result["skipped_resources"] += 1
                        result["refresh_details"].append({
                            "resource_id": resource.id,
                            "status": "skipped",
                            "reason": "永久分享无需刷新"
                        })
                        continue
                    
                    # 获取用户网盘账户信息
                    drive_account = await drive_account_dao.get(db, resource.user_id)
                    if not drive_account or not drive_account.is_valid:
                        result["failed_resources"] += 1
                        result["refresh_details"].append({
                            "resource_id": resource.id,
                            "status": "failed",
                            "reason": "网盘账户不存在或无效"
                        })
                        continue
                    
                    # 检查 cookies 是否存在
                    if not drive_account.cookies:
                        result["failed_resources"] += 1
                        result["refresh_details"].append({
                            "resource_id": resource.id,
                            "status": "failed",
                            "reason": "网盘账户缺少认证信息"
                        })
                        continue
                    
                    # 需要重新分享，但需要文件ID
                    if not resource.file_id:
                        result["failed_resources"] += 1
                        result["refresh_details"].append({
                            "resource_id": resource.id,
                            "status": "failed",
                            "reason": "缺少文件ID，无法重新分享"
                        })
                        continue
                    
                    # 创建新的分享，默认7天过期
                    share_params = ShareParam(
                        drive_type=DriveType(drive_account.type),
                        file_name=resource.title or resource.main_name,
                        file_ids=[resource.file_id],
                        expired_type=7,  # 默认创建7天的分享
                        password=resource.extract_code
                    )
                    
                    # 调用分享服务
                    new_share_info = await drive_manager.create_share(
                        drive_account.cookies,
                        share_params
                    )
                    
                    # 更新资源信息
                    from backend.app.coulddrive.schema.resource import UpdateResourceParam, CreateResourceViewHistoryParam
                    from backend.app.coulddrive.crud.crud_resource import resource_view_history_dao
                    
                    # 创建更新参数，只设置需要更新的字段
                    update_data = {
                        "url": new_share_info.url,
                        "share_id": new_share_info.share_id,
                        "pwd_id": new_share_info.pwd_id,
                        "expired_at": new_share_info.expired_at,
                        "expired_left": new_share_info.expired_left,
                        "expired_type": new_share_info.expired_type,
                        "extract_code": resource.extract_code or "",
                        "view_count": 0
                    }
                    update_params = UpdateResourceParam(**update_data)
                    
                    # 更新数据库
                    await resource_dao.update(db, resource.id, update_params)
                    
                    # 记录初始浏览量历史
                    if new_share_info.pwd_id:
                        try:
                            history_param = CreateResourceViewHistoryParam(
                                pwd_id=new_share_info.pwd_id,
                                view_count=0
                            )
                            await resource_view_history_dao.create(db, history_param)
                        except Exception as e:
                            # 记录浏览量历史失败不影响资源刷新
                            logger.error(f"记录浏览量历史失败: {str(e)}")
                            pass
                    
                    result["refreshed_resources"] += 1
                    result["refresh_details"].append({
                        "resource_id": resource.id,
                        "resource_title": resource.title or resource.main_name,
                        "status": "success",
                        "old_url": resource.url,
                        "new_url": new_share_info.url,
                        "new_expired_at": new_share_info.expired_at.isoformat() if new_share_info.expired_at else None
                    })
                    
                    logger.info(f"{resource.title or resource.main_name} 刷新成功")
                    
                    # 添加随机间隔时间，避免频繁请求
                    wait_time = random.randint(5, 10)
                    await asyncio.sleep(wait_time)
                
                except Exception as e:
                    logger.error(f"刷新资源 {resource.id} 分享链接时发生错误: {str(e)}")
                    result["failed_resources"] += 1
                    result["refresh_details"].append({
                        "resource_id": resource.id,
                        "resource_title": resource.title or resource.main_name,
                        "status": "error",
                        "error": str(e)
                    })
    
    except Exception as e:
        logger.error(f"检查资源过期时发生错误: {str(e)}")
        result["error"] = str(e)
    
    return result


@celery_app.task(name='refresh_resource_share_by_id')
async def refresh_resource_share_by_id(resource_id: int) -> Dict[str, Any]:
    """
    根据资源ID刷新单个资源的分享链接
    
    :param resource_id: 资源ID
    :return: 执行结果
    """
    try:
        return await _refresh_resource_share_by_id(resource_id)
    except Exception as e:
        logger.error(f"刷新资源 {resource_id} 分享链接失败: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "resource_id": resource_id
        }


async def _refresh_resource_share_by_id(resource_id: int) -> Dict[str, Any]:
    """
    根据资源ID刷新单个资源的分享链接的异步实现
    
    :param resource_id: 资源ID
    :return: 执行结果
    """
    try:
        async with async_db_session() as db:
            # 获取资源信息
            resource = await resource_dao.get(db, resource_id)
            if not resource:
                return {
                    "success": False,
                    "error": "资源不存在",
                    "resource_id": resource_id
                }
            
            # 检查资源状态
            if resource.is_deleted or resource.status != 1:
                return {
                    "success": False,
                    "error": "资源已删除或停用",
                    "resource_id": resource_id
                }
            
            # 获取用户网盘账户信息
            drive_account = await drive_account_dao.get(db, resource.user_id)
            if not drive_account or not drive_account.is_valid:
                return {
                    "success": False,
                    "error": "网盘账户不存在或无效",
                    "resource_id": resource_id
                }
            
            # 检查 cookies 是否存在
            if not drive_account.cookies:
                return {
                    "success": False,
                    "error": "网盘账户缺少认证信息",
                    "resource_id": resource_id
                }
            
            # 检查是否有文件ID
            if not resource.file_id:
                return {
                    "success": False,
                    "error": "缺少文件ID，无法重新分享",
                    "resource_id": resource_id
                }
            
            # 创建新的分享，默认7天过期
            drive_manager = get_drive_manager()
            share_params = ShareParam(
                drive_type=DriveType(drive_account.type),
                file_name=resource.title or resource.main_name,
                file_ids=[resource.file_id],
                expired_type=7,  # 默认创建7天的分享
                password=resource.extract_code
            )
            
            # 调用分享服务
            new_share_info = await drive_manager.create_share(
                drive_account.cookies,
                share_params
            )
            
            # 更新资源信息
            from backend.app.coulddrive.schema.resource import UpdateResourceParam, CreateResourceViewHistoryParam
            from backend.app.coulddrive.crud.crud_resource import resource_view_history_dao
            
            # 创建更新参数，只设置需要更新的字段
            update_data = {
                "url": new_share_info.url,
                "share_id": new_share_info.share_id,
                "pwd_id": new_share_info.pwd_id,
                "expired_at": new_share_info.expired_at,
                "expired_left": new_share_info.expired_left,
                "expired_type": new_share_info.expired_type,
                "extract_code": resource.extract_code or "",
                "view_count": 0
            }
            update_params = UpdateResourceParam(**update_data)
            
            # 更新数据库
            await resource_dao.update(db, resource_id, update_params)
            
            # 记录初始浏览量历史
            if new_share_info.pwd_id:
                try:
                    history_param = CreateResourceViewHistoryParam(
                        pwd_id=new_share_info.pwd_id,
                        view_count=0
                    )
                    await resource_view_history_dao.create(db, history_param)
                except Exception as e:
                    # 记录浏览量历史失败不影响资源刷新
                    logger.error(f"记录浏览量历史失败: {str(e)}")
                    pass
            
            logger.info(f"{resource.title or resource.main_name} 刷新成功")
            
            return {
                "success": True,
                "resource_id": resource_id,
                "resource_title": resource.title or resource.main_name,
                "old_url": resource.url,
                "new_url": new_share_info.url,
                "new_expired_at": new_share_info.expired_at.isoformat() if new_share_info.expired_at else None
            }
    
    except Exception as e:
        error_msg = f"刷新资源 {resource_id} 分享链接时发生错误: {str(e)}"
        logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg,
            "resource_id": resource_id
        }


@celery_app.task(name='get_expiring_resources')
async def get_expiring_resources(hours: int = 24) -> List[Dict[str, Any]]:
    """
    获取即将过期的资源列表
    
    :param hours: 过期时间阈值（小时）
    :return: 即将过期的资源列表
    """
    try:
        return await _get_expiring_resources(hours)
    except Exception as e:
        logger.error(f"获取即将过期的资源列表失败: {str(e)}")
        return []


async def _get_expiring_resources(hours: int = 24) -> List[Dict[str, Any]]:
    """
    获取即将过期的资源列表的异步实现
    
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
            
            drive_manager = get_drive_manager()
            
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
                                size=50,  # 每页50条
                                order_field="created_at",
                                order_type="desc"
                            )
                            
                            # 获取分享信息
                            share_info_list = await drive_manager.get_share_info(
                                account.cookies, 
                                share_info_params
                            )
                            
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
                            
                            # 如果本页数据少于50条，说明已经是最后一页
                            if len(share_info_list) < 50:
                                break
                            
                            page += 1
                            
                            # 翻页间隔10秒
                            logger.debug(f"账户 {account.id} 翻页间隔，等待10秒...")
                            await asyncio.sleep(10)
                            
                        except Exception as e:
                            logger.error(f"获取账户 {account.id} 第{page}页分享信息失败: {str(e)}")
                            break
                    
                    # 如果有过期的分享，批量取消
                    if all_expired_shares:
                        try:
                            from backend.app.coulddrive.schema.file import CancelShareParam
                            
                            cancel_params = CancelShareParam(
                                drive_type=DriveType(account.type),
                                shareid_list=all_expired_shares
                            )
                            
                            # 批量取消分享
                            success = await drive_manager.cancel_share(
                                account.cookies,
                                cancel_params
                            )
                            
                            if success:
                                result["cleaned_shares"] += len(all_expired_shares)
                                result["cleanup_details"].append({
                                    "account_id": account.id,
                                    "account_type": account.type,
                                    "status": "success",
                                    "cleaned_count": len(all_expired_shares),
                                    "share_ids": all_expired_shares
                                })
                                logger.info(f"账户 {account.id} 成功清理 {len(all_expired_shares)} 个过期分享")
                            else:
                                result["failed_accounts"] += 1
                                result["cleanup_details"].append({
                                    "account_id": account.id,
                                    "account_type": account.type,
                                    "status": "failed",
                                    "reason": "取消分享API调用失败",
                                    "expired_count": len(all_expired_shares)
                                })
                                logger.error(f"账户 {account.id} 取消分享失败")
                        
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
                    
                    # 每个账号间隔1分钟
                    logger.debug(f"账户 {account.id} 处理完成，等待1分钟后处理下一个账户...")
                    await asyncio.sleep(60)
                
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