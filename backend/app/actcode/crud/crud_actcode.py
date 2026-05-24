#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.actcode.model import Actcode, ActcodeBatch, ActcodeUsage
from backend.app.actcode.schema.actcode import CreateBatchParam, RedeemCodeParam


class CRUDActcodeBatchDao(CRUDPlus[ActcodeBatch]):
    """激活码批次数据库操作类"""

    async def get_select(
        self,
        app_id: str | None = None,
        status: int | None = None,
        batch_no: str | None = None,
        reward_type: str | None = None,
    ) -> Select:
        """
        获取批次列表查询表达式

        :param app_id: 应用 ID
        :param status: 状态
        :param batch_no: 批次编号
        :param reward_type: 权益类型
        :return:
        """
        filters = {}

        if app_id is not None:
            filters['app_id__eq'] = app_id
        if status is not None:
            filters['status__eq'] = status
        if batch_no is not None:
            filters['batch_no__like'] = f'%{batch_no}%'
        if reward_type is not None:
            filters['reward_type__eq'] = reward_type

        return await self.select_order('created_time', 'desc', **filters)

    async def get_by_batch_no(self, db: AsyncSession, batch_no: str) -> ActcodeBatch | None:
        """
        根据批次编号获取批次

        :param db: 数据库会话
        :param batch_no: 批次编号
        :return:
        """
        return await self.select_model_by_column(db, batch_no__eq=batch_no)

    async def create(self, db: AsyncSession, obj: CreateBatchParam, batch_no: str) -> ActcodeBatch:
        """
        创建批次

        :param db: 数据库会话
        :param obj: 批次创建参数
        :param batch_no: 批次编号
        :return:
        """
        return await self.create_model(db, obj, batch_no=batch_no, commit=False)

    async def increment_used_count(self, db: AsyncSession, pk: int) -> None:
        """
        增加已使用数量和总数量

        :param db: 数据库会话
        :param pk: 批次 ID
        :return:
        """
        from sqlalchemy import update
        stmt = (
            update(self.model)
            .where(self.model.id == pk)
            .values(used_count=self.model.used_count + 1)
        )
        await db.execute(stmt)


class CRUDActcodeDao(CRUDPlus[Actcode]):
    """激活码数据库操作类"""

    async def get_select(self, batch_id: int | None = None, status: int | None = None) -> Select:
        """
        获取激活码列表查询表达式

        :param batch_id: 批次 ID
        :param status: 状态
        :return:
        """
        filters = {}

        if batch_id is not None:
            filters['batch_id__eq'] = batch_id
        if status is not None:
            filters['status__eq'] = status

        return await self.select_order('created_time', 'desc', **filters)

    async def get_by_code(self, db: AsyncSession, code: str) -> Actcode | None:
        """
        根据激活码获取记录

        :param db: 数据库会话
        :param code: 激活码
        :return:
        """
        return await self.select_model_by_column(db, code__eq=code)

    async def find_code_in_text(self, db: AsyncSession, text: str) -> Actcode | None:
        """
        从用户输入的文本中匹配已存在的激活码

        用 SQL POSITION(code IN :text) 判断激活码是否包含在用户输入中

        :param db: 数据库会话
        :param text: 用户输入的原始文本
        :return: 匹配到的激活码记录，未匹配返回 None
        """
        from sqlalchemy import func, literal

        stmt = (
            select(self.model)
            .where(func.position(self.model.code.op('IN')(literal(text))) > 0)
            .limit(1)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def bulk_create(self, db: AsyncSession, batch_id: int, codes: list[str]) -> None:
        """
        批量创建激活码

        :param db: 数据库会话
        :param batch_id: 批次 ID
        :param codes: 激活码列表
        :return:
        """
        objs = [{'batch_id': batch_id, 'code': code} for code in codes]
        await self.create_models(db, objs, commit=False)

    async def update_status(self, db: AsyncSession, pk: int, status: int, used_count: int) -> None:
        """
        更新激活码状态

        :param db: 数据库会话
        :param pk: 激活码 ID
        :param status: 状态
        :param used_count: 使用次数
        :return:
        """
        await self.update_model(db, pk, {'status': status, 'used_count': used_count}, commit=False)


class CRUDActcodeUsageDao(CRUDPlus[ActcodeUsage]):
    """激活码使用记录数据库操作类"""

    async def get_by_code_id(self, db: AsyncSession, code_id: int) -> ActcodeUsage | None:
        """
        根据激活码 ID 获取使用记录

        :param db: 数据库会话
        :param code_id: 激活码 ID
        :return:
        """
        return await self.select_model_by_column(db, code_id__eq=code_id)

    async def get_select(
        self, app_id: str | None = None, user_id: str | None = None, code_id: int | None = None
    ) -> Select:
        """
        获取使用记录列表查询表达式

        :param app_id: 应用 ID
        :param user_id: 用户 ID
        :param code_id: 激活码 ID
        :return:
        """
        filters = {}

        if app_id is not None:
            filters['app_id__eq'] = app_id
        if user_id is not None:
            filters['user_id__eq'] = user_id
        if code_id is not None:
            filters['code_id__eq'] = code_id

        return await self.select_order('created_time', 'desc', **filters)

    async def create(self, db: AsyncSession, obj: RedeemCodeParam, code_id: int) -> None:
        """
        创建使用记录

        :param db: 数据库会话
        :param obj: 兑换参数（Pydantic 模型）
        :param code_id: 激活码 ID
        :return:
        """
        from backend.app.actcode.model import ActcodeUsage

        usage_record = ActcodeUsage(
            code_id=code_id,
            app_id=obj.app_id,
            user_id=obj.user_id,
            ip_address=obj.ip_address,
            device_info=obj.device_info,
        )
        db.add(usage_record)

    async def check_user_used(self, db: AsyncSession, code_id: int, user_id: str) -> bool:
        """
        检查用户是否使用过激活码

        :param db: 数据库会话
        :param code_id: 激活码 ID
        :param user_id: 用户 ID
        :return:
        """
        result = await self.select_model_by_column(db, code_id__eq=code_id, user_id__eq=user_id)
        return result is not None


actcode_batch_dao: CRUDActcodeBatchDao = CRUDActcodeBatchDao(ActcodeBatch)
actcode_dao: CRUDActcodeDao = CRUDActcodeDao(Actcode)
actcode_usage_dao: CRUDActcodeUsageDao = CRUDActcodeUsageDao(ActcodeUsage)
