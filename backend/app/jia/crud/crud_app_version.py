#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.jia.model.app_version import JiaAppVersion
from backend.app.jia.schema.app_version import CreateAppVersionParam


class CRUDAppVersion(CRUDPlus[JiaAppVersion]):
    """应用版本数据库操作类"""

    async def get_latest_by_platform(self, db: AsyncSession, platform: str) -> JiaAppVersion | None:
        """
        获取指定平台的最新版本记录（按 build_number 降序）

        :param db: 数据库会话
        :param platform: 平台标识(android/ios)
        :return:
        """
        stmt = select(self.model).where(self.model.platform == platform).order_by(self.model.build_number.desc()).limit(1)
        result = await db.execute(stmt)
        return result.scalars().first()

    async def create(self, db: AsyncSession, obj: CreateAppVersionParam, platform: str) -> None:
        """
        创建版本记录

        :param db: 数据库会话
        :param obj: 创建参数
        :param platform: 平台标识
        :return:
        """
        dict_obj = obj.model_dump()
        dict_obj['platform'] = platform
        await self.create_model(db, dict_obj)


app_version_dao: CRUDAppVersion = CRUDAppVersion(JiaAppVersion)
