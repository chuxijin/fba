#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.plugin.links.model import Domain
from backend.plugin.links.schema import CreateDomainParam, UpdateDomainParam


class CRUDDomain(CRUDPlus[Domain]):
    """域名 CRUD"""

    async def get(self, db: AsyncSession, pk: int) -> Domain | None:
        """
        获取域名详情

        :param db: 数据库会话
        :param pk: 域名ID
        :return:
        """
        return await self.select_model(db, pk)

    async def get_by_domain(self, db: AsyncSession, domain: str) -> Domain | None:
        """
        通过域名获取记录

        :param db: 数据库会话
        :param domain: 域名
        :return:
        """
        return await self.select_model_by_column(db, domain=domain)

    def get_select(
        self,
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
        filters = {}
        if domain_type is not None:
            filters['domain_type'] = domain_type

        stmt = select(self.model).filter_by(**filters)
        if domain:
            stmt = stmt.where(self.model.domain.ilike(f'%{domain}%'))
        stmt = stmt.order_by(self.model.created_time.desc())
        return stmt

    async def get_by_type(self, db: AsyncSession, domain_type: int) -> list[Domain]:
        """
        获取指定类型的所有域名

        :param db: 数据库会话
        :param domain_type: 域名类型(1入口 2中转 3落地)
        :return:
        """
        stmt = select(self.model).where(self.model.domain_type == domain_type)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def create(self, db: AsyncSession, obj: CreateDomainParam, created_by: int) -> Domain:
        """
        创建域名

        :param db: 数据库会话
        :param obj: 创建参数
        :param created_by: 创建者ID
        :return:
        """
        domain = Domain(
            domain=obj.domain,
            domain_type=obj.domain_type,
            remark=obj.remark,
            created_by=created_by,
        )
        db.add(domain)
        await db.flush()
        await db.refresh(domain)
        return domain

    async def update(self, db: AsyncSession, pk: int, obj: UpdateDomainParam) -> int:
        """
        更新域名

        :param db: 数据库会话
        :param pk: 域名ID
        :param obj: 更新参数
        :return:
        """
        return await self.update_model(db, pk, obj)

    async def delete(self, db: AsyncSession, pk: int) -> int:
        """
        删除域名

        :param db: 数据库会话
        :param pk: 域名ID
        :return:
        """
        return await self.delete_model(db, pk)

    async def check_domain_exists(self, db: AsyncSession, domain: str) -> bool:
        """
        检查域名是否存在

        :param db: 数据库会话
        :param domain: 域名
        :return:
        """
        result = await self.select_model_by_column(db, domain=domain)
        return result is not None


domain_dao: CRUDDomain = CRUDDomain(Domain)
