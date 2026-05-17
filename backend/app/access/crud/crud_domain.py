#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.access.model.domain import StudyDomain


class CRUDStudyDomain(CRUDPlus[StudyDomain]):
    """学习领域 CRUD"""

    async def get_by_code(self, db: AsyncSession, code: str) -> StudyDomain | None:
        """
        按编码获取

        :param db: 数据库会话
        :param code: 领域编码
        :return:
        """
        stmt = select(self.model).where(self.model.code == code)
        return (await db.execute(stmt)).scalars().first()

    async def get_select(self, *, keyword: str | None = None) -> Select:
        """
        分页查询语句

        :param keyword: 关键字
        :return:
        """
        filters: dict[str, str] = {}
        if keyword:
            filters['name__like'] = f'%{keyword}%'
        return await self.select_order('display_order', 'asc', **filters)


study_domain_dao: CRUDStudyDomain = CRUDStudyDomain(StudyDomain)
