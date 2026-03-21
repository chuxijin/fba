#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一认证策略模式

支持多种用户类型的可扩展认证体系
"""
from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.conf import settings
from backend.database.db import async_db_session


class AuthUser(BaseModel):
    """统一的认证用户基类"""

    user_id: int
    user_type: str
    username: str | None = None
    is_authenticated: bool = True

    # 可选的扩展字段
    extra: dict[str, Any] | None = None


class UserLoader(ABC):
    """用户加载器抽象基类"""

    @abstractmethod
    async def load_user(self, db: AsyncSession, user_id: int) -> AuthUser | None:
        """
        加载用户信息

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        pass

    @abstractmethod
    def get_user_type(self) -> str:
        """获取用户类型标识"""
        pass

    @abstractmethod
    def get_redis_prefix(self) -> str:
        """获取 Redis 存储前缀"""
        pass


class AdminUserLoader(UserLoader):
    """管理员用户加载器"""

    def get_user_type(self) -> str:
        return 'admin'

    def get_redis_prefix(self) -> str:
        return settings.TOKEN_REDIS_PREFIX

    async def load_user(self, db: AsyncSession, user_id: int) -> AuthUser | None:
        from backend.app.admin.crud.crud_user import user_dao
        from backend.common.exception import errors

        user = await user_dao.get_with_relation(db, user_id=user_id)
        if not user:
            return None

        if not user.status:
            raise errors.AuthorizationError(msg='用户已被锁定，请联系系统管理员')

        if user.dept_id:
            if not user.dept.status:
                raise errors.AuthorizationError(msg='用户所属部门已被锁定，请联系系统管理员')
            if user.dept.del_flag:
                raise errors.AuthorizationError(msg='用户所属部门已被删除，请联系系统管理员')

        if user.roles:
            role_status = [role.status for role in user.roles]
            if all(status == 0 for status in role_status):
                raise errors.AuthorizationError(msg='用户所属角色已被锁定，请联系系统管理员')

        return AuthUser(
            user_id=user.id,
            user_type='admin',
            username=user.username,
            extra={
                'is_superuser': user.is_superuser,
                'is_staff': user.is_staff,
                'dept_id': user.dept_id,
                'roles': [role.id for role in user.roles] if user.roles else [],
            },
        )


class CustomerUserLoader(UserLoader):
    """客户用户加载器（知识店铺）"""

    def get_user_type(self) -> str:
        return 'customer'

    def get_redis_prefix(self) -> str:
        return f'{settings.TOKEN_REDIS_PREFIX}:customer'

    async def load_user(self, db: AsyncSession, user_id: int) -> AuthUser | None:
        from sqlalchemy import select

        from backend.app.admin.model import User
        from backend.app.auth.crud.crud_social_account import social_account_dao
        from backend.common.exception import errors

        # user_id 现在是 sys_user.id
        stmt = select(User).where(User.id == user_id)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
        if not user:
            return None

        if not user.status:
            raise errors.AuthorizationError(msg='账户已被禁用')

        # 从社交绑定表获取 openid
        open_id = await social_account_dao.get_user_openid(db, user_id, 'wechat_miniapp')

        return AuthUser(
            user_id=user.id,
            user_type='customer',
            username=user.username,
            extra={
                'nickname': user.nickname,
                'open_id': open_id,
            },
        )


# 用户加载器注册表
_USER_LOADERS: dict[str, UserLoader] = {
    'admin': AdminUserLoader(),
    'customer': CustomerUserLoader(),
}


def register_user_loader(user_type: str, loader: UserLoader) -> None:
    """
    注册用户加载器

    :param user_type: 用户类型
    :param loader: 加载器实例
    :return:
    """
    _USER_LOADERS[user_type] = loader


def get_user_loader(user_type: str) -> UserLoader | None:
    """
    获取用户加载器

    :param user_type: 用户类型
    :return:
    """
    return _USER_LOADERS.get(user_type)


async def load_user_by_type(user_type: str, user_id: int) -> AuthUser | None:
    """
    根据用户类型加载用户

    :param user_type: 用户类型
    :param user_id: 用户 ID
    :return:
    """
    loader = get_user_loader(user_type)
    if not loader:
        return None

    async with async_db_session() as db:
        return await loader.load_user(db, user_id)
