#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.access.crud.crud_domain import study_domain_dao
from backend.app.access.model.domain import StudyDomain
from backend.app.access.schema.domain import CreateStudyDomainParam, UpdateStudyDomainParam
from backend.common.exception import errors


class StudyDomainService:
    """学习领域服务"""

    @staticmethod
    async def get(db: AsyncSession, *, pk: int) -> StudyDomain:
        """
        获取领域详情

        :param db: 数据库会话
        :param pk: 领域 ID
        :return:
        """
        domain = await study_domain_dao.select_model(db, pk)
        if not domain:
            raise errors.NotFoundError(msg='学习领域不存在')
        return domain

    @staticmethod
    async def get_by_code(db: AsyncSession, *, code: str) -> StudyDomain:
        """
        按编码获取领域

        :param db: 数据库会话
        :param code: 领域编码
        :return:
        """
        domain = await study_domain_dao.get_by_code(db, code)
        if not domain:
            raise errors.NotFoundError(msg=f'学习领域不存在: {code}')
        return domain

    @staticmethod
    async def get_select(*, keyword: str | None = None) -> Select:
        """
        获取分页查询语句

        :param keyword: 关键字
        :return:
        """
        return await study_domain_dao.get_select(keyword=keyword)

    @staticmethod
    async def create(db: AsyncSession, *, obj: CreateStudyDomainParam) -> None:
        """
        创建领域

        :param db: 数据库会话
        :param obj: 创建参数
        :return:
        """
        existing = await study_domain_dao.get_by_code(db, obj.code)
        if existing:
            raise errors.ConflictError(msg='领域编码已存在')
        if obj.parent_id is not None:
            await StudyDomainService.get(db, pk=obj.parent_id)
        await study_domain_dao.create_model(db, obj)

    @staticmethod
    async def update(db: AsyncSession, *, pk: int, obj: UpdateStudyDomainParam) -> int:
        """
        更新领域

        :param db: 数据库会话
        :param pk: 领域 ID
        :param obj: 更新参数
        :return:
        """
        await StudyDomainService.get(db, pk=pk)
        if obj.parent_id is not None:
            if obj.parent_id == pk:
                raise errors.ForbiddenError(msg='禁止将领域挂到自己下')
            await StudyDomainService.get(db, pk=obj.parent_id)
        return await study_domain_dao.update_model(db, pk, obj)

    @staticmethod
    async def delete(db: AsyncSession, *, pk: int) -> int:
        """
        删除领域

        :param db: 数据库会话
        :param pk: 领域 ID
        :return:
        """
        return await study_domain_dao.delete_model(db, pk)


study_domain_service: StudyDomainService = StudyDomainService()
