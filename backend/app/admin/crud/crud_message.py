#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from sqlalchemy import Select, and_, exists, func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.admin.model.message import Message, MessageRead, MessageStatus, MessageTargetType
from backend.app.admin.schema.message import CreateMessageParam, MessageQueryParam
from backend.common.enums import DataBaseType
from backend.core.conf import settings
from backend.utils.timezone import timezone


class CRUDMessage(CRUDPlus[Message]):
    """系统消息数据库操作类"""

    @staticmethod
    def _active_condition(now: datetime):
        """有效期与启用状态条件"""
        return and_(
            Message.status == MessageStatus.ENABLED,
            Message.publish_time <= now,
            or_(Message.expire_time.is_(None), Message.expire_time >= now),
        )

    @staticmethod
    def _visible_condition(user_id: int):
        """
        用户可见范围条件

        TODO: role 定向投递需 join 用户角色后展开，首版仅支持 all/user
        """
        return or_(
            Message.target_type == MessageTargetType.ALL,
            and_(Message.target_type == MessageTargetType.USER, Message.user_id == user_id),
        )

    @staticmethod
    def _read_exists(user_id: int):
        """已读存在性条件（全站/单人/角色统一走已读表）"""
        return exists().where(
            MessageRead.message_id == Message.id,
            MessageRead.user_id == user_id,
        )

    async def get(self, db: AsyncSession, pk: int) -> Message | None:
        """
        获取消息

        :param db: 数据库会话
        :param pk: 消息 ID
        :return:
        """
        return await self.select_model(db, pk)

    def get_select(self, params: MessageQueryParam) -> Select:
        """
        获取管理端消息列表查询表达式

        :param params: 查询参数
        :return:
        """
        stmt = select(Message).order_by(Message.id.desc())

        if params.message_type is not None:
            stmt = stmt.where(Message.message_type == params.message_type)
        if params.target_type is not None:
            stmt = stmt.where(Message.target_type == params.target_type)
        if params.status is not None:
            stmt = stmt.where(Message.status == params.status)
        if params.keyword is not None:
            stmt = stmt.where(
                or_(
                    Message.title.ilike(f'%{params.keyword}%'),
                    Message.content.ilike(f'%{params.keyword}%'),
                )
            )
        if params.biz_source is not None:
            stmt = stmt.where(Message.biz_source == params.biz_source)

        return stmt

    def get_select_for_user(
        self,
        *,
        user_id: int,
        unread_only: bool = False,
        message_type: str | None = None,
    ) -> Select:
        """
        获取用户可见消息查询表达式

        :param user_id: 用户 ID
        :param unread_only: 是否只看未读
        :param message_type: 消息类型
        :return:
        """
        now = timezone.now()
        stmt = (
            select(Message)
            .where(
                self._visible_condition(user_id),
                self._active_condition(now),
            )
            .order_by(Message.publish_time.desc(), Message.id.desc())
        )
        if unread_only:
            stmt = stmt.where(~self._read_exists(user_id))
        if message_type is not None:
            stmt = stmt.where(Message.message_type == message_type)
        return stmt

    async def get_for_user(self, db: AsyncSession, message_id: int, user_id: int) -> Message | None:
        """
        获取用户可见的单条消息

        :param db: 数据库会话
        :param message_id: 消息 ID
        :param user_id: 用户 ID
        :return:
        """
        stmt = self.get_select_for_user(user_id=user_id).where(Message.id == message_id)
        result = await db.execute(stmt)
        return result.scalars().first()

    async def get_read_map(
        self,
        db: AsyncSession,
        user_id: int,
        message_ids: list[int],
    ) -> dict[int, datetime]:
        """
        获取消息已读时间映射

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param message_ids: 消息 ID 列表
        :return:
        """
        if not message_ids:
            return {}

        stmt = select(MessageRead.message_id, MessageRead.read_time).where(
            MessageRead.user_id == user_id,
            MessageRead.message_id.in_(message_ids),
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
        stmt = (
            select(func.count())
            .select_from(Message)
            .where(
                self._visible_condition(user_id),
                self._active_condition(now),
                ~self._read_exists(user_id),
            )
        )
        result = await db.execute(stmt)
        return result.scalar() or 0

    async def create(self, db: AsyncSession, obj: CreateMessageParam, sender_id: int | None = None) -> Message:
        """
        创建消息

        :param db: 数据库会话
        :param obj: 创建参数
        :param sender_id: 发送人 ID
        :return:
        """
        obj_data = obj.model_dump()
        if obj_data.get('publish_time') is None:
            obj_data['publish_time'] = timezone.now()
        message = self.model(**obj_data, sender_id=sender_id)
        db.add(message)
        await db.flush()
        await db.refresh(message)
        return message

    async def update(self, db: AsyncSession, pk: int, values: dict[str, object]) -> int:
        """
        更新消息

        :param db: 数据库会话
        :param pk: 消息 ID
        :param values: 更新字段
        :return:
        """
        return await self.update_model_by_column(db, values, id=pk)

    async def delete_batch(self, db: AsyncSession, ids: list[int]) -> int:
        """
        批量删除消息

        :param db: 数据库会话
        :param ids: 消息 ID 列表
        :return:
        """
        return await self.delete_model_by_column(db, allow_multiple=True, id__in=ids)

    async def mark_read(self, db: AsyncSession, message_id: int, user_id: int) -> None:
        """
        标记消息已读（幂等 upsert）

        :param db: 数据库会话
        :param message_id: 消息 ID
        :param user_id: 用户 ID
        """
        now = timezone.now()
        row = {
            'message_id': message_id,
            'user_id': user_id,
            'read_time': now,
            'created_time': now,
        }
        if DataBaseType.postgresql == settings.DATABASE_TYPE:
            stmt = pg_insert(MessageRead).values(row)
            stmt = stmt.on_conflict_do_nothing(constraint='uq_message_read_message_user')
            await db.execute(stmt)
        else:
            from sqlalchemy.dialects.mysql import insert as mysql_insert

            stmt = mysql_insert(MessageRead).values(row)
            stmt = stmt.on_duplicate_key_update(read_time=MessageRead.read_time)
            await db.execute(stmt)
        await db.flush()

    async def mark_all_read(self, db: AsyncSession, user_id: int) -> int:
        """
        标记全部消息已读

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        stmt = select(Message.id).where(
            self._visible_condition(user_id),
            self._active_condition(timezone.now()),
            ~self._read_exists(user_id),
        )
        message_ids = list((await db.execute(stmt)).scalars().all())
        for message_id in message_ids:
            await self.mark_read(db, message_id, user_id)
        return len(message_ids)


message_dao: CRUDMessage = CRUDMessage(Message)
