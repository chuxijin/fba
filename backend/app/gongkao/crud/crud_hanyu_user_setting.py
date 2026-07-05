#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.gongkao.model import GkHanyuUserSetting


class CRUDHanyuUserSetting(CRUDPlus[GkHanyuUserSetting]):
    """用户汉语学习设置数据库操作类"""

    async def get_by_user(self, db: AsyncSession, user_id: int) -> GkHanyuUserSetting | None:
        """
        获取用户学习设置

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        return await self.select_model_by_column(db, user_id__eq=user_id)

    async def get_or_create(self, db: AsyncSession, user_id: int) -> GkHanyuUserSetting:
        """
        获取或创建用户学习设置

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        setting = await self.get_by_user(db, user_id)
        if setting:
            return setting

        setting = GkHanyuUserSetting(user_id=user_id)
        db.add(setting)
        await db.flush()
        await db.commit()
        await db.refresh(setting)
        return setting


hanyu_user_setting_dao: CRUDHanyuUserSetting = CRUDHanyuUserSetting(GkHanyuUserSetting)
