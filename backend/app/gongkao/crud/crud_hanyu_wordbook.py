#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.gongkao.model import GkHanyuWordbook


class CRUDHanyuWordbook(CRUDPlus[GkHanyuWordbook]):
    """词语本数据库操作类"""

    async def get(self, db: AsyncSession, pk: int) -> GkHanyuWordbook | None:
        """
        获取词语本详情

        :param db: 数据库会话
        :param pk: 主键 ID
        :return:
        """
        return await self.select_model(db, pk)

    async def get_by_teacher(self, db: AsyncSession, teacher_id: int) -> list[GkHanyuWordbook]:
        """
        获取老师的所有词语本

        :param db: 数据库会话
        :param teacher_id: 老师用户 ID
        :return:
        """
        return await self.select_models(db, teacher_id=teacher_id)


hanyu_wordbook_dao: CRUDHanyuWordbook = CRUDHanyuWordbook(GkHanyuWordbook)
