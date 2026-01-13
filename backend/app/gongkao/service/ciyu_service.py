#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.gongkao.crud.crud_ciyu import ciyu_dao
from backend.app.gongkao.model.ciyu import GkCiyu
from backend.app.gongkao.schema.ciyu import (
    CreateCiyuParam,
    DeleteCiyuParam,
    CiyuParam,
    UpdateCiyuParam,
)
from backend.common.exception import errors


class CiyuService:
    """词语服务类"""

    @staticmethod
    async def get(*, db: AsyncSession, pk: int) -> GkCiyu:
        """
        获取词语详情

        :param db: 数据库会话
        :param pk: 词语 ID
        :return:
        """
        ciyu = await ciyu_dao.get(db, pk)
        if not ciyu:
            raise errors.NotFoundError(msg='词语不存在')
        return ciyu

    @staticmethod
    async def get_list(*, db: AsyncSession, params: CiyuParam) -> Sequence[GkCiyu]:
        """
        获取词语列表

        :param db: 数据库会话
        :param params: 查询参数
        :return:
        """
        return await ciyu_dao.get_list(
            db,
            word=params.word,
            category=params.category,
            emotion=params.emotion,
            frequency=params.frequency,
        )

    @staticmethod
    async def create(*, db: AsyncSession, obj: CreateCiyuParam, created_by: int) -> GkCiyu:
        """
        创建词语

        :param db: 数据库会话
        :param obj: 创建参数
        :param created_by: 创建者 ID
        :return:
        """
        ciyu = await ciyu_dao.get_by_word(db, obj.word)
        if ciyu:
            raise errors.ConflictError(msg='词语已存在')
        return await ciyu_dao.create(db, obj, created_by)

    @staticmethod
    async def update(*, db: AsyncSession, pk: int, obj: UpdateCiyuParam, updated_by: int) -> int:
        """
        更新词语

        :param db: 数据库会话
        :param pk: 词语 ID
        :param obj: 更新参数
        :param updated_by: 修改者 ID
        :return:
        """
        ciyu = await ciyu_dao.get(db, pk)
        if not ciyu:
            raise errors.NotFoundError(msg='词语不存在')
        if obj.word and ciyu.word != obj.word:
            existing = await ciyu_dao.get_by_word(db, obj.word)
            if existing:
                raise errors.ConflictError(msg='词语已存在')
        return await ciyu_dao.update(db, pk, obj, updated_by)

    @staticmethod
    async def delete(*, db: AsyncSession, obj: DeleteCiyuParam) -> int:
        """
        删除词语

        :param db: 数据库会话
        :param obj: 删除参数
        :return:
        """
        return await ciyu_dao.delete(db, obj.ids)


ciyu_service: CiyuService = CiyuService()
