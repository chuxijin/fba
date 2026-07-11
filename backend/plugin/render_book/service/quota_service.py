#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.access.schema.engine import Decision
from backend.app.access.service.resource_access_service import resource_access_service
from backend.app.access.service.resource_profiles import RENDER_BOOK_EXPORT_PROFILE_CODE


class RenderBookQuotaService:
    """题本 PDF 权益适配层"""

    async def ensure_quota(
        self,
        db: AsyncSession,
        *,
        user_id: int,
    ) -> Decision:
        """
        生成前权益预检，不扣减

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        return await resource_access_service.ensure(
            db,
            profile_code=RENDER_BOOK_EXPORT_PROFILE_CODE,
            user_id=user_id,
        )

    async def consume_quota(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        source_ref: str,
    ) -> Decision:
        """
        生成开始时预扣权益

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param source_ref: 业务来源引用
        :return:
        """
        return await resource_access_service.consume(
            db,
            profile_code=RENDER_BOOK_EXPORT_PROFILE_CODE,
            user_id=user_id,
            source_ref=source_ref,
        )

    async def refund_quota(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        decision: Decision,
        source_ref: str,
    ) -> None:
        """
        渲染失败后回滚已预扣权益

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param decision: 预扣决策
        :param source_ref: 业务来源引用
        :return:
        """
        await resource_access_service.refund(
            db,
            profile_code=RENDER_BOOK_EXPORT_PROFILE_CODE,
            user_id=user_id,
            decision=decision,
            source_ref=source_ref,
        )


render_book_quota_service: RenderBookQuotaService = RenderBookQuotaService()
