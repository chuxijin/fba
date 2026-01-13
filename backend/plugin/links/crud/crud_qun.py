#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import Select, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.plugin.links.model import Qun, QunItem
from backend.plugin.links.schema import (
    CreateQunItemParam,
    CreateQunParam,
    UpdateQunItemParam,
    UpdateQunParam,
)


class CRUDQun(CRUDPlus[Qun]):
    """群活码 CRUD"""

    async def get(self, db: AsyncSession, pk: int) -> Qun | None:
        """
        获取群活码详情

        :param db: 数据库会话
        :param pk: 群活码ID
        :return:
        """
        return await self.select_model(db, pk)

    async def get_by_code(self, db: AsyncSession, code: str) -> Qun | None:
        """
        通过活码Key获取群活码

        :param db: 数据库会话
        :param code: 活码Key
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
        获取群活码列表查询

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

    async def create(self, db: AsyncSession, obj: CreateQunParam, code: str, created_by: int) -> Qun:
        """
        创建群活码

        :param db: 数据库会话
        :param obj: 创建参数
        :param code: 生成的活码Key
        :param created_by: 创建者ID
        :return:
        """
        qun = Qun(
            code=code,
            title=obj.title,
            remark=obj.remark,
            entry_domain=obj.entry_domain,
            redirect_domain=obj.redirect_domain,
            landing_domain=obj.landing_domain,
            kf=obj.kf,
            kf_status=obj.kf_status,
            created_by=created_by,
        )
        db.add(qun)
        await db.flush()
        await db.refresh(qun)
        return qun

    async def update(self, db: AsyncSession, pk: int, obj: UpdateQunParam) -> int:
        """
        更新群活码

        :param db: 数据库会话
        :param pk: 群活码ID
        :param obj: 更新参数
        :return:
        """
        return await self.update_model(db, pk, obj)

    async def delete(self, db: AsyncSession, pk: int) -> int:
        """
        删除群活码

        :param db: 数据库会话
        :param pk: 群活码ID
        :return:
        """
        return await self.delete_model(db, pk)

    async def increment_clicks(self, db: AsyncSession, pk: int) -> None:
        """
        增加访问量

        :param db: 数据库会话
        :param pk: 群活码ID
        :return:
        """
        stmt = update(self.model).where(self.model.id == pk).values(clicks=self.model.clicks + 1)
        await db.execute(stmt)

    async def check_code_exists(self, db: AsyncSession, code: str) -> bool:
        """
        检查活码Key是否存在

        :param db: 数据库会话
        :param code: 活码Key
        :return:
        """
        result = await self.select_model_by_column(db, code=code)
        return result is not None


class CRUDQunItem(CRUDPlus[QunItem]):
    """群活码子项 CRUD"""

    async def get(self, db: AsyncSession, pk: int) -> QunItem | None:
        """
        获取群活码子项详情

        :param db: 数据库会话
        :param pk: 子项ID
        :return:
        """
        return await self.select_model(db, pk)

    async def get_by_qun_id(self, db: AsyncSession, qun_id: int) -> list[QunItem]:
        """
        获取群活码的所有子项

        :param db: 数据库会话
        :param qun_id: 群活码ID
        :return:
        """
        stmt = (
            select(self.model)
            .where(self.model.qun_id == qun_id)
            .order_by(self.model.created_time.desc())
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_available_item(self, db: AsyncSession, qun_id: int) -> QunItem | None:
        """
        获取可用的群二维码(未满且启用)

        :param db: 数据库会话
        :param qun_id: 群活码ID
        :return:
        """
        stmt = (
            select(self.model)
            .where(self.model.qun_id == qun_id)
            .where(self.model.status == 1)
            .where(self.model.clicks < self.model.limit)
            .order_by(self.model.clicks.asc())
            .limit(1)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, db: AsyncSession, obj: CreateQunItemParam, created_by: int) -> QunItem:
        """
        创建群活码子项

        :param db: 数据库会话
        :param obj: 创建参数
        :param created_by: 创建者ID
        :return:
        """
        item = QunItem(
            qun_id=obj.qun_id,
            qrcode=obj.qrcode,
            limit=obj.limit,
            leader=obj.leader,
            created_by=created_by,
        )
        db.add(item)
        await db.flush()
        await db.refresh(item)
        return item

    async def update(self, db: AsyncSession, pk: int, obj: UpdateQunItemParam) -> int:
        """
        更新群活码子项

        :param db: 数据库会话
        :param pk: 子项ID
        :param obj: 更新参数
        :return:
        """
        return await self.update_model(db, pk, obj)

    async def delete(self, db: AsyncSession, pk: int) -> int:
        """
        删除群活码子项

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


qun_dao: CRUDQun = CRUDQun(Qun)
qun_item_dao: CRUDQunItem = CRUDQunItem(QunItem)
