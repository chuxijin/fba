#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.gongkao.model.user_profile import GkUserProfile
from backend.app.gongkao.schema.user_profile import CreateUserProfileParam, UpdateUserProfileParam


class CRUDUserProfile(CRUDPlus[GkUserProfile]):
    """用户画像数据库操作类"""

    async def get(self, db: AsyncSession, pk: int) -> GkUserProfile | None:
        """
        获取用户画像详情

        :param db: 数据库会话
        :param pk: 主键 ID
        :return:
        """
        return await self.get_model(db, pk)

    async def get_by_user_id(self, db: AsyncSession, user_id: int) -> GkUserProfile | None:
        """
        通过用户 ID 获取画像

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        return await self.get_model_by_column(db, user_id=user_id)

    async def get_select(self, user_id: int | None = None) -> Select:
        """
        获取用户画像列表查询表达式

        :param user_id: 用户 ID
        :return:
        """
        filters = {}
        if user_id is not None:
            filters['user_id'] = user_id
        return await self.select_order('id', 'desc', **filters)

    async def create(self, db: AsyncSession, user_id: int, obj: CreateUserProfileParam) -> GkUserProfile:
        """
        创建用户画像

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param obj: 创建参数
        :return:
        """
        profile_data = obj.model_dump()
        profile = GkUserProfile(**profile_data, user_id=user_id)
        db.add(profile)
        await db.flush()
        await db.refresh(profile)
        return profile

    async def update(self, db: AsyncSession, pk: int, obj: UpdateUserProfileParam) -> int:
        """
        更新用户画像

        :param db: 数据库会话
        :param pk: 主键 ID
        :param obj: 更新参数
        :return:
        """
        return await self.update_model(db, pk, obj)

    async def delete(self, db: AsyncSession, pk: int) -> int:
        """
        删除用户画像

        :param db: 数据库会话
        :param pk: 主键 ID
        :return:
        """
        return await self.delete_model(db, pk)

    async def delete_by_user_id(self, db: AsyncSession, user_id: int) -> int:
        """
        通过用户 ID 删除画像

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        return await self.delete_model_by_column(db, user_id=user_id)


user_profile_dao: CRUDUserProfile = CRUDUserProfile(GkUserProfile)
