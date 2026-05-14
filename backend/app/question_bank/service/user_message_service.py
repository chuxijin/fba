#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.question_bank.crud.crud_user_message import user_message_dao
from backend.app.question_bank.model import UserMessage
from backend.app.question_bank.schema.user_message import (
    CreateUserMessageParam,
    GetUserMessageDetail,
    GetUserMessageListItem,
    UpdateUserMessageParam,
)
from backend.common.exception import errors
from backend.common.pagination import paging_data
from backend.utils.sensitive_words import validate_no_sensitive_words


class UserMessageService:
    """用户消息服务类"""

    @staticmethod
    async def get_admin_list(
        *,
        db: AsyncSession,
        title: str | None = None,
        message_type: str | None = None,
        status: int | None = None,
    ) -> dict[str, Any]:
        """
        获取管理端消息列表

        :param db: 数据库会话
        :param title: 标题关键词
        :param message_type: 消息类型
        :param status: 状态
        :return:
        """
        stmt = await user_message_dao.get_admin_select(
            title=title,
            message_type=message_type,
            status=status,
        )
        return await paging_data(db, stmt, GetUserMessageListItem)

    @staticmethod
    def _to_detail(message: UserMessage, is_read: bool, read_time) -> GetUserMessageDetail:
        """
        转换消息详情

        :param message: 消息
        :param is_read: 是否已读
        :param read_time: 已读时间
        :return:
        """
        data = GetUserMessageDetail.model_validate(message).model_dump()
        data['is_read'] = is_read
        data['read_time'] = read_time
        return GetUserMessageDetail(**data)

    @staticmethod
    async def get_user_list(
        *,
        db: AsyncSession,
        user_id: int,
        unread_only: bool = False,
        message_type: str | None = None,
    ) -> dict[str, Any]:
        """
        获取用户消息列表

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param unread_only: 是否只看未读
        :param message_type: 消息类型
        :return:
        """
        stmt = await user_message_dao.get_select(
            user_id=user_id,
            unread_only=unread_only,
            message_type=message_type,
        )
        page_data = await paging_data(db, stmt, GetUserMessageListItem)
        message_ids = [item['id'] for item in page_data['items'] if item.get('target_type') == 'all']
        read_map = await user_message_dao.get_read_map(db=db, user_id=user_id, message_ids=message_ids)

        for item in page_data['items']:
            if item.get('target_type') == 'user':
                item['is_read'] = item.get('read_time') is not None
                continue
            read_time = read_map.get(item['id'])
            item['read_time'] = read_time
            item['is_read'] = read_time is not None

        return page_data

    @staticmethod
    async def get_user_detail(*, db: AsyncSession, message_id: int, user_id: int) -> GetUserMessageDetail:
        """
        获取用户消息详情

        :param db: 数据库会话
        :param message_id: 消息 ID
        :param user_id: 用户 ID
        :return:
        """
        row = await user_message_dao.get_detail_for_user(db, message_id, user_id)
        if not row:
            raise errors.NotFoundError(msg='消息不存在')
        message, is_read, read_time = row
        return UserMessageService._to_detail(message, is_read, read_time)

    @staticmethod
    async def count_unread(*, db: AsyncSession, user_id: int) -> int:
        """
        获取未读消息数

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        return await user_message_dao.count_unread(db, user_id)

    @staticmethod
    async def mark_read(*, db: AsyncSession, message_id: int, user_id: int) -> None:
        """
        标记消息已读

        :param db: 数据库会话
        :param message_id: 消息 ID
        :param user_id: 用户 ID
        """
        row = await user_message_dao.get_detail_for_user(db, message_id, user_id)
        if not row:
            raise errors.NotFoundError(msg='消息不存在')
        message = row[0]
        await user_message_dao.mark_read(db, message, user_id)

    @staticmethod
    async def mark_all_read(*, db: AsyncSession, user_id: int) -> int:
        """
        标记全部消息已读

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        return await user_message_dao.mark_all_read(db, user_id)

    @staticmethod
    async def create(*, db: AsyncSession, obj_in: CreateUserMessageParam) -> UserMessage:
        """
        创建用户消息

        :param db: 数据库会话
        :param obj_in: 创建参数
        :return:
        """
        validate_no_sensitive_words(obj_in.title, '消息标题')
        validate_no_sensitive_words(obj_in.content, '消息内容')
        if obj_in.target_type == 'user' and obj_in.user_id is None:
            raise errors.RequestError(msg='个人消息必须指定用户 ID')
        if obj_in.target_type == 'all' and obj_in.user_id is not None:
            raise errors.RequestError(msg='全站消息不能指定用户 ID')
        return await user_message_dao.create(db, obj_in)

    @staticmethod
    async def update(*, db: AsyncSession, pk: int, obj_in: UpdateUserMessageParam) -> int:
        """
        更新用户消息

        :param db: 数据库会话
        :param pk: 消息 ID
        :param obj_in: 更新参数
        :return:
        """
        message = await user_message_dao.get(db, pk)
        if not message:
            raise errors.NotFoundError(msg='消息不存在')
        validate_no_sensitive_words(obj_in.title, '消息标题')
        validate_no_sensitive_words(obj_in.content, '消息内容')
        if obj_in.target_type == 'user' and obj_in.user_id is None:
            raise errors.RequestError(msg='个人消息必须指定用户 ID')
        if obj_in.target_type == 'all' and obj_in.user_id is not None:
            raise errors.RequestError(msg='全站消息不能指定用户 ID')
        return await user_message_dao.update(db, pk, obj_in)

    @staticmethod
    async def delete(*, db: AsyncSession, pk: int) -> int:
        """
        删除用户消息

        :param db: 数据库会话
        :param pk: 消息 ID
        :return:
        """
        message = await user_message_dao.get(db, pk)
        if not message:
            raise errors.NotFoundError(msg='消息不存在')
        return await user_message_dao.delete(db, pk)


user_message_service: UserMessageService = UserMessageService()
