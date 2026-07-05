#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.pomodoro.crud.crud_setting import pomodoro_setting_dao
from backend.app.pomodoro.model.setting import PomodoroUserSetting
from backend.app.pomodoro.schema.setting import CreatePomodoroUserSettingInternal, UpdatePomodoroUserSettingParam


class PomodoroSettingService:
    """番茄设置服务类"""

    @staticmethod
    async def get_or_create(*, db: AsyncSession, user_id: int) -> PomodoroUserSetting:
        """
        获取或创建用户番茄设置

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        setting = await pomodoro_setting_dao.get_by_user(db, user_id)
        if setting:
            return setting

        setting = await pomodoro_setting_dao.create_model(
            db,
            CreatePomodoroUserSettingInternal(user_id=user_id),
            commit=False,
        )
        await db.flush()
        await db.refresh(setting)
        return setting

    @staticmethod
    async def update(
        *,
        db: AsyncSession,
        user_id: int,
        obj: UpdatePomodoroUserSettingParam,
    ) -> PomodoroUserSetting:
        """
        更新用户番茄设置

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param obj: 更新参数
        :return:
        """
        setting = await PomodoroSettingService.get_or_create(db=db, user_id=user_id)
        update_data = obj.model_dump(exclude_unset=True)
        if not update_data:
            return setting

        await pomodoro_setting_dao.update_model(db, setting.id, update_data, commit=False)
        await db.flush()
        await db.refresh(setting)
        return setting


pomodoro_setting_service: PomodoroSettingService = PomodoroSettingService()
