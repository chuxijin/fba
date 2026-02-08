#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.gongkao.crud.crud_user_profile import user_profile_dao
from backend.app.gongkao.model.user_profile import GkUserProfile
from backend.app.gongkao.schema.user_profile import CreateUserProfileParam, UpdateUserProfileParam
from backend.common.exception import errors


class UserProfileService:
    """用户画像服务类"""

    @staticmethod
    async def get(*, db: AsyncSession, pk: int) -> GkUserProfile:
        """
        获取用户画像详情

        :param db: 数据库会话
        :param pk: 画像 ID
        :return:
        """
        profile = await user_profile_dao.get(db, pk)
        if not profile:
            raise errors.NotFoundError(msg='用户画像不存在')
        return profile

    @staticmethod
    async def get_by_user_id(*, db: AsyncSession, user_id: int) -> GkUserProfile | None:
        """
        通过用户 ID 获取画像

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        return await user_profile_dao.get_by_user_id(db, user_id)

    @staticmethod
    async def get_or_create(*, db: AsyncSession, user_id: int) -> GkUserProfile:
        """
        获取或创建用户画像

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        profile = await user_profile_dao.get_by_user_id(db, user_id)
        if profile:
            return profile
        # 创建空画像
        obj = CreateUserProfileParam()
        return await user_profile_dao.create(db, user_id, obj)

    @staticmethod
    async def create(*, db: AsyncSession, user_id: int, obj: CreateUserProfileParam) -> GkUserProfile:
        """
        创建用户画像

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param obj: 创建参数
        :return:
        """
        existing = await user_profile_dao.get_by_user_id(db, user_id)
        if existing:
            raise errors.ConflictError(msg='用户画像已存在，请使用更新接口')
        return await user_profile_dao.create(db, user_id, obj)

    @staticmethod
    async def update(*, db: AsyncSession, user_id: int, obj: UpdateUserProfileParam) -> int:
        """
        更新用户画像

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param obj: 更新参数
        :return:
        """
        profile = await user_profile_dao.get_by_user_id(db, user_id)
        if not profile:
            raise errors.NotFoundError(msg='用户画像不存在')
        return await user_profile_dao.update(db, profile.id, obj)

    @staticmethod
    async def save(*, db: AsyncSession, user_id: int, obj: CreateUserProfileParam) -> GkUserProfile:
        """
        保存用户画像（存在则更新，不存在则创建）

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param obj: 创建参数
        :return:
        """
        existing = await user_profile_dao.get_by_user_id(db, user_id)
        if existing:
            update_obj = UpdateUserProfileParam(**obj.model_dump())
            await user_profile_dao.update(db, existing.id, update_obj)
            return await user_profile_dao.get(db, existing.id)
        return await user_profile_dao.create(db, user_id, obj)

    @staticmethod
    async def delete(*, db: AsyncSession, user_id: int) -> int:
        """
        删除用户画像

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        profile = await user_profile_dao.get_by_user_id(db, user_id)
        if not profile:
            raise errors.NotFoundError(msg='用户画像不存在')
        return await user_profile_dao.delete(db, profile.id)


user_profile_service: UserProfileService = UserProfileService()
