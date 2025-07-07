#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio
import logging
import random
from datetime import datetime
from typing import Dict, Any

from backend.app.coulddrive.crud.crud_drive_account import drive_account_dao
from backend.app.coulddrive.service.yp_service import get_drive_manager
from backend.app.coulddrive.schema.file import UserInfoParam
from backend.app.coulddrive.schema.enum import DriveType
from backend.app.coulddrive.schema.user import UpdateDriveAccountParam
from backend.app.task.celery import celery_app
from backend.database.db import async_db_session

logger = logging.getLogger(__name__)


@celery_app.task(name='refresh_all_valid_drive_users')
async def refresh_all_valid_drive_users() -> Dict[str, Any]:
    """
    刷新所有有效的网盘用户信息
    
    扫描数据库中所有有效的网盘账户，
    通过API获取最新的用户信息并更新到数据库
    
    :return: 执行结果统计
    """
    try:
        result = await _refresh_all_valid_drive_users()
        logger.info(f"用户信息刷新完成: 检查{result['checked_users']}个，刷新{result['refreshed_users']}个")
        return result
            
    except Exception as e:
        logger.error(f"用户信息刷新失败: {str(e)}")
        return {
            "checked_users": 0,
            "refreshed_users": 0,
            "failed_users": 0,
            "skipped_users": 0,
            "refresh_details": [],
            "error": str(e)
        }


async def _refresh_all_valid_drive_users() -> Dict[str, Any]:
    """
    刷新所有有效的网盘用户信息的异步实现
    
    :return: 执行结果统计
    """
    result = {
        "checked_users": 0,
        "refreshed_users": 0,
        "failed_users": 0,
        "skipped_users": 0,
        "refresh_details": []
    }
    
    try:
        async with async_db_session() as db:
            # 获取所有有效的网盘账户
            valid_accounts = await drive_account_dao.get_list_with_pagination(db, is_valid=True)
            
            result["checked_users"] = len(valid_accounts)
            
            drive_manager = get_drive_manager()
            
            for account in valid_accounts:
                try:
                    # 跳过无效账户或缺少认证信息的账户
                    if not account.is_valid or not account.cookies:
                        result["skipped_users"] += 1
                        result["refresh_details"].append({
                            "account_id": account.id,
                            "user_id": account.user_id,
                            "username": account.username,
                            "drive_type": account.type,
                            "status": "skipped",
                            "reason": "账户无效或缺少认证信息"
                        })
                        continue
                    
                    logger.info(f"开始刷新用户 {account.username} ({account.type}) 的信息")
                    
                    # 构建用户信息查询参数
                    user_info_params = UserInfoParam(
                        drive_type=DriveType(account.type)
                    )
                    
                    # 获取最新的用户信息
                    updated_user_info = await drive_manager.get_user_info(
                        account.cookies, 
                        user_info_params
                    )
                    
                    # 准备更新数据
                    update_data = UpdateDriveAccountParam(
                        username=updated_user_info.username,
                        avatar_url=updated_user_info.avatar_url,
                        quota=updated_user_info.quota,
                        used=updated_user_info.used,
                        is_vip=updated_user_info.is_vip,
                        is_supervip=updated_user_info.is_supervip,
                        is_valid=True  # 如果能成功获取信息，说明账户仍然有效
                    )
                    
                    # 更新数据库
                    await drive_account_dao.update(db, account.id, update_data)
                    
                    result["refreshed_users"] += 1
                    result["refresh_details"].append({
                        "account_id": account.id,
                        "user_id": account.user_id,
                        "username": updated_user_info.username,
                        "drive_type": account.type,
                        "status": "success",
                        "old_quota": account.quota,
                        "new_quota": updated_user_info.quota,
                        "old_used": account.used,
                        "new_used": updated_user_info.used,
                        "old_vip": account.is_vip,
                        "new_vip": updated_user_info.is_vip,
                        "old_supervip": account.is_supervip,
                        "new_supervip": updated_user_info.is_supervip
                    })
                    
                    logger.info(f"用户 {updated_user_info.username} 信息刷新成功")
                    
                    # 添加随机间隔时间，避免频繁请求
                    wait_time = random.randint(3, 8)
                    await asyncio.sleep(wait_time)
                
                except Exception as e:
                    logger.error(f"刷新用户 {account.id} 信息时发生错误: {str(e)}")
                    
                    # 如果是认证失败，标记账户为无效
                    if "认证" in str(e) or "登录" in str(e) or "token" in str(e).lower() or "auth" in str(e).lower():
                        try:
                            await drive_account_dao.update_validity(db, account.id, False)
                            logger.warning(f"用户 {account.id} 认证失败，已标记为无效")
                        except Exception as update_error:
                            logger.error(f"更新用户 {account.id} 有效性状态失败: {str(update_error)}")
                    
                    result["failed_users"] += 1
                    result["refresh_details"].append({
                        "account_id": account.id,
                        "user_id": account.user_id,
                        "username": account.username,
                        "drive_type": account.type,
                        "status": "error",
                        "error": str(e)
                    })
    
    except Exception as e:
        logger.error(f"刷新用户信息时发生错误: {str(e)}")
        result["error"] = str(e)
    
    return result 