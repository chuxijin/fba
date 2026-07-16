#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.mydrive.crud.crud_account import mydrive_account_dao
from backend.app.mydrive.model.space import MyDriveSpace
from backend.app.mydrive.service.filesystem.factory import create_file_space
from backend.app.mydrive.service.filesystem.models import SpaceType
from backend.app.mydrive.service.filesystem.spaces import ShareableFileSpace
from backend.common.log import log
from backend.utils.timezone import timezone


class MyDriveShareCleanupService:
    """MyDrive 本地过期分享清理服务"""

    PAGE_SIZE = 100

    @staticmethod
    async def cleanup_expired_local_shares(db: AsyncSession) -> dict[str, Any]:
        """清理所有活跃账户的本地过期分享。"""
        result: dict[str, Any] = {
            'checked_accounts': 0,
            'cleaned_shares': 0,
            'failed_accounts': 0,
            'details': [],
        }
        accounts = await mydrive_account_dao.list_active_share_accounts(db)
        result['checked_accounts'] = len(accounts)
        current_time = timezone.now()

        for account in accounts:
            try:
                account_result = await MyDriveShareCleanupService._cleanup_account(db, account, current_time)
                result['cleaned_shares'] += account_result['cleaned_count']
                result['details'].append(account_result)
            except Exception as exc:
                log.warning('清理 MyDrive 账户过期分享失败 account_id={} provider={} error={}', account.id, account.provider, exc)
                result['failed_accounts'] += 1
                result['details'].append({
                    'account_id': account.id,
                    'provider': account.provider,
                    'status': 'failed',
                    'reason': str(exc),
                })
        return result

    @staticmethod
    async def _cleanup_account(db: AsyncSession, account, current_time: datetime) -> dict[str, Any]:
        """
        清理单个账户的过期分享。

        :param db: 数据库会话
        :param account: MyDrive 账户
        :param current_time: 当前时间
        :return:
        """
        space = MyDriveSpace(
            account_id=account.id,
            capabilities=[],
            name='share-cleanup',
            owner_id=account.owner_id,
            provider=account.provider,
            root_id='0' if account.provider == 'quark' else None,
            root_path='/',
            source_key=f'account:{account.id}',
            source_ref={},
            space_type=SpaceType.PERSONAL.value,
        )
        file_space = await create_file_space(db, space)
        try:
            if not isinstance(file_space, ShareableFileSpace):
                return {
                    'account_id': account.id,
                    'provider': account.provider,
                    'status': 'skipped',
                    'reason': '账户不支持分享管理',
                    'cleaned_count': 0,
                }
            expired_share_ids = await MyDriveShareCleanupService._collect_expired_share_ids(file_space, current_time)
            if expired_share_ids:
                await file_space.cancel_shares(expired_share_ids)
            return {
                'account_id': account.id,
                'provider': account.provider,
                'status': 'success',
                'cleaned_count': len(expired_share_ids),
            }
        finally:
            await file_space.aclose()

    @staticmethod
    async def _collect_expired_share_ids(file_space: ShareableFileSpace, current_time: datetime) -> list[str]:
        """
        分页获取本地过期分享 ID。

        :param file_space: 可管理分享的个人空间
        :param current_time: 当前时间
        :return:
        """
        expired_share_ids: list[str] = []
        page = 1
        while True:
            shares, total = await file_space.list_shares(page, MyDriveShareCleanupService.PAGE_SIZE)
            expired_share_ids.extend(
                share.share_id
                for share in shares
                if MyDriveShareCleanupService._is_expired(share.expired_at, current_time)
            )
            if page * MyDriveShareCleanupService.PAGE_SIZE >= total or len(shares) < MyDriveShareCleanupService.PAGE_SIZE:
                return expired_share_ids
            page += 1

    @staticmethod
    def _is_expired(expired_at: datetime | None, current_time: datetime) -> bool:
        """
        判断分享是否过期。

        :param expired_at: 分享过期时间
        :param current_time: 当前时间
        :return:
        """
        if expired_at is None:
            return False
        if expired_at.tzinfo is None:
            expired_at = expired_at.replace(tzinfo=timezone.tz_info)
        return expired_at <= current_time


mydrive_share_cleanup_service: MyDriveShareCleanupService = MyDriveShareCleanupService()
