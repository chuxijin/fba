#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.exception import errors
from backend.common.security.jwt import superuser_verify
from backend.database.db import async_db_session
from backend.plugin.app_auth.crud import application_dao
from backend.plugin.app_auth.model import AppApplication
from backend.plugin.app_auth.schema.application import CreateApplicationParam, UpdateApplicationParam


class ApplicationService:
    """应用服务类"""

    @staticmethod
    async def create(*, request: Request, obj: CreateApplicationParam) -> AppApplication:
        """
        创建应用

        :param request: FastAPI 请求对象
        :param obj: 创建参数
        :return:
        """
        async with async_db_session.begin() as db:
            superuser_verify(request)
            
            # 检查应用名称是否已存在
            existing_name = await application_dao.get_by_name(db, obj.name)
            if existing_name:
                raise errors.ForbiddenError(msg='应用名称已存在')
            
            # 检查应用标识是否已存在
            existing_key = await application_dao.get_by_app_key(db, obj.app_key)
            if existing_key:
                raise errors.ForbiddenError(msg='应用标识已存在')
            
            return await application_dao.create(db, obj)

    @staticmethod
    async def update(*, request: Request, app_id: int, obj: UpdateApplicationParam) -> int:
        """
        更新应用

        :param request: FastAPI 请求对象
        :param app_id: 应用 ID
        :param obj: 更新参数
        :return:
        """
        async with async_db_session.begin() as db:
            superuser_verify(request)
            
            # 检查应用是否存在
            app = await application_dao.get(db, app_id)
            if not app:
                raise errors.NotFoundError(msg='应用不存在')
            
            # 如果更新名称，检查是否重复
            if obj.name and obj.name != app.name:
                existing_name = await application_dao.get_by_name(db, obj.name)
                if existing_name:
                    raise errors.ForbiddenError(msg='应用名称已存在')
            
            return await application_dao.update(db, app_id, obj)

    @staticmethod
    async def delete(*, request: Request, app_id: int) -> int:
        """
        删除应用

        :param request: FastAPI 请求对象
        :param app_id: 应用 ID
        :return:
        """
        async with async_db_session.begin() as db:
            superuser_verify(request)
            
            app = await application_dao.get(db, app_id)
            if not app:
                raise errors.NotFoundError(msg='应用不存在')
            
            return await application_dao.delete(db, app_id)

    @staticmethod
    async def get(app_id: int) -> AppApplication:
        """
        获取应用详情

        :param app_id: 应用 ID
        :return:
        """
        async with async_db_session() as db:
            app = await application_dao.get(db, app_id)
            if not app:
                raise errors.NotFoundError(msg='应用不存在')
            return app

    @staticmethod
    async def get_list(name: str = None, status: int = None) -> list[AppApplication]:
        """获取应用列表"""
        async with async_db_session() as db:
            return await application_dao.get_list(db, name=name, status=status)

    @staticmethod
    def get_select(name: str = None, app_key: str = None, status: int = None):
        """获取应用查询语句用于分页"""
        return application_dao.get_select(name=name, app_key=app_key, status=status)

    @staticmethod
    async def get_options() -> list[dict]:
        """获取应用选择选项"""
        async with async_db_session() as db:
            apps = await application_dao.get_list(db, status=1)  # 只获取启用的应用
            return [
                {
                    'id': app.id,
                    'name': app.name
                }
                for app in apps
            ]


application_service = ApplicationService()