#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.plugin.app_auth.model import AppRedeemCode
from backend.plugin.app_auth.schema.redeem_code import CreateRedeemCodeParam


class CRUDRedeemCode(CRUDPlus[AppRedeemCode]):
    """兑换码数据库操作类"""

    async def get(self, db: AsyncSession, code_id: int) -> AppRedeemCode | None:
        """
        获取兑换码详情

        :param db: 数据库会话
        :param code_id: 兑换码 ID
        :return:
        """
        return await self.select_model(db, code_id)

    async def get_by_code(self, db: AsyncSession, code: str) -> AppRedeemCode | None:
        """
        通过兑换码获取详情

        :param db: 数据库会话
        :param code: 兑换码
        :return:
        """
        return await self.select_model_by_column(db, code=code)

    async def create(self, db: AsyncSession, obj_in: CreateRedeemCodeParam, code: str) -> AppRedeemCode:
        """
        创建兑换码

        :param db: 数据库会话
        :param obj_in: 创建参数
        :param code: 兑换码
        :return:
        """
        # 创建包含兑换码的新模型
        from backend.plugin.app_auth.model import AppRedeemCode
        code_data = obj_in.model_dump()
        code_data['code'] = code
        
        # 直接创建模型实例
        redeem_code = AppRedeemCode(**code_data)
        db.add(redeem_code)
        await db.flush()
        await db.refresh(redeem_code)
        return redeem_code

    async def use_code(self, db: AsyncSession, code_id: int, used_by: str) -> int:
        """
        使用兑换码

        :param db: 数据库会话
        :param code_id: 兑换码 ID
        :param used_by: 使用者
        :return:
        """
        from backend.utils.timezone import timezone
        return await self.update_model(db, code_id, {
            'is_used': True,
            'used_by': used_by,
            'used_time': timezone.now()
        })

    async def delete(self, db: AsyncSession, code_id: int) -> int:
        """删除兑换码"""
        return await self.delete_model(db, code_id)

    async def get_by_application(self, db: AsyncSession, application_id: int, 
                                batch_no: str = None, is_used: bool = None) -> list[AppRedeemCode]:
        """
        获取应用的兑换码列表

        :param db: 数据库会话
        :param application_id: 应用 ID
        :param batch_no: 批次号
        :param is_used: 是否已使用
        :return:
        """
        stmt = select(self.model).where(self.model.application_id == application_id)
        if batch_no:
            stmt = stmt.where(self.model.batch_no == batch_no)
        if is_used is not None:
            stmt = stmt.where(self.model.is_used == is_used)
        stmt = stmt.order_by(self.model.created_time.desc())
        return await self.select_models(db, stmt)

    async def get_list(self, db: AsyncSession, application_id: int = None, 
                      batch_no: str = None, is_used: bool = None) -> list[AppRedeemCode]:
        """获取兑换码列表"""
        stmt = select(self.model)
        if application_id:
            stmt = stmt.where(self.model.application_id == application_id)
        if batch_no:
            stmt = stmt.where(self.model.batch_no == batch_no)
        if is_used is not None:
            stmt = stmt.where(self.model.is_used == is_used)
        stmt = stmt.order_by(self.model.created_time.desc())
        return await self.select_models(db, stmt)

    def get_select(self, application_id: int = None, batch_no: str = None, 
                  is_used: bool = None):
        """
        获取兑换码查询语句

        :param application_id: 应用 ID
        :param batch_no: 批次号
        :param is_used: 是否已使用
        :return:
        """
        stmt = select(self.model)
        if application_id:
            stmt = stmt.where(self.model.application_id == application_id)
        if batch_no:
            stmt = stmt.where(self.model.batch_no == batch_no)
        if is_used is not None:
            stmt = stmt.where(self.model.is_used == is_used)
        stmt = stmt.order_by(self.model.created_time.desc())
        return stmt


redeem_code_dao: CRUDRedeemCode = CRUDRedeemCode(AppRedeemCode)