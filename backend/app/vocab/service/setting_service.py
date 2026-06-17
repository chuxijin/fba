#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.vocab.crud.crud_user_setting import user_setting_dao
from backend.app.vocab.schema.setting import GetSettingDetail, UpdateSettingParam


class SettingService:
    """用户学习设置服务类"""

    @staticmethod
    async def get_setting(*, db: AsyncSession, user_id: int) -> GetSettingDetail:
        """
        获取用户学习设置（不存在则自动创建）

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        setting = await user_setting_dao.get_or_create(db, user_id)
        return GetSettingDetail.model_validate(setting)

    @staticmethod
    async def update_setting(*, db: AsyncSession, user_id: int, obj: UpdateSettingParam) -> GetSettingDetail:
        """
        更新用户学习设置

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param obj: 更新参数
        :return:
        """
        setting = await user_setting_dao.get_or_create(db, user_id)
        update_data = obj.model_dump(exclude_unset=True)
        if update_data:
            await user_setting_dao.update_model(db, setting.id, update_data)
            await db.refresh(setting)
        return GetSettingDetail.model_validate(setting)


setting_service: SettingService = SettingService()
