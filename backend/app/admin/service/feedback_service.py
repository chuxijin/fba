#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.admin.crud.crud_feedback import feedback_dao
from backend.app.admin.model.feedback import Feedback, FeedbackStatus
from backend.app.admin.schema.feedback import (
    CreateFeedbackParam,
    DeleteFeedbackParam,
    FeedbackQueryParam,
    UpdateFeedbackParam,
)
from backend.common.exception import errors
from backend.common.pagination import paging_data
from backend.utils.timezone import timezone


class FeedbackService:
    """反馈服务类"""

    @staticmethod
    async def create(
        *,
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
        return await feedback_dao.create(
            db=db,
            obj=obj,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    @staticmethod
    async def get_list(*, db: AsyncSession, params: FeedbackQueryParam) -> dict[str, Any]:
        """
        获取反馈分页列表

        :param db: 数据库会话
        :param params: 查询参数
        :return:
        """
        select_stmt = feedback_dao.get_select(params)
        return await paging_data(db, select_stmt)

    @staticmethod
    async def get(*, db: AsyncSession, pk: int, mark_as_read: bool = False) -> Feedback:
        """
        获取反馈详情

        :param db: 数据库会话
        :param pk: 反馈 ID
        :param mark_as_read: 是否标记已读
        :return:
        """
        feedback = await feedback_dao.get(db, pk)
        if not feedback:
            raise errors.NotFoundError(msg='反馈不存在')

        if mark_as_read and feedback.read_time is None:
            await feedback_dao.mark_as_read(db, pk)
            feedback.read_time = timezone.now()

        return feedback

    @staticmethod
    async def update(*, db: AsyncSession, pk: int, obj: UpdateFeedbackParam, handled_by: int) -> int:
        """
        更新反馈

        :param db: 数据库会话
        :param pk: 反馈 ID
        :param obj: 更新参数
        :param handled_by: 处理人 ID
        :return:
        """
        feedback = await feedback_dao.get(db, pk)
        if not feedback:
            raise errors.NotFoundError(msg='反馈不存在')

        update_data = obj.model_dump(exclude_unset=True)
        if not update_data:
            return 0

        if update_data.get('status') == FeedbackStatus.PENDING:
            update_data['handled_by'] = None
            update_data['handled_time'] = None
        else:
            update_data['handled_by'] = handled_by
            update_data['handled_time'] = timezone.now()

        return await feedback_dao.update(db, pk, update_data)

    @staticmethod
    async def delete_batch(*, db: AsyncSession, obj: DeleteFeedbackParam) -> int:
        """
        批量删除反馈

        :param db: 数据库会话
        :param obj: 删除参数
        :return:
        """
        return await feedback_dao.delete_batch(db, obj.ids)


feedback_service: FeedbackService = FeedbackService()
