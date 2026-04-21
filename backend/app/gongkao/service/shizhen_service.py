#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.content.model.content import Content
from backend.app.gongkao.schema.shizhen import GetShizhenListDetail
from backend.common.exception import errors
from backend.common.pagination import paging_data

APP_CODE_GONGKAO = 'gongkao'
CONTENT_TYPE_SHIZHEN = 'shizhen'


class ShizhenService:
    @staticmethod
    async def get_list_paged(*, db: AsyncSession, daily_date: str | None = None) -> dict[str, Any]:
        """
        获取时政分页列表

        :param daily_date: 按日期筛选，格式 YYYY-MM-DD
        :return:
        """
        stmt = select(Content).where(
            Content.app_code == APP_CODE_GONGKAO,
            Content.is_published.is_(True),
            Content.extra['content_type'].as_string() == CONTENT_TYPE_SHIZHEN,
        )
        if daily_date:
            stmt = stmt.where(Content.extra['daily_date'].as_string() == daily_date)

        stmt = stmt.order_by(
            Content.extra['daily_date'].as_string().desc().nullslast(),
            Content.created_time.desc(),
        )
        return await paging_data(db, stmt, schema_cls=GetShizhenListDetail)

    @staticmethod
    async def get_with_incr_view(*, db: AsyncSession, pk: int) -> Content:
        """
        获取时政详情并累加浏览量

        :param pk: 时政 ID
        :return:
        """
        stmt = select(Content).where(
            Content.id == pk,
            Content.app_code == APP_CODE_GONGKAO,
        )
        result = await db.execute(stmt)
        content = result.scalar_one_or_none()
        if not content:
            raise errors.NotFoundError(msg='时政不存在')

        content.view_count += 1
        await db.commit()
        return content


shizhen_service = ShizhenService()
