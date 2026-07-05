#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.pomodoro.model.setting import PomodoroUserSetting


class CRUDPomodoroSetting(CRUDPlus[PomodoroUserSetting]):
    """番茄设置数据库操作类"""

    async def get_by_user(self, db: AsyncSession, user_id: int) -> PomodoroUserSetting | None:
        """
        获取用户番茄设置

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        return await self.select_model_by_column(db, user_id__eq=user_id)


pomodoro_setting_dao: CRUDPomodoroSetting = CRUDPomodoroSetting(PomodoroUserSetting)
