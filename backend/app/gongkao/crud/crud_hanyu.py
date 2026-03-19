#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.gongkao.model import GkHanyu
from backend.app.gongkao.schema.hanyu import CreateHanyuParam, HanyuParam, UpdateHanyuParam


class CRUDHanyu(CRUDPlus[GkHanyu]):
    """Hanyu CRUD."""

    async def get(self, db: AsyncSession, pk: int) -> GkHanyu | None:
        """
        获取汉语词汇详情

        :param db: database session
        :param pk: primary key
        :return:
        """
        return await self.select_model(db, pk)

    async def get_by_name(self, db: AsyncSession, name: str, type_: str | None = None) -> GkHanyu | None:
        """
        根据名称获取汉语词汇

        :param db: database session
        :param name: 词语名称
        :param type_: 类型
        :return:
        """
        filters = {'name': name}
        if type_ is not None:
            filters['type'] = type_
        return await self.select_model_by_column(db, **filters)

    async def get_select(self, params: HanyuParam) -> Select:
        """
        构建汉语词汇列表查询

        :param params: query params
        :return:
        """
        from sqlalchemy import select

        se = select(self.model).order_by(
            self.model.frequency.desc(),
            self.model.created_time.desc(),
        )

        if params.type is not None:
            se = se.where(self.model.type == params.type)
        if params.baobian is not None:
            se = se.where(self.model.baobian == params.baobian)
        if params.structure is not None:
            se = se.where(self.model.structure == params.structure)
        if params.min_frequency is not None:
            se = se.where(self.model.frequency >= params.min_frequency)
        if params.name:
            se = se.where(self.model.name.ilike(f'%{params.name}%'))

        return se

    async def create(self, db: AsyncSession, obj: CreateHanyuParam, created_by: int) -> GkHanyu:
        """
        创建汉语词汇

        :param db: database session
        :param obj: create payload
        :param created_by: user id
        :return:
        """
        hanyu = await self.create_model(db, obj, created_by=created_by)
        await db.flush()
        await db.refresh(hanyu)
        return hanyu

    async def update(self, db: AsyncSession, pk: int, obj: UpdateHanyuParam, updated_by: int) -> int:
        """
        更新汉语词汇

        :param db: database session
        :param pk: primary key
        :param obj: update payload
        :param updated_by: user id
        :return:
        """
        return await self.update_model(db, pk, obj, updated_by=updated_by)

    async def delete(self, db: AsyncSession, pks: list[int]) -> int:
        """
        删除汉语词汇

        :param db: database session
        :param pks: id list
        :return:
        """
        return await self.delete_model_by_column(db, allow_multiple=True, id__in=pks)

    async def increment_frequency(self, db: AsyncSession, pk: int) -> int:
        """
        增加使用频次

        :param db: database session
        :param pk: primary key
        :return:
        """
        hanyu = await self.get(db, pk)
        if hanyu:
            return await self.update_model(db, pk, {'frequency': hanyu.frequency + 1})
        return 0

    async def get_types(self, db: AsyncSession) -> list[str]:
        """
        获取所有类型

        :param db: database session
        :return:
        """
        from sqlalchemy import select

        stmt = select(GkHanyu.type).where(
            GkHanyu.type.isnot(None)
        ).distinct().order_by(GkHanyu.type)
        result = await db.execute(stmt)
        return [row[0] for row in result.all()]


hanyu_dao: CRUDHanyu = CRUDHanyu(GkHanyu)
