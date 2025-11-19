#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.bili.crud import bili_template_dao
from backend.app.bili.model import BiliTemplate
from backend.app.bili.schema.template import CreateBiliTemplateParam, UpdateBiliTemplateParam
from backend.common.exception import errors


class BiliTemplateService:
    """B 站模板话术服务类"""

    @staticmethod
    async def get(db: AsyncSession, pk: int) -> BiliTemplate:
        """
        获取模板详情

        :param db: 数据库会话
        :param pk: 主键 ID
        :return:
        """
        template = await bili_template_dao.get(db, pk)
        if not template:
            raise errors.NotFoundError(msg='模板不存在')
        return template

    @staticmethod
    async def create(db: AsyncSession, obj: CreateBiliTemplateParam) -> None:
        """
        创建模板

        :param db: 数据库会话
        :param obj: 创建参数
        :return:
        """
        await bili_template_dao.create(db, obj)

    @staticmethod
    async def update(db: AsyncSession, pk: int, obj: UpdateBiliTemplateParam) -> int:
        """
        更新模板

        :param db: 数据库会话
        :param pk: 主键 ID
        :param obj: 更新参数
        :return:
        """
        template = await bili_template_dao.get(db, pk)
        if not template:
            raise errors.NotFoundError(msg='模板不存在')
        count = await bili_template_dao.update(db, pk, obj)
        return count

    @staticmethod
    async def delete(db: AsyncSession, pk: int) -> int:
        """
        删除模板

        :param db: 数据库会话
        :param pk: 主键 ID
        :return:
        """
        template = await bili_template_dao.get(db, pk)
        if not template:
            raise errors.NotFoundError(msg='模板不存在')
        count = await bili_template_dao.delete(db, pk)
        return count


bili_template_service = BiliTemplateService()
