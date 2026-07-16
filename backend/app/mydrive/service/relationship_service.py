#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.mydrive.crud.crud_account import mydrive_account_dao
from backend.app.mydrive.service.drives.baidu.client import BaiduRequest
from backend.common.exception import errors


class MyDriveRelationshipService:
    """网盘关系分享服务"""

    @staticmethod
    async def list_relationships(
        db: AsyncSession,
        *,
        account_id: int,
        owner_id: int,
        space_type: str,
        offset: int = 0,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """
        获取百度好友或群组列表。

        :param db: 数据库会话
        :param account_id: MyDrive 账户 ID
        :param owner_id: 所属用户 ID
        :param space_type: 关系空间类型
        :param offset: 偏移量
        :param limit: 单页数量
        :return:
        """
        client = await MyDriveRelationshipService._create_baidu_client(db, account_id, owner_id)
        try:
            if space_type == 'friend':
                response = await client.list_friends(start=offset, limit=limit)
                return [
                    {
                        'source_id': str(item.get('uk') or ''),
                        'name': str(item.get('nick_name') or item.get('uname') or item.get('uk') or ''),
                        'extra': {'avatar_url': item.get('avatar_url'), 'is_friend': item.get('is_friend')},
                    }
                    for item in response.get('records', [])
                    if isinstance(item, dict) and item.get('uk')
                ]
            if space_type == 'group':
                response = await client.list_groups(start=offset, limit=limit)
                return [
                    {
                        'source_id': str(item.get('gid') or ''),
                        'name': str(item.get('name') or item.get('gid') or ''),
                        'extra': {'group_number': item.get('gnum'), 'type': item.get('type'), 'status': item.get('status')},
                    }
                    for item in response.get('records', [])
                    if isinstance(item, dict) and item.get('gid')
                ]
            raise errors.ForbiddenError(msg='关系空间类型仅支持 friend 或 group')
        finally:
            await client.aclose()

    @staticmethod
    async def list_shares(
        db: AsyncSession,
        *,
        account_id: int,
        owner_id: int,
        space_type: str,
        source_id: str,
    ) -> list[dict[str, Any]]:
        """
        获取百度好友或群组分享消息。

        :param db: 数据库会话
        :param account_id: MyDrive 账户 ID
        :param owner_id: 所属用户 ID
        :param space_type: 关系空间类型
        :param source_id: 好友 UK 或群组 ID
        :return:
        """
        client = await MyDriveRelationshipService._create_baidu_client(db, account_id, owner_id)
        try:
            if space_type == 'friend':
                response = await client.list_friend_shares(source_id)
                messages = response.get('records', {}).get('list', [])
                return MyDriveRelationshipService._serialize_shares(messages, source_id, 'friend')
            if space_type == 'group':
                response = await client.list_group_shares(source_id)
                messages = response.get('records', {}).get('msg_list', [])
                return MyDriveRelationshipService._serialize_shares(messages, source_id, 'group')
            raise errors.ForbiddenError(msg='关系空间类型仅支持 friend 或 group')
        finally:
            await client.aclose()

    @staticmethod
    async def _create_baidu_client(db: AsyncSession, account_id: int, owner_id: int) -> BaiduRequest:
        """创建已校验的百度关系请求客户端。"""
        account = await mydrive_account_dao.get(db, account_id, owner_id)
        if account is None:
            raise errors.NotFoundError(msg='网盘账户不存在')
        if account.provider != 'baidu':
            raise errors.ForbiddenError(msg='好友或群组功能仅支持百度网盘账户')
        cookie = str(account.credential.get('cookie') or '').strip()
        if not cookie:
            raise errors.ForbiddenError(msg='网盘账户缺少 Cookie 凭证')
        return BaiduRequest(cookie)

    @staticmethod
    def _serialize_shares(messages: Any, source_id: str, space_type: str) -> list[dict[str, Any]]:
        """将关系分享消息转换为文件空间定位信息。"""
        if not isinstance(messages, list):
            return []
        shares: list[dict[str, Any]] = []
        for message in messages:
            if not isinstance(message, dict):
                continue
            message_id = str(message.get('msg_id') or '')
            from_uk = str(message.get('from_uk') or message.get('uk') or '')
            file_list = message.get('filelist', {}).get('list', []) if space_type == 'friend' else message.get('file_list', [])
            if not message_id or not from_uk or not isinstance(file_list, list):
                continue
            for item in file_list:
                if not isinstance(item, dict) or not item.get('fs_id'):
                    continue
                shares.append(
                    {
                        'source_id': source_id,
                        'from_uk': from_uk,
                        'message_id': message_id,
                        'root_id': str(item['fs_id']),
                        'name': str(item.get('server_filename') or item['fs_id']),
                        'is_directory': bool(item.get('isdir')),
                        'size': item.get('size'),
                        'extra': {'space_type': space_type},
                    }
                )
        return shares


mydrive_relationship_service: MyDriveRelationshipService = MyDriveRelationshipService()
