#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Any

from sqlalchemy import Select

from backend.common.exception import errors
from backend.database.db import async_db_session
from backend.plugin.app_auth.crud.crud_version import CRUDVersion, version_dao
from backend.plugin.app_auth.model.version import AppVersion
from backend.plugin.app_auth.schema.version import CreateVersionParam, GetVersionDetail, UpdateVersionParam


class VersionService:
    """版本服务"""

    @staticmethod
    async def get(pk: int) -> GetVersionDetail:
        """
        获取版本详情
        
        :param pk: 版本ID
        :return:
        """
        async with async_db_session() as db:
            version = await version_dao.get(db, pk)
            if not version:
                raise errors.NotFoundError(msg='版本不存在')
            return GetVersionDetail.model_validate(version)

    @staticmethod
    def get_select(
        application_id: int | None = None,
        version_name: str | None = None,
        is_active: bool | None = None,
    ) -> Select:
        """
        获取版本查询语句
        
        :param application_id: 应用ID
        :param version_name: 版本名称
        :param is_active: 是否启用
        :return:
        """
        return version_dao.get_select(
            application_id=application_id,
            version_name=version_name,
            is_active=is_active,
        )

    @staticmethod
    async def create(obj: CreateVersionParam) -> GetVersionDetail:
        """
        创建版本
        
        :param obj: 版本创建参数
        :return:
        """
        async with async_db_session.begin() as db:
            # 检查应用是否存在
            from backend.plugin.app_auth.crud.crud_application import application_dao
            application = await application_dao.get(db, obj.application_id)
            if not application:
                raise errors.NotFoundError(msg='应用不存在')
            
            # 检查版本号是否重复（暂时跳过，因为没有这个方法）
            # existing_version = await version_dao.get_by_version_code(db, obj.application_id, obj.version_code)
            # if existing_version:
            #     raise errors.ForbiddenError(msg='版本号已存在')
            
            version = await version_dao.create(db, obj_in=obj)
            return GetVersionDetail.model_validate(version)

    @staticmethod
    async def update(pk: int, obj: UpdateVersionParam) -> int:
        """
        更新版本
        
        :param pk: 版本ID
        :param obj: 版本更新参数
        :return:
        """
        async with async_db_session.begin() as db:
            version = await version_dao.get(db, pk)
            if not version:
                raise errors.NotFoundError(msg='版本不存在')
            
            count = await version_dao.update(db, pk, obj)
            return count

    @staticmethod
    async def delete(pk: int) -> int:
        """
        删除版本
        
        :param pk: 版本ID
        :return:
        """
        async with async_db_session.begin() as db:
            version = await version_dao.get(db, pk)
            if not version:
                raise errors.NotFoundError(msg='版本不存在')
            
            count = await version_dao.delete(db, pk)
            return count

    @staticmethod
    async def get_options_by_application(application_id: int) -> list[dict]:
        """
        根据应用获取版本选项
        
        :param application_id: 应用ID
        :return:
        """
        async with async_db_session() as db:
            versions = await version_dao.get_by_application(db, application_id)
            return [
                {
                    'label': f"{version.version_name} ({version.version_code})",
                    'value': version.id,
                    'version_code': version.version_code,
                    'is_latest': version.is_latest,
                }
                for version in versions
            ]


version_service = VersionService() 