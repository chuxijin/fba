#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import Select, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.plugin.links.model import Kf, KfItem
from backend.plugin.links.schema import (
    CreateKfItemParam,
    CreateKfParam,
    UpdateKfItemParam,
    UpdateKfParam,
)


class CRUDKf(CRUDPlus[Kf]):
    """客服码 CRUD"""

    async def get(self, db: AsyncSession, pk: int) -> Kf | None:
        """
        获取客服码详情

        :param db: 数据库会话
        :param pk: 客服码ID
        :return:
        """
        return await self.select_model(db, pk)

    async def get_by_code(self, db: AsyncSession, code: str) -> Kf | None:
        """
        通过客服码Key获取客服码

        :param db: 数据库会话
        :param code: 客服码Key
        :return:
        """
        return await self.select_model_by_column(db, code=code)

    def get_select(
        self,
        *,
        title: str | None = None,
        status: int | None = None,
        created_by: int | None = None,
    ) -> Select:
        """
        获取客服码列表查询

        :param title: 标题模糊搜索
        :param status: 状态筛选
        :param created_by: 创建者筛选
        :return:
        """
        filters = {}
        if status is not None:
            filters['status'] = status
        if created_by is not None:
            filters['created_by'] = created_by

        stmt = select(self.model).filter_by(**filters)
        if title:
            stmt = stmt.where(self.model.title.ilike(f'%{title}%'))
        stmt = stmt.order_by(self.model.created_time.desc())
        return stmt

    async def create(self, db: AsyncSession, obj: CreateKfParam, code: str, created_by: int) -> Kf:
        """
        创建客服码

        :param db: 数据库会话
        :param obj: 创建参数
        :param code: 生成的客服码Key
        :param created_by: 创建者ID
        :return:
        """
        kf = Kf(
            code=code,
            title=obj.title,
            remark=obj.remark,
            online=obj.online,
            entry_domain=obj.entry_domain,
            redirect_domain=obj.redirect_domain,
            landing_domain=obj.landing_domain,
            created_by=created_by,
        )
        db.add(kf)
        await db.flush()
        await db.refresh(kf)
        return kf

    async def update(self, db: AsyncSession, pk: int, obj: UpdateKfParam) -> int:
        """
        更新客服码

        :param db: 数据库会话
        :param pk: 客服码ID
        :param obj: 更新参数
        :return:
        """
        return await self.update_model(db, pk, obj)

    async def delete(self, db: AsyncSession, pk: int) -> int:
        """
        删除客服码

        :param db: 数据库会话
        :param pk: 客服码ID
        :return:
        """
        return await self.delete_model(db, pk)

    async def increment_clicks(self, db: AsyncSession, pk: int) -> None:
        """
        增加访问量

        :param db: 数据库会话
        :param pk: 客服码ID
        :return:
        """
        stmt = update(self.model).where(self.model.id == pk).values(clicks=self.model.clicks + 1)
        await db.execute(stmt)

    async def check_code_exists(self, db: AsyncSession, code: str) -> bool:
        """
        检查客服码Key是否存在

        :param db: 数据库会话
        :param code: 客服码Key
        :return:
        """
        result = await self.select_model_by_column(db, code=code)
        return result is not None


class CRUDKfItem(CRUDPlus[KfItem]):
    """客服码子项 CRUD"""

    async def get(self, db: AsyncSession, pk: int) -> KfItem | None:
        """
        获取客服码子项详情

        :param db: 数据库会话
        :param pk: 子项ID
        :return:
        """
        return await self.select_model(db, pk)

    async def get_by_kf_id(self, db: AsyncSession, kf_id: int) -> list[KfItem]:
        """
        获取客服码的所有子项

        :param db: 数据库会话
        :param kf_id: 客服码ID
        :return:
        """
        stmt = (
            select(self.model)
            .where(self.model.kf_id == kf_id)
            .order_by(self.model.created_time.desc())
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_available_item(self, db: AsyncSession, kf_id: int) -> KfItem | None:
        """
        获取可用的客服二维码(未满且启用)

        :param db: 数据库会话
        :param kf_id: 客服码ID
        :return:
        """
        stmt = (
            select(self.model)
            .where(self.model.kf_id == kf_id)
            .where(self.model.status == 1)
            .where(self.model.clicks < self.model.limit)
            .order_by(self.model.clicks.asc())
            .limit(1)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, db: AsyncSession, obj: CreateKfItemParam, created_by: int) -> KfItem:
        """
        创建客服码子项

        :param db: 数据库会话
        :param obj: 创建参数
        :param created_by: 创建者ID
        :return:
        """
        item = KfItem(
            kf_id=obj.kf_id,
            qrcode=obj.qrcode,
            limit=obj.limit,
            leader=obj.leader,
            created_by=created_by,
        )
        db.add(item)
        await db.flush()
        await db.refresh(item)
        return item

    async def update(self, db: AsyncSession, pk: int, obj: UpdateKfItemParam) -> int:
        """
        更新客服码子项

        :param db: 数据库会话
        :param pk: 子项ID
        :param obj: 更新参数
        :return:
        """
        return await self.update_model(db, pk, obj)

    async def delete(self, db: AsyncSession, pk: int) -> int:
        """
        删除客服码子项

        :param db: 数据库会话
        :param pk: 子项ID
        :return:
        """
        return await self.delete_model(db, pk)

    async def increment_clicks(self, db: AsyncSession, pk: int) -> None:
        """
        增加访问量

        :param db: 数据库会话
        :param pk: 子项ID
        :return:
        """
        stmt = update(self.model).where(self.model.id == pk).values(clicks=self.model.clicks + 1)
        await db.execute(stmt)

    async def increment_longpress(self, db: AsyncSession, pk: int) -> None:
        """
        增加长按次数

        :param db: 数据库会话
        :param pk: 子项ID
        :return:
        """
        stmt = update(self.model).where(self.model.id == pk).values(longpress=self.model.longpress + 1)
        await db.execute(stmt)

    async def mark_as_full(self, db: AsyncSession, pk: int) -> int:
        """
        标记为已满

        :param db: 数据库会话
        :param pk: 子项ID
        :return:
        """
        stmt = update(self.model).where(self.model.id == pk).values(status=2)
        result = await db.execute(stmt)
        return result.rowcount


kf_dao: CRUDKf = CRUDKf(Kf)
kf_item_dao: CRUDKfItem = CRUDKfItem(KfItem)
