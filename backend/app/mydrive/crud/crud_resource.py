#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from sqlalchemy import Select, and_, case, desc, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.mydrive.model.resource import (
    MyDriveResource,
    MyDriveResourceShare,
    MyDriveResourceViewHistory,
)
from backend.app.mydrive.schema.resource import GetMyDriveResourceListParam


class CRUDMyDriveResource(CRUDPlus[MyDriveResource]):
    """MyDrive 资源 CRUD"""

    async def get(self, db: AsyncSession, pk: int, owner_id: int) -> MyDriveResource | None:
        """
        获取用户资源。

        :param db: 数据库会话
        :param pk: 资源 ID
        :param owner_id: 所属用户 ID
        :return:
        """
        stmt = (
            select(self.model)
            .where(
                self.model.id == pk,
                self.model.owner_id == owner_id,
                self.model.deleted == 0,
            )
            .options(selectinload(self.model.share))
        )
        return (await db.execute(stmt)).scalars().first()

    async def get_select(self, owner_id: int, params: GetMyDriveResourceListParam) -> Select:
        """
        获取资源查询语句。

        :param owner_id: 所属用户 ID
        :param params: 查询参数
        :return:
        """
        stmt = (
            select(self.model)
            .outerjoin(MyDriveResourceShare, MyDriveResourceShare.resource_id == self.model.id)
            .where(self.model.owner_id == owner_id, self.model.deleted == 0)
            .options(selectinload(self.model.share))
        )
        filters = []
        if params.category_id is not None:
            filters.append(self.model.category_id == params.category_id)
        if params.resource_type:
            filters.append(self.model.resource_type == params.resource_type)
        if params.status:
            filters.append(self.model.status == params.status)
        if params.audit_status:
            filters.append(self.model.audit_status == params.audit_status)
        if params.provider:
            filters.append(MyDriveResourceShare.provider == params.provider)
        if params.share_status:
            filters.append(MyDriveResourceShare.share_status == params.share_status)
        if params.keyword:
            keyword = f'%{params.keyword}%'
            filters.append(
                or_(
                    self.model.title.ilike(keyword),
                    self.model.description.ilike(keyword),
                    self.model.org_name.ilike(keyword),
                    MyDriveResourceShare.share_title.ilike(keyword),
                    MyDriveResourceShare.file_name.ilike(keyword),
                )
            )
        if filters:
            stmt = stmt.where(and_(*filters))
        sort_column = {
            'hot': self.model.hot,
            'sort': self.model.sort,
            'view_count': self.model.view_count,
            'search_count': self.model.search_count,
        }.get(params.sort_by, self.model.created_time)
        if params.sort_order == 'asc':
            return stmt.order_by(sort_column, desc(self.model.id))
        return stmt.order_by(desc(sort_column), desc(self.model.id))

    async def increment_view(self, db: AsyncSession, pk: int, owner_id: int, increment: int) -> int:
        """
        增加浏览量。

        :param db: 数据库会话
        :param pk: 资源 ID
        :param owner_id: 所属用户 ID
        :param increment: 增量
        :return:
        """
        stmt = (
            update(self.model)
            .where(self.model.id == pk, self.model.owner_id == owner_id, self.model.deleted == 0)
            .values(
                view_count=self.model.view_count + increment,
                hot=self.model.hot + increment,
                last_viewed_at=datetime.now(),
            )
        )
        return (await db.execute(stmt)).rowcount

    async def increment_search(self, db: AsyncSession, pk: int, owner_id: int, increment: int) -> int:
        """
        增加搜索次数。

        :param db: 数据库会话
        :param pk: 资源 ID
        :param owner_id: 所属用户 ID
        :param increment: 增量
        :return:
        """
        stmt = (
            update(self.model)
            .where(self.model.id == pk, self.model.owner_id == owner_id, self.model.deleted == 0)
            .values(
                search_count=self.model.search_count + increment,
                hot=self.model.hot + increment * 3,
                last_searched_at=datetime.now(),
            )
        )
        return (await db.execute(stmt)).rowcount

    async def get_statistics(self, db: AsyncSession, owner_id: int) -> dict[str, int]:
        """
        获取资源统计。

        :param db: 数据库会话
        :param owner_id: 所属用户 ID
        :return:
        """
        stmt = select(
            func.count(self.model.id).label('total_count'),
            func.coalesce(func.sum(case((self.model.status == 'enabled', 1), else_=0)), 0).label('active_count'),
            func.coalesce(func.sum(self.model.view_count), 0).label('total_views'),
            func.coalesce(func.sum(self.model.search_count), 0).label('total_searches'),
            func.coalesce(func.sum(self.model.hot), 0).label('total_hot'),
        ).where(self.model.owner_id == owner_id, self.model.deleted == 0)
        row = (await db.execute(stmt)).mappings().first() or {}
        return {
            'active_count': int(row.get('active_count') or 0),
            'total_count': int(row.get('total_count') or 0),
            'total_hot': int(row.get('total_hot') or 0),
            'total_searches': int(row.get('total_searches') or 0),
            'total_views': int(row.get('total_views') or 0),
        }

    async def get_public_select(self, params: GetMyDriveResourceListParam) -> Select:
        """
        获取公开资源查询语句（不限 owner_id）。

        :param params: 查询参数
        :return:
        """
        stmt = (
            select(self.model)
            .outerjoin(MyDriveResourceShare, MyDriveResourceShare.resource_id == self.model.id)
            .where(
                self.model.deleted == 0,
                self.model.status == 'enabled',
                self.model.audit_status == 'approved',
                MyDriveResourceShare.deleted == 0,
                MyDriveResourceShare.share_status == 'active',
                MyDriveResourceShare.share_url != '',
            )
            .options(selectinload(self.model.share))
        )
        filters = []
        if params.category_id is not None:
            filters.append(self.model.category_id == params.category_id)
        if params.resource_type:
            filters.append(self.model.resource_type == params.resource_type)
        if params.keyword:
            keyword = f'%{params.keyword}%'
            filters.append(
                or_(
                    self.model.title.ilike(keyword),
                    self.model.description.ilike(keyword),
                    self.model.org_name.ilike(keyword),
                    MyDriveResourceShare.share_title.ilike(keyword),
                    MyDriveResourceShare.file_name.ilike(keyword),
                )
            )
        if filters:
            stmt = stmt.where(and_(*filters))
        sort_column = {
            'hot': self.model.hot,
            'sort': self.model.sort,
            'view_count': self.model.view_count,
            'search_count': self.model.search_count,
        }.get(params.sort_by, self.model.created_time)
        if params.sort_order == 'asc':
            return stmt.order_by(sort_column, desc(self.model.id))
        return stmt.order_by(desc(sort_column), desc(self.model.id))

    async def get_public_hot_list(
        self,
        db: AsyncSession,
        *,
        category_id: int | None = None,
        resource_types: list[str] | None = None,
        limit: int = 20,
    ) -> list[MyDriveResource]:
        """
        获取公开热门资源列表。

        :param db: 数据库会话
        :param category_id: 分类 ID
        :param resource_types: 资源类型列表
        :param limit: 数量限制
        :return:
        """
        stmt = (
            select(self.model)
            .outerjoin(MyDriveResourceShare, MyDriveResourceShare.resource_id == self.model.id)
            .where(
                self.model.deleted == 0,
                self.model.status == 'enabled',
                self.model.audit_status == 'approved',
                MyDriveResourceShare.deleted == 0,
                MyDriveResourceShare.share_status == 'active',
                MyDriveResourceShare.share_url != '',
            )
            .options(selectinload(self.model.share))
        )
        filters = []
        if category_id is not None:
            filters.append(self.model.category_id == category_id)
        if resource_types:
            filters.append(self.model.resource_type.in_(resource_types))
        if filters:
            stmt = stmt.where(and_(*filters))
        return list((await db.execute(stmt.order_by(desc(self.model.hot), desc(self.model.id)).limit(limit))).scalars().all())

    async def get_public(self, db: AsyncSession, pk: int) -> MyDriveResource | None:
        """
        获取公开资源（不限 owner_id）。

        :param db: 数据库会话
        :param pk: 资源 ID
        :return:
        """
        stmt = (
            select(self.model)
            .where(
                self.model.id == pk,
                self.model.deleted == 0,
                self.model.status == 'enabled',
                self.model.audit_status == 'approved',
                MyDriveResourceShare.deleted == 0,
                MyDriveResourceShare.share_status == 'active',
                MyDriveResourceShare.share_url != '',
            )
            .outerjoin(MyDriveResourceShare, MyDriveResourceShare.resource_id == self.model.id)
            .options(selectinload(self.model.share))
        )
        return (await db.execute(stmt)).scalars().first()

    async def public_increment_view(self, db: AsyncSession, pk: int, increment: int) -> int:
        """
        增加公开资源浏览量。

        :param db: 数据库会话
        :param pk: 资源 ID
        :param increment: 增量
        :return:
        """
        stmt = (
            update(self.model)
            .where(
                self.model.id == pk,
                self.model.deleted == 0,
                self.model.status == 'enabled',
                self.model.audit_status == 'approved',
            )
            .values(
                view_count=self.model.view_count + increment,
                hot=self.model.hot + increment,
                last_viewed_at=datetime.now(),
            )
        )
        return (await db.execute(stmt)).rowcount

    async def list_by_temp_policy(self, db: AsyncSession, temp_policy: int) -> list[MyDriveResource]:
        """
        按临时策略获取资源。

        :param db: 数据库会话
        :param temp_policy: 临时策略
        :return:
        """
        stmt = (
            select(self.model)
            .where(
                self.model.temp_policy == temp_policy,
                self.model.status == 'enabled',
                self.model.deleted == 0,
            )
            .options(selectinload(self.model.share))
        )
        return list((await db.execute(stmt)).scalars().all())


class CRUDMyDriveResourceShare(CRUDPlus[MyDriveResourceShare]):
    """MyDrive 资源分享 CRUD"""

    async def get_by_resource_id(self, db: AsyncSession, resource_id: int) -> MyDriveResourceShare | None:
        """按资源 ID 获取分享。"""
        stmt = select(self.model).where(self.model.resource_id == resource_id, self.model.deleted == 0)
        return (await db.execute(stmt)).scalars().first()


class CRUDMyDriveResourceViewHistory(CRUDPlus[MyDriveResourceViewHistory]):
    """MyDrive 资源浏览历史 CRUD"""

    async def get_select(
        self,
        resource_id: int,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> Select:
        """
        获取浏览历史查询语句。

        :param resource_id: 资源 ID
        :param start_time: 开始时间
        :param end_time: 结束时间
        :return:
        """
        stmt = select(self.model).where(self.model.resource_id == resource_id, self.model.deleted == 0)
        if start_time is not None:
            stmt = stmt.where(self.model.record_time >= start_time)
        if end_time is not None:
            stmt = stmt.where(self.model.record_time <= end_time)
        return stmt.order_by(self.model.record_time)


mydrive_resource_dao: CRUDMyDriveResource = CRUDMyDriveResource(MyDriveResource)
mydrive_resource_share_dao: CRUDMyDriveResourceShare = CRUDMyDriveResourceShare(MyDriveResourceShare)
mydrive_resource_view_history_dao: CRUDMyDriveResourceViewHistory = CRUDMyDriveResourceViewHistory(MyDriveResourceViewHistory)
