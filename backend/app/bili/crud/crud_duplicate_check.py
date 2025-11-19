#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence

from sqlalchemy import Select, desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.bili.model import BiliDuplicateCheck
from backend.app.bili.schema.duplicate_check import CreateBiliDuplicateCheckParam, UpdateBiliDuplicateCheckParam


class CRUDBiliDuplicateCheck(CRUDPlus[BiliDuplicateCheck]):
    """B 站用户操作记录数据库操作类"""

    async def get(self, db: AsyncSession, pk: int) -> BiliDuplicateCheck | None:
        """
        获取操作记录详情

        :param db: 数据库会话
        :param pk: 主键 ID
        :return:
        """
        return await self.select_model(db, pk)

    async def get_by_mid_and_type(
        self, db: AsyncSession, mid: str, operation_type: str
    ) -> Sequence[BiliDuplicateCheck]:
        """
        根据 MID 和操作类型查询记录

        :param db: 数据库会话
        :param mid: 用户 MID
        :param operation_type: 操作类型
        :return:
        """
        return await self.select_models(db, mid=mid, operation_type=operation_type)

    async def get_list(
        self,
        db: AsyncSession,
        mid: str | None = None,
        operation_type: str | None = None,
        is_active: bool | None = None,
        work_id: int | None = None,
    ) -> Sequence[BiliDuplicateCheck]:
        """
        获取操作记录列表

        :param db: 数据库会话
        :param mid: 用户 MID
        :param operation_type: 操作类型
        :param is_active: 是否主动
        :param work_id: 作品 ID
        :return:
        """
        filters = {}
        if mid is not None:
            filters['mid'] = mid
        if operation_type is not None:
            filters['operation_type'] = operation_type
        if is_active is not None:
            filters['is_active'] = is_active
        if work_id is not None:
            filters['work_id'] = work_id
        return await self.select_models_order(db, 'created_time', 'desc', **filters)

    async def create(self, db: AsyncSession, obj: CreateBiliDuplicateCheckParam) -> None:
        """
        创建操作记录

        :param db: 数据库会话
        :param obj: 创建参数
        :return:
        """
        await self.create_model(db, obj)

    async def update(self, db: AsyncSession, pk: int, obj: UpdateBiliDuplicateCheckParam) -> int:
        """
        更新操作记录

        :param db: 数据库会话
        :param pk: 主键 ID
        :param obj: 更新参数
        :return:
        """
        return await self.update_model(db, pk, obj)

    async def delete(self, db: AsyncSession, pk: int) -> int:
        """
        删除操作记录

        :param db: 数据库会话
        :param pk: 主键 ID
        :return:
        """
        return await self.delete_model(db, pk)

    async def get_select(
        self,
        mid: str | None = None,
        operation_type: str | None = None,
        is_active: bool | None = None,
        work_id: int | None = None,
        execution_log_id: int | None = None,
    ) -> Select:
        """
        获取操作记录查询语句

        :param mid: 用户 MID
        :param operation_type: 操作类型
        :param is_active: 是否主动
        :param work_id: 作品 ID
        :param execution_log_id: 任务执行记录 ID
        :return:
        """
        stmt = select(self.model).order_by(desc(self.model.created_time))
        if mid is not None:
            stmt = stmt.where(self.model.mid == mid)
        if operation_type is not None:
            stmt = stmt.where(self.model.operation_type == operation_type)
        if is_active is not None:
            stmt = stmt.where(self.model.is_active == is_active)
        if work_id is not None:
            stmt = stmt.where(self.model.work_id == work_id)
        if execution_log_id is not None:
            stmt = stmt.where(self.model.execution_log_id == execution_log_id)
        return stmt


bili_duplicate_check_dao: CRUDBiliDuplicateCheck = CRUDBiliDuplicateCheck(BiliDuplicateCheck)
