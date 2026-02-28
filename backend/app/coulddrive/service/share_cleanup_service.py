#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
网盘分享清理服务

职责：遍历有效网盘账户，查找过期的本地分享并批量取消。
"""
import asyncio
import random
from typing import Any

from backend.app.coulddrive.crud.crud_drive_account import drive_account_dao
from backend.app.coulddrive.schema.enum import DriveType
from backend.app.coulddrive.schema.file import CancelShareParam, ListShareInfoParam
from backend.app.coulddrive.service.coulddrive_service import CouldDriveService
from backend.common.log import log
from backend.database.db import async_db_session


class ShareCleanupService:
    """网盘分享清理服务"""

    # 分批取消时每批的最大数量
    CANCEL_BATCH_SIZE = 40
    # 每页查询分享数
    PAGE_SIZE = 100

    @staticmethod
    async def cleanup_expired_local_shares() -> dict[str, Any]:
        """
        扫描所有有效网盘账户，查找过期的本地分享并批量取消。

        :return: 执行结果统计
        """
        result = {
            'checked_accounts': 0,
            'cleaned_shares': 0,
            'failed_accounts': 0,
            'cleanup_details': [],
        }

        async with async_db_session() as db:
            drive_accounts = await drive_account_dao.get_list_with_pagination(db, is_valid=True)
            result['checked_accounts'] = len(drive_accounts)

            for account in drive_accounts:
                if not account.is_valid or not account.cookies:
                    result['cleanup_details'].append({
                        'account_id': account.id,
                        'account_type': account.type,
                        'status': 'skipped',
                        'reason': '账户无效或缺少认证信息',
                    })
                    continue

                log.info(f'开始检查账户 {account.id} ({account.type}) 的本地分享')

                try:
                    detail = await ShareCleanupService._process_account(account)
                    result['cleaned_shares'] += detail.get('cleaned_count', 0)
                    if detail['status'] == 'error':
                        result['failed_accounts'] += 1
                    result['cleanup_details'].append(detail)
                except Exception as e:
                    log.error(f'处理账户 {account.id} 时发生错误: {e}')
                    result['failed_accounts'] += 1
                    result['cleanup_details'].append({
                        'account_id': account.id,
                        'account_type': account.type,
                        'status': 'error',
                        'error': str(e),
                    })

                # 每个账号间隔 30-40 秒
                await asyncio.sleep(random.randint(30, 40))

        return result

    @staticmethod
    async def _process_account(account) -> dict[str, Any]:
        """处理单个账户：获取过期分享 → 批量取消"""
        service = CouldDriveService(
            auth_data=account.cookies,
            drive_type=DriveType(account.type),
        )

        # 1. 收集所有过期的分享 ID
        expired_share_ids = await ShareCleanupService._collect_expired_shares(service, account)

        if not expired_share_ids:
            log.info(f'账户 {account.id} 没有过期的分享需要清理')
            return {
                'account_id': account.id,
                'account_type': account.type,
                'status': 'no_expired',
                'reason': '没有找到过期的分享',
            }

        # 2. 分批取消
        return await ShareCleanupService._batch_cancel_shares(service, account, expired_share_ids)

    @staticmethod
    async def _collect_expired_shares(service: CouldDriveService, account) -> list[str]:
        """翻页获取某个账户的所有过期分享 ID"""
        expired_ids: list[str] = []
        page = 1

        while True:
            try:
                params = ListShareInfoParam(
                    drive_type=DriveType(account.type),
                    source_type='local',
                    source_id='',
                    page=page,
                    size=ShareCleanupService.PAGE_SIZE,
                    order_field='created_at',
                    order_type='desc',
                )
                response = await service.get_share_info(params=params)

                # 兼容 dict / list 两种返回格式
                if isinstance(response, dict) and 'list' in response:
                    share_list = response['list']
                elif isinstance(response, list):
                    share_list = response
                else:
                    share_list = []

                if not share_list:
                    break

                for info in share_list:
                    if info.expired_type == -1:
                        expired_ids.append(info.share_id)
                    elif info.expired_left is not None and info.expired_left < 0:
                        expired_ids.append(info.share_id)

                if len(share_list) < ShareCleanupService.PAGE_SIZE:
                    break

                page += 1
                await asyncio.sleep(random.randint(5, 8))

            except Exception as e:
                log.error(f'获取账户 {account.id} 第{page}页分享信息失败: {e}')
                break

        return expired_ids

    @staticmethod
    async def _batch_cancel_shares(
        service: CouldDriveService,
        account,
        share_ids: list[str],
    ) -> dict[str, Any]:
        """分批取消过期分享"""
        batch_size = ShareCleanupService.CANCEL_BATCH_SIZE
        total = len(share_ids)
        total_cleaned = 0
        successful_batches = 0
        failed_batches = 0

        log.info(f'账户 {account.id} 共有 {total} 个过期分享，将分 {(total + batch_size - 1) // batch_size} 批处理')

        for i in range(0, total, batch_size):
            batch = share_ids[i:i + batch_size]
            batch_num = i // batch_size + 1

            try:
                params = CancelShareParam(
                    drive_type=DriveType(account.type),
                    shareid_list=batch,
                )
                success = await service.cancel_share(params=params)

                if success:
                    successful_batches += 1
                    total_cleaned += len(batch)
                    log.info(f'账户 {account.id} 第{batch_num}批成功清理 {len(batch)} 个过期分享')
                else:
                    failed_batches += 1
                    log.error(f'账户 {account.id} 第{batch_num}批取消分享失败')

                # 批次间隔
                if i + batch_size < total:
                    await asyncio.sleep(random.randint(3, 5))

            except Exception as e:
                failed_batches += 1
                log.error(f'账户 {account.id} 第{batch_num}批取消分享时发生错误: {e}')

        status = 'success' if total_cleaned > 0 else 'failed'
        log.info(f'账户 {account.id} 成功清理 {total_cleaned}/{total} 个过期分享')

        return {
            'account_id': account.id,
            'account_type': account.type,
            'status': status,
            'cleaned_count': total_cleaned,
            'total_count': total,
            'successful_batches': successful_batches,
            'failed_batches': failed_batches,
        }


share_cleanup_service: ShareCleanupService = ShareCleanupService()
