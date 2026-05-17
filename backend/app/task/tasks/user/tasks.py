#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio
import logging
import random

from typing import Any

from backend.app.coulddrive.crud.crud_drive_account import drive_account_dao
from backend.app.coulddrive.schema.enum import DriveType
from backend.app.coulddrive.schema.file import UserInfoParam
from backend.app.coulddrive.schema.user import UpdateDriveAccountParam
from backend.app.coulddrive.service.coulddrive_service import CouldDriveService, DriveAuthError
from backend.app.task.celery import celery_app
from backend.database.db import async_db_session

logger = logging.getLogger(__name__)


@celery_app.task(name='refresh_all_valid_drive_users', bind=True)
async def refresh_all_valid_drive_users(self) -> dict[str, Any]:
    """刷新所有有效的网盘用户信息"""
    result = await _refresh_all_valid_drive_users(self)
    logger.info(f"用户信息刷新完成: 检查{result['checked_users']}个，刷新{result['refreshed_users']}个")
    return result


async def _refresh_all_valid_drive_users(task) -> dict[str, Any]:
    """刷新所有有效的网盘用户信息的异步实现"""
    result = {
        "checked_users": 0,
        "refreshed_users": 0,
        "failed_users": 0,
        "skipped_users": 0,
        "refresh_details": []
    }

    async with async_db_session() as db:
        # 获取所有有效的网盘账户
        valid_accounts = await drive_account_dao.get_list_with_pagination(db, is_valid=True)

        result["checked_users"] = len(valid_accounts)

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

                # 直接使用外部模式创建服务实例（避免重复查询数据库）
                service = CouldDriveService(auth_data=account.cookies, drive_type=DriveType(account.type))

                # 构建用户信息查询参数
                user_info_params = UserInfoParam(
                    drive_type=DriveType(account.type)
                )

                # 获取最新的用户信息
                updated_user_info = await service.get_user_info(params=user_info_params)

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

            except DriveAuthError as e:
                # 认证失效：回滚事务 → 标记账号无效 → 发送警告通知
                await db.rollback()
                try:
                    await drive_account_dao.update_validity(db, account.id, False)
                    await db.commit()
                except Exception:
                    await db.rollback()

                logger.warning(f"用户 {account.username} ({account.type}) 认证已失效，已标记为无效")
                await task.on_warning(
                    f'网盘账号认证失效: {account.username} ({account.type})\n'
                    f'账户ID: {account.id}\n'
                    f'错误: {str(e)[:200]}\n'
                    f'请及时更新 Cookie/Token'
                )

                result["failed_users"] += 1
                result["refresh_details"].append({
                    "account_id": account.id,
                    "user_id": account.user_id,
                    "username": account.username,
                    "drive_type": account.type,
                    "status": "auth_expired",
                    "error": str(e)
                })

            except Exception as e:
                # 其他错误：回滚事务防止污染后续用户
                await db.rollback()
                logger.error(f"刷新用户 {account.id} 信息时发生错误: {str(e)}")

                result["failed_users"] += 1
                result["refresh_details"].append({
                    "account_id": account.id,
                    "user_id": account.user_id,
                    "username": account.username,
                    "drive_type": account.type,
                    "status": "error",
                    "error": str(e)
                })

    return result


@celery_app.task(name='check_expired_user_roles')
async def check_expired_user_roles() -> int:
    """检查并处理过期的用户角色"""
    from backend.app.admin.service.user_role_expiry_service import user_role_expiry_service

    return await user_role_expiry_service.check_and_expire_roles()


@celery_app.task(name='check_expired_memberships')
async def check_expired_memberships() -> int:
    """检查并处理过期会员"""
    from backend.app.access.service.subscription_service import subscription_service

    async with async_db_session.begin() as db:
        return await subscription_service.expire_due_subscriptions(db)
