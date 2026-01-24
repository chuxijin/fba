#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence

from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.gongkao.model.ciyu import GkCiyu
from backend.app.gongkao.schema.ciyu import CreateCiyuParam, UpdateCiyuParam


class CRUDCiyu(CRUDPlus[GkCiyu]):
    """词语数据库操作类"""

    async def get(self, db: AsyncSession, pk: int) -> GkCiyu | None:
        """
        获取词语详情

        :param db: 数据库会话
        :param pk: 主键 ID
        :return:
        """
        return await self.select_model(db, pk)

    async def get_by_word(self, db: AsyncSession, word: str) -> GkCiyu | None:
        """
        通过词语获取

        :param db: 数据库会话
        :param word: 词语
        :return:
        """
        return await self.select_model_by_column(db, word=word)

    async def get_select(
        self,
        word: str | None = None,
        category: str | None = None,
        emotion: str | None = None,
        frequency: int | None = None,
    ) -> Select:
        """
        获取词语列表查询表达式

        :param word: 词语
        :param category: 分类
        :param emotion: 感情色彩
        :param frequency: 考频
        :return:
        """
        filters = {}
        if word is not None:
            filters['word__like'] = f'{word}%'
        if category is not None:
            filters['category'] = category
        if emotion is not None:
            filters['emotion'] = emotion
        if frequency is not None:
            filters['frequency'] = frequency
        return await self.select_order('id', 'desc', **filters)

    async def create(self, db: AsyncSession, obj: CreateCiyuParam, created_by: int) -> GkCiyu:
        """
        创建词语

        :param db: 数据库会话
        :param obj: 创建参数
        :param created_by: 创建者 ID
        :return:
        """
        ciyu = await self.create_model(db, obj, created_by=created_by)
        await db.flush()
        await db.refresh(ciyu)
        return ciyu

    async def update(self, db: AsyncSession, pk: int, obj: UpdateCiyuParam, updated_by: int) -> int:
        """
        更新词语

        :param db: 数据库会话
        :param pk: 主键 ID
        :param obj: 更新参数
        :param updated_by: 修改者 ID
        :return:
        """
        return await self.update_model(db, pk, obj, updated_by=updated_by)

    async def delete(self, db: AsyncSession, pks: list[int]) -> int:
        """
        删除词语

        :param db: 数据库会话
        :param pks: 主键 ID 列表
        :return:
        """
        return await self.delete_model_by_column(db, allow_multiple=True, id__in=pks)

    async def increment_view_count(self, db: AsyncSession, pk: int) -> int:
        """
        增加阅读量

        :param db: 数据库会话
        :param pk: 主键 ID
        :return:
        """
        ciyu = await self.get(db, pk)
        if ciyu:
            return await self.update_model(db, pk, {'view_count': ciyu.view_count + 1})
        return 0

    async def get_hot(self, db: AsyncSession, limit: int = 10) -> Sequence[GkCiyu]:
        """
        获取热门词语（按 view_count 降序排列）

        :param db: 数据库会话
        :param limit: 返回数量
        :return:
        """
        return await self.select_models_order(db, 'view_count', 'desc', limit=limit)


ciyu_dao: CRUDCiyu = CRUDCiyu(GkCiyu)
