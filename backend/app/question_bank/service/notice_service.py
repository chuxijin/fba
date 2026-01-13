#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.question_bank.crud.crud_notice import notice_dao
from backend.app.question_bank.schema.notice import (
    CreateNoticeParam,
    GetActiveNotice,
    GetNoticeDetail,
    UpdateNoticeParam,
)
from backend.common.exception import errors


class NoticeService:
    """通知栏服务类"""

    @staticmethod
    async def get(*, db: AsyncSession, pk: int) -> GetNoticeDetail:
        """
        获取通知详情

        :param db: 数据库会话
        :param pk: 通知 ID
        :return:
        """
        notice = await notice_dao.get(db, pk)
        if not notice:
            raise errors.NotFoundError(msg='通知不存在')
        return GetNoticeDetail.model_validate(notice)

    @staticmethod
    async def get_list(
        *,
        db: AsyncSession,
        status: int | None = None,
        notice_type: str | None = None,
        scene: str | None = None,
    ) -> Sequence[GetNoticeDetail]:
        """
        获取通知列表

        :param db: 数据库会话
        :param status: 状态筛选
        :param notice_type: 通知类型筛选
        :param scene: 展示场景筛选
        :return:
        """
        notices = await notice_dao.get_all(db, status=status, notice_type=notice_type, scene=scene)
        return [GetNoticeDetail.model_validate(notice) for notice in notices]

    @staticmethod
    async def get_active_list(*, db: AsyncSession, scene: str | None = None) -> Sequence[GetActiveNotice]:
        """
        获取启用且在有效期内的通知列表

        :param db: 数据库会话
        :param scene: 展示场景筛选
        :return:
        """
        notices = await notice_dao.get_active_list(db, scene=scene)
        return [GetActiveNotice.model_validate(notice) for notice in notices]

    @staticmethod
    async def create(*, db: AsyncSession, obj_in: CreateNoticeParam) -> None:
        """
        创建通知

        :param db: 数据库会话
        :param obj_in: 创建参数
        :return:
        """
        await notice_dao.create(db, obj_in)

    @staticmethod
    async def update(*, db: AsyncSession, pk: int, obj_in: UpdateNoticeParam) -> int:
        """
        更新通知

        :param db: 数据库会话
        :param pk: 通知 ID
        :param obj_in: 更新参数
        :return:
        """
        notice = await notice_dao.get(db, pk)
        if not notice:
            raise errors.NotFoundError(msg='通知不存在')
        count = await notice_dao.update(db, pk, obj_in)
        return count

    @staticmethod
    async def delete(*, db: AsyncSession, pk: int) -> int:
        """
        删除通知

        :param db: 数据库会话
        :param pk: 通知 ID
        :return:
        """
        notice = await notice_dao.get(db, pk)
        if not notice:
            raise errors.NotFoundError(msg='通知不存在')
        count = await notice_dao.delete(db, pk)
        return count
