#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import Select, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.plugin.links.model import Log
from backend.plugin.links.schema import CreateLogParam
from backend.utils.timezone import timezone


class CRUDLog(CRUDPlus[Log]):
    """访问日志 CRUD"""

    async def get(self, db: AsyncSession, pk: int) -> Log | None:
        """
        获取日志详情

        :param db: 数据库会话
        :param pk: 日志ID
        :return:
        """
        return await self.select_model(db, pk)

    def get_select(
        self,
        *,
        log_type: int | None = None,
        target_id: int | None = None,
        device: str | None = None,
        reference: str | None = None,
    ) -> Select:
        """
        获取日志列表查询

        :param log_type: 类型筛选(1短链 2群活码 3客服码)
        :param target_id: 目标ID筛选
        :param device: 设备筛选
        :param reference: 来源筛选
        :return:
        """
        filters = {}
        if log_type is not None:
            filters['type'] = log_type
        if target_id is not None:
            filters['target_id'] = target_id
        if device is not None:
            filters['device'] = device
        if reference is not None:
            filters['reference'] = reference

        stmt = select(self.model).filter_by(**filters).order_by(self.model.created_time.desc())
        return stmt

    async def get_by_target(
        self,
        db: AsyncSession,
        log_type: int,
        target_id: int,
        *,
        limit: int = 100,
    ) -> list[Log]:
        """
        获取目标的访问日志

        :param db: 数据库会话
        :param log_type: 类型(1短链 2群活码 3客服码)
        :param target_id: 目标ID
        :param limit: 返回数量限制
        :return:
        """
        stmt = (
            select(self.model)
            .where(self.model.type == log_type)
            .where(self.model.target_id == target_id)
            .order_by(self.model.created_time.desc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def find_existing(
        self,
        db: AsyncSession,
        log_type: int,
        target_id: int,
        ip: str | None,
        device: str | None,
        reference: str | None,
    ) -> Log | None:
        """
        查找已存在的访问记录（用于 PV 累加）

        :param db: 数据库会话
        :param log_type: 类型(1短链 2群活码 3客服码)
        :param target_id: 目标ID
        :param ip: IP 地址
        :param device: 设备类型
        :param reference: 来源
        :return:
        """
        stmt = (
            select(self.model)
            .where(self.model.type == log_type)
            .where(self.model.target_id == target_id)
            .where(self.model.ip == ip)
            .where(self.model.device == device)
            .where(self.model.reference == reference)
        )
        result = await db.execute(stmt)
        return result.scalars().first()

    async def increment_pv(self, db: AsyncSession, log_id: int) -> None:
        """
        累加访问量

        :param db: 数据库会话
        :param log_id: 日志ID
        :return:
        """
        stmt = update(self.model).where(self.model.id == log_id).values(pv=self.model.pv + 1)
        await db.execute(stmt)

    async def create(self, db: AsyncSession, obj: CreateLogParam, created_by: int = 0) -> Log:
        """
        创建访问日志（自动去重，相同访客累加 PV）

        :param db: 数据库会话
        :param obj: 创建参数
        :param created_by: 创建者ID(匿名访问为0)
        :return:
        """
        # 查找已存在的记录
        existing = await self.find_existing(
            db,
            log_type=obj.type,
            target_id=obj.target_id,
            ip=obj.ip,
            device=obj.device,
            reference=obj.reference,
        )

        if existing:
            # 累加 PV
            await self.increment_pv(db, existing.id)
            await db.refresh(existing)
            return existing

        # 新建记录
        log = Log(
            type=obj.type,
            target_id=obj.target_id,
            ip=obj.ip,
            device=obj.device,
            reference=obj.reference,
            user_agent=obj.user_agent,
            country=obj.country,
            city=obj.city,
            pv=1,
            created_by=created_by,
        )
        db.add(log)
        await db.flush()
        await db.refresh(log)
        return log

    async def count_total(self, db: AsyncSession, log_type: int, target_id: int) -> int:
        """
        统计总访问量

        :param db: 数据库会话
        :param log_type: 类型(1短链 2群活码 3客服码)
        :param target_id: 目标ID
        :return:
        """
        stmt = (
            select(func.sum(self.model.pv))
            .where(self.model.type == log_type)
            .where(self.model.target_id == target_id)
        )
        result = await db.execute(stmt)
        return result.scalar() or 0

    async def count_today(self, db: AsyncSession, log_type: int, target_id: int) -> int:
        """
        统计今日访问量

        :param db: 数据库会话
        :param log_type: 类型(1短链 2群活码 3客服码)
        :param target_id: 目标ID
        :return:
        """
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        stmt = (
            select(func.sum(self.model.pv))
            .where(self.model.type == log_type)
            .where(self.model.target_id == target_id)
            .where(self.model.created_time >= today_start)
        )
        result = await db.execute(stmt)
        return result.scalar() or 0

    async def get_device_stats(self, db: AsyncSession, log_type: int, target_id: int) -> dict[str, int]:
        """
        获取设备访问统计

        :param db: 数据库会话
        :param log_type: 类型(1短链 2群活码 3客服码)
        :param target_id: 目标ID
        :return:
        """
        stmt = (
            select(self.model.device, func.sum(self.model.pv).label('count'))
            .where(self.model.type == log_type)
            .where(self.model.target_id == target_id)
            .where(self.model.device.isnot(None))
            .group_by(self.model.device)
        )
        result = await db.execute(stmt)
        rows = result.all()
        return {row.device: row.count for row in rows}

    async def get_reference_stats(self, db: AsyncSession, log_type: int, target_id: int) -> dict[str, int]:
        """
        获取来源访问统计

        :param db: 数据库会话
        :param log_type: 类型(1短链 2群活码 3客服码)
        :param target_id: 目标ID
        :return:
        """
        stmt = (
            select(self.model.reference, func.sum(self.model.pv).label('count'))
            .where(self.model.type == log_type)
            .where(self.model.target_id == target_id)
            .where(self.model.reference.isnot(None))
            .group_by(self.model.reference)
        )
        result = await db.execute(stmt)
        rows = result.all()
        return {row.reference: row.count for row in rows}

    async def delete_by_target(self, db: AsyncSession, log_type: int, target_id: int) -> int:
        """
        删除目标的所有访问日志

        :param db: 数据库会话
        :param log_type: 类型(1短链 2群活码 3客服码)
        :param target_id: 目标ID
        :return:
        """
        return await self.delete_model_by_column(db, type=log_type, target_id=target_id)


log_dao: CRUDLog = CRUDLog(Log)
