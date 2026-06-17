#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import and_, exists, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.question_bank.model import UserMessage, UserMessageRead
from backend.app.question_bank.schema.user_message import CreateUserMessageParam, UpdateUserMessageParam
from backend.common.enums import DataBaseType
from backend.core.conf import settings
from backend.utils.timezone import timezone


class CRUDUserMessage(CRUDPlus[UserMessage]):
    """用户消息数据库操作类"""

    @staticmethod
    def _active_condition(now: datetime):
        return and_(
            UserMessage.status == 1,
            UserMessage.publish_time <= now,
            or_(UserMessage.expire_time.is_(None), UserMessage.expire_time >= now),
        )

    @staticmethod
    def _visible_condition(user_id: int):
        return or_(
            UserMessage.target_type == 'all',
            and_(UserMessage.target_type == 'user', UserMessage.user_id == user_id),
        )

    @staticmethod
    def _read_exists(user_id: int):
        return exists().where(
            UserMessageRead.message_id == UserMessage.id,
            UserMessageRead.user_id == user_id,
        )

    async def get(self, db: AsyncSession, pk: int) -> UserMessage | None:
        """
        获取用户消息

        :param db: 数据库会话
        :param pk: 消息 ID
        :return:
        """
        return await self.select_model(db, pk)

    async def get_admin_select(
        self,
        *,
        title: str | None = None,
        message_type: str | None = None,
        status: int | None = None,
    ) -> Select:
        """
        获取管理端消息查询表达式

        :param title: 标题关键词
        :param message_type: 消息类型
        :param status: 状态
        :return:
        """
        stmt = select(UserMessage).order_by(UserMessage.id.desc())
        if title:
            stmt = stmt.where(UserMessage.title.ilike(f'%{title}%'))
        if message_type:
            stmt = stmt.where(UserMessage.message_type == message_type)
        if status is not None:
            stmt = stmt.where(UserMessage.status == status)
        return stmt

    async def get_select(
        self,
        *,
        user_id: int,
        unread_only: bool = False,
        message_type: str | None = None,
    ) -> Select:
        """
        获取用户消息查询表达式

        :param user_id: 用户 ID
        :param unread_only: 是否只看未读
        :param message_type: 消息类型
        :return:
        """
        now = timezone.now()
        read_exists = self._read_exists(user_id)

        stmt = (
            select(UserMessage)
            .where(
                self._visible_condition(user_id),
                self._active_condition(now),
            )
            .order_by(UserMessage.publish_time.desc(), UserMessage.id.desc())
        )
        if unread_only:
            stmt = stmt.where(
                or_(
                    and_(UserMessage.target_type == 'user', UserMessage.read_time.is_(None)),
                    and_(UserMessage.target_type == 'all', ~read_exists),
                )
            )
        if message_type:
            stmt = stmt.where(UserMessage.message_type == message_type)
        return stmt

    async def get_detail_for_user(
        self, db: AsyncSession, message_id: int, user_id: int
    ) -> tuple[UserMessage, bool, datetime | None] | None:
        """
        获取用户可见消息详情

        :param db: 数据库会话
        :param message_id: 消息 ID
        :param user_id: 用户 ID
        :return:
        """
        stmt = await self.get_select(user_id=user_id)
        stmt = stmt.where(UserMessage.id == message_id)
        result = await db.execute(stmt)
        message = result.scalars().first()
        if not message:
            return None

        if message.target_type == 'user':
            return message, message.read_time is not None, message.read_time

        read_map = await self.get_read_map(db=db, user_id=user_id, message_ids=[message.id])
        read_time = read_map.get(message.id)
        return message, read_time is not None, read_time

    async def get_read_map(
        self,
        db: AsyncSession,
        user_id: int,
        message_ids: list[int],
    ) -> dict[int, datetime]:
        """
        获取全站消息已读时间映射

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param message_ids: 消息 ID 列表
        :return:
        """
        if not message_ids:
            return {}

        stmt = select(UserMessageRead.message_id, UserMessageRead.read_time).where(
            UserMessageRead.user_id == user_id,
            UserMessageRead.message_id.in_(message_ids),
        )
        rows = (await db.execute(stmt)).all()
        return {row.message_id: row.read_time for row in rows}

    async def count_unread(self, db: AsyncSession, user_id: int) -> int:
        """
        统计未读消息数

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        now = timezone.now()
        read_exists = self._read_exists(user_id)
        stmt = (
            select(func.count())
            .select_from(UserMessage)
            .where(
                self._visible_condition(user_id),
                self._active_condition(now),
                or_(
                    and_(UserMessage.target_type == 'user', UserMessage.read_time.is_(None)),
                    and_(UserMessage.target_type == 'all', ~read_exists),
                ),
            )
        )
        result = await db.execute(stmt)
        return result.scalar() or 0

    async def create(self, db: AsyncSession, obj_in: CreateUserMessageParam) -> UserMessage:
        """
        创建用户消息

        :param db: 数据库会话
        :param obj_in: 创建参数
        :return:
        """
        obj_data = obj_in.model_dump()
        if obj_data.get('publish_time') is None:
            obj_data['publish_time'] = timezone.now()
        message = self.model(**obj_data)
        db.add(message)
        await db.flush()
        await db.refresh(message)
        return message

    async def update(self, db: AsyncSession, pk: int, obj_in: UpdateUserMessageParam) -> int:
        """
        更新用户消息

        :param db: 数据库会话
        :param pk: 消息 ID
        :param obj_in: 更新参数
        :return:
        """
        return await self.update_model(db, pk, obj_in)

    async def delete(self, db: AsyncSession, pk: int) -> int:
        """
        删除用户消息

        :param db: 数据库会话
        :param pk: 消息 ID
        :return:
        """
        return await self.delete_model(db, pk)

    async def mark_read(self, db: AsyncSession, message: UserMessage, user_id: int) -> None:
        """
        标记消息已读

        :param db: 数据库会话
        :param message: 消息
        :param user_id: 用户 ID
        """
        now = timezone.now()
        if message.target_type == 'user':
            stmt = (
                update(UserMessage)
                .where(
                    UserMessage.id == message.id,
                    UserMessage.user_id == user_id,
                )
                .values(read_time=now)
            )
            await db.execute(stmt)
            await db.flush()
            return

        row = {
            'message_id': message.id,
            'user_id': user_id,
            'read_time': now,
            'created_time': now,
        }
        if DataBaseType.postgresql == settings.DATABASE_TYPE:
            stmt = pg_insert(UserMessageRead).values(row)
            stmt = stmt.on_conflict_do_update(
                constraint='uq_user_message_read_message_user',
                set_={'read_time': stmt.excluded.read_time},
            )
            await db.execute(stmt)
        else:
            from sqlalchemy.dialects.mysql import insert as mysql_insert

            stmt = mysql_insert(UserMessageRead).values(row)
            stmt = stmt.on_duplicate_key_update(read_time=stmt.inserted.read_time)
            await db.execute(stmt)
        await db.flush()

    async def mark_all_read(self, db: AsyncSession, user_id: int) -> int:
        """
        标记全部消息已读

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        stmt = await self.get_select(user_id=user_id, unread_only=True)
        messages: Sequence[UserMessage] = list((await db.execute(stmt)).scalars().all())
        for message in messages:
            await self.mark_read(db, message, user_id)
        return len(messages)


user_message_dao: CRUDUserMessage = CRUDUserMessage(UserMessage)
