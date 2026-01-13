#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.exception import errors
from backend.plugin.links.crud import domain_dao
from backend.plugin.links.model import Domain
from backend.plugin.links.schema import CreateDomainParam, UpdateDomainParam


class DomainService:
    """域名服务"""

    @staticmethod
    async def get(*, db: AsyncSession, pk: int) -> Domain:
        """
        获取域名详情

        :param db: 数据库会话
        :param pk: 域名ID
        :return:
        """
        domain = await domain_dao.get(db, pk)
        if not domain:
            raise errors.NotFoundError(msg='域名不存在')
        return domain

    @staticmethod
    def get_select(
        *,
        domain: str | None = None,
        domain_type: int | None = None,
    ) -> Select:
        """
        获取域名列表查询

        :param domain: 域名模糊搜索
        :param domain_type: 域名类型筛选
        :return:
        """
        return domain_dao.get_select(domain=domain, domain_type=domain_type)

    @staticmethod
    async def get_by_type(*, db: AsyncSession, domain_type: int) -> list[Domain]:
        """
        获取指定类型的所有域名

        :param db: 数据库会话
        :param domain_type: 域名类型(1入口 2中转 3落地)
        :return:
        """
        return await domain_dao.get_by_type(db, domain_type)

    @staticmethod
    async def create(*, db: AsyncSession, obj: CreateDomainParam, created_by: int) -> Domain:
        """
        创建域名

        :param db: 数据库会话
        :param obj: 创建参数
        :param created_by: 创建者ID
        :return:
        """
        if await domain_dao.check_domain_exists(db, obj.domain):
            raise errors.RequestError(msg='域名已存在')
        return await domain_dao.create(db, obj, created_by)

    @staticmethod
    async def update(*, db: AsyncSession, pk: int, obj: UpdateDomainParam) -> int:
        """
        更新域名

        :param db: 数据库会话
        :param pk: 域名ID
        :param obj: 更新参数
        :return:
        """
        domain = await domain_dao.get(db, pk)
        if not domain:
            raise errors.NotFoundError(msg='域名不存在')

        # 如果修改了域名，检查新域名是否已存在
        if obj.domain and obj.domain != domain.domain:
            if await domain_dao.check_domain_exists(db, obj.domain):
                raise errors.RequestError(msg='域名已存在')

        return await domain_dao.update(db, pk, obj)

    @staticmethod
    async def delete(*, db: AsyncSession, pk: int) -> int:
        """
        删除域名

        :param db: 数据库会话
        :param pk: 域名ID
        :return:
        """
        domain = await domain_dao.get(db, pk)
        if not domain:
            raise errors.NotFoundError(msg='域名不存在')
        return await domain_dao.delete(db, pk)


domain_service: DomainService = DomainService()
