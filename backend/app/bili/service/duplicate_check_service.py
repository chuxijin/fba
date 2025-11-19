#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.bili.crud import bili_duplicate_check_dao
from backend.app.bili.model import BiliDuplicateCheck
from backend.app.bili.schema.duplicate_check import CreateBiliDuplicateCheckParam, UpdateBiliDuplicateCheckParam
from backend.common.exception import errors
from backend.common.pagination import paging_data


class BiliDuplicateCheckService:
    """B 站用户操作记录服务类"""

    @staticmethod
    async def get(db: AsyncSession, pk: int) -> BiliDuplicateCheck:
        """
        获取操作记录详情

        :param db: 数据库会话
        :param pk: 主键 ID
        :return:
        """
        record = await bili_duplicate_check_dao.get(db, pk)
        if not record:
            raise errors.NotFoundError(msg='操作记录不存在')
        return record

    @staticmethod
    async def create(db: AsyncSession, obj: CreateBiliDuplicateCheckParam) -> None:
        """
        创建操作记录

        :param db: 数据库会话
        :param obj: 创建参数
        :return:
        """
        await bili_duplicate_check_dao.create(db, obj)

    @staticmethod
    async def update(db: AsyncSession, pk: int, obj: UpdateBiliDuplicateCheckParam) -> int:
        """
        更新操作记录

        :param db: 数据库会话
        :param pk: 主键 ID
        :param obj: 更新参数
        :return:
        """
        record = await bili_duplicate_check_dao.get(db, pk)
        if not record:
            raise errors.NotFoundError(msg='操作记录不存在')
        count = await bili_duplicate_check_dao.update(db, pk, obj)
        return count

    @staticmethod
    async def delete(db: AsyncSession, pk: int) -> int:
        """
        删除操作记录

        :param db: 数据库会话
        :param pk: 主键 ID
        :return:
        """
        record = await bili_duplicate_check_dao.get(db, pk)
        if not record:
            raise errors.NotFoundError(msg='操作记录不存在')
        count = await bili_duplicate_check_dao.delete(db, pk)
        return count

    @staticmethod
    async def get_list(
        *,
        db: AsyncSession,
        mid: str | None = None,
        operation_type: str | None = None,
        is_active: bool | None = None,
        work_id: int | None = None,
        execution_log_id: int | None = None,
    ) -> dict[str, Any]:
        """
        分页获取操作记录列表

        :param db: 数据库会话
        :param mid: 用户 MID
        :param operation_type: 操作类型
        :param is_active: 是否主动
        :param work_id: 作品 ID
        :param execution_log_id: 任务执行记录 ID
        :return:
        """
        select_stmt = await bili_duplicate_check_dao.get_select(
            mid=mid, operation_type=operation_type, is_active=is_active, work_id=work_id, execution_log_id=execution_log_id
        )
        return await paging_data(db, select_stmt)


bili_duplicate_check_service = BiliDuplicateCheckService()
