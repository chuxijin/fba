#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.admin.crud.crud_message import message_dao
from backend.app.admin.model.message import Message, MessageTargetType
from backend.app.admin.schema.message import (
    CreateMessageParam,
    DeleteMessageParam,
    GetMyMessageItem,
    MessageQueryParam,
    PublishMessageParam,
    UpdateMessageParam,
)
from backend.common.exception import errors
from backend.common.pagination import paging_data
from backend.utils.sensitive_words import validate_no_sensitive_words


class MessageService:
    """系统消息服务类"""

    @staticmethod
    def _validate_target(target_type: str | None, user_id: int | None, role_id: int | None) -> None:
        """
        校验投递目标合法性

        :param target_type: 目标类型
        :param user_id: 目标用户 ID
        :param role_id: 目标角色 ID
        """
        if target_type is None:
            return
        if target_type == MessageTargetType.USER and user_id is None:
            raise errors.RequestError(msg='个人消息必须指定用户 ID')
        if target_type == MessageTargetType.ROLE and role_id is None:
            raise errors.RequestError(msg='角色消息必须指定角色 ID')
        if target_type == MessageTargetType.ALL and (user_id is not None or role_id is not None):
            raise errors.RequestError(msg='全站消息不能指定用户 ID 或角色 ID')

    # ------------------------------------------------------------------ 管理端

    @staticmethod
    async def get_list(*, db: AsyncSession, params: MessageQueryParam) -> dict[str, Any]:
        """
        获取消息分页列表

        :param db: 数据库会话
        :param params: 查询参数
        :return:
        """
        select_stmt = message_dao.get_select(params)
        return await paging_data(db, select_stmt)

    @staticmethod
    async def get(*, db: AsyncSession, pk: int) -> Message:
        """
        获取消息详情

        :param db: 数据库会话
        :param pk: 消息 ID
        :return:
        """
        message = await message_dao.get(db, pk)
        if not message:
            raise errors.NotFoundError(msg='消息不存在')
        return message

    @staticmethod
    async def create(*, db: AsyncSession, obj: CreateMessageParam, sender_id: int | None = None) -> Message:
        """
        创建消息

        :param db: 数据库会话
        :param obj: 创建参数
        :param sender_id: 发送人 ID
        :return:
        """
        validate_no_sensitive_words(obj.title, '消息标题')
        validate_no_sensitive_words(obj.content, '消息内容')
        MessageService._validate_target(obj.target_type, obj.user_id, obj.role_id)
        return await message_dao.create(db, obj, sender_id=sender_id)

    @staticmethod
    async def update(*, db: AsyncSession, pk: int, obj: UpdateMessageParam) -> int:
        """
        更新消息

        :param db: 数据库会话
        :param pk: 消息 ID
        :param obj: 更新参数
        :return:
        """
        message = await message_dao.get(db, pk)
        if not message:
            raise errors.NotFoundError(msg='消息不存在')

        update_data = obj.model_dump(exclude_unset=True)
        if not update_data:
            return 0

        validate_no_sensitive_words(update_data.get('title'), '消息标题')
        validate_no_sensitive_words(update_data.get('content'), '消息内容')

        target_type = update_data.get('target_type', message.target_type)
        user_id = update_data.get('user_id', message.user_id)
        role_id = update_data.get('role_id', message.role_id)
        MessageService._validate_target(target_type, user_id, role_id)

        return await message_dao.update(db, pk, update_data)

    @staticmethod
    async def delete_batch(*, db: AsyncSession, obj: DeleteMessageParam) -> int:
        """
        批量删除消息

        :param db: 数据库会话
        :param obj: 删除参数
        :return:
        """
        return await message_dao.delete_batch(db, obj.ids)

    # ------------------------------------------------------------------ 生产者入口

    @staticmethod
    async def publish(*, db: AsyncSession, obj: PublishMessageParam, sender_id: int | None = None) -> Message:
        """
        发布消息（其他模块作为生产者的统一入口）

        :param db: 数据库会话
        :param obj: 发布参数
        :param sender_id: 发送人 ID（系统自动发送为空）
        :return:
        """
        create_obj = CreateMessageParam(**obj.model_dump())
        return await MessageService.create(db=db, obj=create_obj, sender_id=sender_id)

    # ------------------------------------------------------------------ 用户端

    @staticmethod
    async def get_my_list(
        *,
        db: AsyncSession,
        user_id: int,
        unread_only: bool = False,
        message_type: str | None = None,
    ) -> dict[str, Any]:
        """
        获取当前用户的消息分页列表

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param unread_only: 是否只看未读
        :param message_type: 消息类型
        :return:
        """
        select_stmt = message_dao.get_select_for_user(
            user_id=user_id,
            unread_only=unread_only,
            message_type=message_type,
        )
        page_data = await paging_data(db, select_stmt, GetMyMessageItem)

        message_ids = [item['id'] for item in page_data['items']]
        read_map = await message_dao.get_read_map(db=db, user_id=user_id, message_ids=message_ids)
        for item in page_data['items']:
            read_time = read_map.get(item['id'])
            item['read_time'] = read_time
            item['is_read'] = read_time is not None

        return page_data

    @staticmethod
    async def get_my_detail(*, db: AsyncSession, pk: int, user_id: int) -> GetMyMessageItem:
        """
        获取当前用户的消息详情

        :param db: 数据库会话
        :param pk: 消息 ID
        :param user_id: 用户 ID
        :return:
        """
        message = await message_dao.get_for_user(db, pk, user_id)
        if not message:
            raise errors.NotFoundError(msg='消息不存在')

        read_map = await message_dao.get_read_map(db=db, user_id=user_id, message_ids=[message.id])
        read_time = read_map.get(message.id)

        detail = GetMyMessageItem.model_validate(message)
        detail.read_time = read_time
        detail.is_read = read_time is not None
        return detail

    @staticmethod
    async def count_unread(*, db: AsyncSession, user_id: int) -> int:
        """
        获取未读消息数

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        return await message_dao.count_unread(db, user_id)

    @staticmethod
    async def mark_read(*, db: AsyncSession, pk: int, user_id: int) -> None:
        """
        标记消息已读

        :param db: 数据库会话
        :param pk: 消息 ID
        :param user_id: 用户 ID
        """
        message = await message_dao.get_for_user(db, pk, user_id)
        if not message:
            raise errors.NotFoundError(msg='消息不存在')
        await message_dao.mark_read(db, message.id, user_id)

    @staticmethod
    async def mark_all_read(*, db: AsyncSession, user_id: int) -> int:
        """
        标记全部消息已读

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        return await message_dao.mark_all_read(db, user_id)


message_service: MessageService = MessageService()
