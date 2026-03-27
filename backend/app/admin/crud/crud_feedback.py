#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sqlalchemy as sa
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.admin.model.feedback import Feedback
from backend.app.admin.schema.feedback import CreateFeedbackParam, FeedbackQueryParam


class CRUDFeedback(CRUDPlus[Feedback]):
    """反馈数据库操作类"""

    async def get(self, db: AsyncSession, pk: int) -> Feedback | None:
        """
        获取反馈

        :param db: 数据库会话
        :param pk: 反馈 ID
        :return:
        """
        return await self.select_model(db, pk)

    def get_select(self, params: FeedbackQueryParam) -> Select:
        """
        获取反馈列表查询表达式

        :param params: 查询参数
        :return:
        """
        stmt = select(Feedback).order_by(Feedback.created_time.desc())

        if params.feedback_type is not None:
            stmt = stmt.where(Feedback.feedback_type == params.feedback_type)
        if params.status is not None:
            stmt = stmt.where(Feedback.status == params.status)
        if params.keyword is not None:
            stmt = stmt.where(Feedback.content.like(f'%{params.keyword}%'))
        if params.contact is not None:
            stmt = stmt.where(Feedback.contact.like(f'%{params.contact}%'))
        if params.source_app is not None:
            stmt = stmt.where(Feedback.source_app == params.source_app)
        if params.source_platform is not None:
            stmt = stmt.where(Feedback.source_platform == params.source_platform)
        if params.target_type is not None:
            stmt = stmt.where(Feedback.target_type == params.target_type)
        if params.is_read is True:
            stmt = stmt.where(Feedback.read_time.is_not(None))
        if params.is_read is False:
            stmt = stmt.where(Feedback.read_time.is_(None))

        return stmt

    async def create(
        self,
        db: AsyncSession,
        obj: CreateFeedbackParam,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> Feedback:
        """
        创建反馈

        :param db: 数据库会话
        :param obj: 创建参数
        :param ip_address: IP 地址
        :param user_agent: 用户代理
        :return:
        """
        create_data = obj.model_dump()
        create_data['ip_address'] = ip_address
        create_data['user_agent'] = user_agent[:512] if user_agent else None
        return await self.create_model(db, create_data)

    async def update(self, db: AsyncSession, pk: int, values: dict[str, object]) -> int:
        """
        更新反馈

        :param db: 数据库会话
        :param pk: 反馈 ID
        :param values: 更新字段
        :return:
        """
        return await self.update_model_by_column(db, values, id=pk)

    async def delete_batch(self, db: AsyncSession, ids: list[int]) -> int:
        """
        批量删除反馈

        :param db: 数据库会话
        :param ids: 反馈 ID 列表
        :return:
        """
        return await self.delete_model_by_column(db, allow_multiple=True, id__in=ids)

    async def mark_as_read(self, db: AsyncSession, pk: int) -> int:
        """
        标记反馈已读

        :param db: 数据库会话
        :param pk: 反馈 ID
        :return:
        """
        return await self.update_model_by_column(
            db,
            {'read_time': sa.func.now()},
            id=pk,
            read_time=None,
        )


feedback_dao: CRUDFeedback = CRUDFeedback(Feedback)
