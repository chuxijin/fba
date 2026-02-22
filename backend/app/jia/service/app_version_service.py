#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.jia.crud.crud_app_version import app_version_dao
from backend.app.jia.model.app_version import JiaAppVersion
from backend.app.jia.schema.app_version import CreateAppVersionParam
from backend.common.exception import errors


class AppVersionService:
    """应用版本服务类"""

    @staticmethod
    async def get_latest(*, db: AsyncSession, platform: str) -> JiaAppVersion:
        """
        获取最新版本信息

        :param db: 数据库会话
        :param platform: 平台标识(android/ios)
        :return:
        """
        record = await app_version_dao.get_latest_by_platform(db, platform)
        if not record:
            raise errors.NotFoundError(msg=f'{platform} 暂无版本信息')
        return record

    @staticmethod
    async def create_version(*, db: AsyncSession, platform: str, obj: CreateAppVersionParam) -> JiaAppVersion:
        """
        创建新版本记录

        :param db: 数据库会话
        :param platform: 平台标识(android/ios)
        :param obj: 创建参数
        :return:
        """
        await app_version_dao.create(db, obj, platform)
        return await app_version_dao.get_latest_by_platform(db, platform)


app_version_service: AppVersionService = AppVersionService()
