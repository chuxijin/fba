#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence

from typing import Any

import bcrypt

from sqlalchemy import Select, and_, delete, insert, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus, JoinConfig

from backend.app.admin.model import (
    DataRule,
    DataScope,
    Dept,
    Menu,
    Role,
    User,
    data_scope_rule,
    role_data_scope,
    role_menu,
    user_role,
)
from backend.app.admin.schema.user import (
    AddOAuth2UserParam,
    AddUserParam,
    AddUserRoleParam,
    UpdateUserParam,
)
from backend.app.admin.utils.password_security import get_hash_password
from backend.common.exception import errors
from backend.core.conf import settings
from backend.plugin.core import check_plugin_installed
from backend.utils.serializers import select_join_serialize
from backend.utils.timezone import timezone


class CRUDUser(CRUDPlus[User]):
    """用户数据库操作类"""


    @staticmethod
    def _active_user_role_join_condition() -> Any:
        """构建生效用户角色关联条件"""
        now = timezone.now()
        return and_(
            user_role.c.user_id == User.id,
            user_role.c.status == 1,
            or_(user_role.c.valid_from.is_(None), user_role.c.valid_from <= now),
            or_(user_role.c.valid_to.is_(None), user_role.c.valid_to >= now),
        )

    async def get(self, db: AsyncSession, user_id: int) -> User | None:
        """
        获取用户详情

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        return await self.select_model(db, user_id)

    async def get_by_username(self, db: AsyncSession, username: str) -> User | None:
        """
        通过用户名获取用户

        :param db: 数据库会话
        :param username: 用户名
        :return:
        """
        return await self.select_model_by_column(db, username=username)

    async def get_by_username_or_email(self, db: AsyncSession, account: str) -> User | None:
        """
        通过用户名或邮箱获取用户

        :param db: 数据库会话
        :param account: 用户名或邮箱
        :return:
        """
        stmt = select(self.model).where(or_(self.model.username == account, self.model.email == account))
        result = await db.execute(stmt)
        return result.scalars().first()

    async def get_by_phone(self, db: AsyncSession, phone: str) -> User | None:
        """
        通过手机号获取用户

        :param db: 数据库会话
        :param phone: 手机号
        :return:
        """
        return await self.select_model_by_column(db, phone=phone)

    async def get_all_by_usernames(self, db: AsyncSession, usernames: list[str]) -> Sequence[User]:
        """
        通过用户名列表批量获取用户

        :param db: 数据库会话
        :param usernames: 用户名列表
        :return:
        """
        return await self.select_models(db, username__in=usernames)

    async def get_by_nickname(self, db: AsyncSession, nickname: str) -> User | None:
        """
        通过昵称获取用户

        :param db: 数据库会话
        :param nickname: 用户昵称
        :return:
        """
        return await self.select_model_by_column(db, nickname=nickname)

    async def check_email(self, db: AsyncSession, email: str) -> User | None:
        """
        检查邮箱是否已被绑定

        :param db: 数据库会话
        :param email: 电子邮箱
        :return:
        """
        return await self.select_model_by_column(db, email=email)

    async def get_select(self, dept: int | None, username: str | None, phone: str | None, status: int | None) -> Select:
        """
        获取用户列表查询表达式

        :param dept: 部门 ID
        :param username: 用户名
        :param phone: 电话号码
        :param status: 用户状态
        :return:
        """
        filters = {}

        if dept:
            filters['dept_id'] = dept
        if username:
            filters['username__like'] = f'%{username}%'
        if phone:
            filters['phone__like'] = f'%{phone}%'
        if status is not None:
            filters['status'] = status

        return await self.select_order(
            'id',
            'desc',
            join_conditions=[
                JoinConfig(model=Dept, join_on=Dept.id == self.model.dept_id, fill_result=True),
                JoinConfig(model=user_role, join_on=self._active_user_role_join_condition()),
                JoinConfig(model=Role, join_on=Role.id == user_role.c.role_id, fill_result=True),
            ],
            **filters,
        )

    async def add(self, db: AsyncSession, obj: AddUserParam) -> None:
        """
        添加用户

        :param db: 数据库会话
        :param obj: 添加用户参数
        :return:
        """
        salt = bcrypt.gensalt()
        obj.password = get_hash_password(obj.password, salt)

        dict_obj = obj.model_dump(exclude={'roles'})
        dict_obj.update({'salt': salt})
        await self.create_user_with_roles(db, user_data=dict_obj, role_ids=obj.roles)

    async def add_by_oauth2(self, db: AsyncSession, obj: AddOAuth2UserParam) -> None:
        """
        通过 OAuth2 添加用户

        :param db: 数据库会话
        :param obj: 注册用户参数
        :return:
        """
        dict_obj = obj.model_dump()

        salt = bcrypt.gensalt()
        password = obj.password if obj.password else '123456'
        dict_obj.update(
            {
                'password': get_hash_password(password, salt),
                'salt': salt,
            }
        )

        await self.create_user_with_roles(db, user_data=dict_obj)



    async def update(self, db: AsyncSession, user_id: int, obj: UpdateUserParam) -> int:
        """
        更新用户信息

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param obj: 更新用户参数
        :return:
        """
        role_ids = obj.roles
        del obj.roles

        count = await self.update_model(db, user_id, obj)

        user_role_stmt = delete(user_role).where(user_role.c.user_id == user_id)
        await db.execute(user_role_stmt)

        bind_role_ids = list(role_ids)
        if settings.USER_BASE_ROLE_ID not in bind_role_ids:
            bind_role_ids.insert(0, settings.USER_BASE_ROLE_ID)
        await self._bind_roles(db, user_id=user_id, role_ids=bind_role_ids)

        return count

    async def update_login_time(self, db: AsyncSession, username: str) -> int:
        """
        更新用户上次登录时间

        :param db: 数据库会话
        :param username: 用户名
        :return:
        """
        return await self.update_model_by_column(db, {'last_login_time': timezone.now()}, username=username)

    async def update_password_changed_time(self, db: AsyncSession, user_id: int) -> int:
        """
        更新用户上次密码变更时间

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        return await self.update_model(db, user_id, {'last_password_changed_time': timezone.now()})

    async def update_username(self, db: AsyncSession, user_id: int, username: str) -> int:
        """
        更新用户名

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param username: 新用户名
        :return:
        """
        return await self.update_model(db, user_id, {'username': username})

    async def update_nickname(self, db: AsyncSession, user_id: int, nickname: str) -> int:
        """
        更新用户昵称

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param nickname: 用户昵称
        :return:
        """
        return await self.update_model(db, user_id, {'nickname': nickname})

    async def update_avatar(self, db: AsyncSession, user_id: int, avatar: str) -> int:
        """
        更新用户头像

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param avatar: 头像地址
        :return:
        """
        return await self.update_model(db, user_id, {'avatar': avatar})

    async def update_email(self, db: AsyncSession, user_id: int, email: str) -> int:
        """
        更新用户邮箱

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param email: 邮箱
        :return:
        """
        return await self.update_model(db, user_id, {'email': email})

    async def update_phone(self, db: AsyncSession, user_id: int, phone: str) -> int:
        """
        更新用户手机号

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param phone: 手机号
        :return:
        """
        return await self.update_model(db, user_id, {'phone': phone})

    async def reset_password(self, db: AsyncSession, pk: int, password: str) -> int:
        """
        重置用户密码

        :param db: 数据库会话
        :param pk: 用户 ID
        :param password: 新密码
        :return:
        """
        salt = bcrypt.gensalt()
        new_pwd = get_hash_password(password, salt)
        return await self.update_model(db, pk, {'password': new_pwd, 'salt': salt}, flush=True)

    async def set_super(self, db: AsyncSession, user_id: int, *, is_super: bool) -> int:
        """
        设置用户超级管理员状态

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param is_super: 是否超级管理员
        :return:
        """
        return await self.update_model(db, user_id, {'is_superuser': is_super})

    async def set_staff(self, db: AsyncSession, user_id: int, *, is_staff: bool) -> int:
        """
        设置用户后台登录状态

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param is_staff: 是否可登录后台
        :return:
        """
        return await self.update_model(db, user_id, {'is_staff': is_staff})

    async def set_status(self, db: AsyncSession, user_id: int, status: int) -> int:
        """
        设置用户状态

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param status: 状态
        :return:
        """
        return await self.update_model(db, user_id, {'status': status})

    async def set_multi_login(self, db: AsyncSession, user_id: int, *, multi_login: bool) -> int:
        """
        设置用户多端登录状态

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param multi_login: 是否允许多端登录
        :return:
        """
        return await self.update_model(db, user_id, {'is_multi_login': multi_login})

    async def delete(self, db: AsyncSession, user_id: int) -> int:
        """
        删除用户

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        if check_plugin_installed('oauth2'):
            try:
                from backend.plugin.oauth2.crud.crud_user_social import user_social_dao

                await user_social_dao.delete_by_user_id(db, user_id)
            except ImportError:
                raise errors.ServerError(msg='OAuth2 插件用法导入失败，请联系系统管理员')

        user_role_stmt = delete(user_role).where(user_role.c.user_id == user_id)
        await db.execute(user_role_stmt)

        return await self.delete_model(db, user_id)

    async def get_join(
        self,
        db: AsyncSession,
        *,
        user_id: int | None = None,
        username: str | None = None,
    ) -> Any | None:
        """
        获取用户关联信息

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param username: 用户名
        :return:
        """
        filters = {}

        if user_id:
            filters['id'] = user_id
        if username:
            filters['username'] = username

        result = await self.select_models(
            db,
            join_conditions=[
                JoinConfig(model=Dept, join_on=Dept.id == self.model.dept_id, fill_result=True),
                JoinConfig(model=user_role, join_on=self._active_user_role_join_condition()),
                JoinConfig(model=Role, join_on=Role.id == user_role.c.role_id, fill_result=True),
                JoinConfig(model=role_menu, join_on=role_menu.c.role_id == Role.id),
                JoinConfig(model=Menu, join_on=Menu.id == role_menu.c.menu_id, fill_result=True),
                JoinConfig(model=role_data_scope, join_on=role_data_scope.c.role_id == Role.id),
                JoinConfig(model=DataScope, join_on=DataScope.id == role_data_scope.c.data_scope_id, fill_result=True),
                JoinConfig(model=data_scope_rule, join_on=data_scope_rule.c.data_scope_id == DataScope.id),
                JoinConfig(model=DataRule, join_on=DataRule.id == data_scope_rule.c.data_rule_id, fill_result=True),
            ],
            **filters,
        )

        return select_join_serialize(
            result,
            relationships=[
                'User-m2o-Dept',
                'User-m2m-Role',
                'Role-m2m-Menu',
                'Role-m2m-DataScope:scopes',
                'DataScope-m2m-DataRule:rules',
            ],
        )

    async def _get_role_or_error(self, db: AsyncSession, role_id: int) -> Role:
        """
        获取角色

        :param db: 数据库会话
        :param role_id: 角色 ID
        :return:
        """
        role = await db.get(Role, role_id)
        if role is None:
            raise errors.NotFoundError(msg=f'未找到可用角色，role_id={role_id}')
        if role.status != 1:
            raise errors.RequestError(msg=f'角色未启用，role_id={role_id}')
        return role

    async def _bind_roles(self, db: AsyncSession, *, user_id: int, role_ids: list[int]) -> None:
        """
        绑定用户角色

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param role_ids: 角色 ID 列表
        :return:
        """
        unique_role_ids = list(dict.fromkeys(role_ids))
        if not unique_role_ids:
            return

        for role_id in unique_role_ids:
            await self._get_role_or_error(db, role_id)

        user_role_data = [AddUserRoleParam(user_id=user_id, role_id=role_id).model_dump() for role_id in unique_role_ids]
        await db.execute(insert(user_role), user_role_data)

    async def create_user_with_roles(
        self,
        db: AsyncSession,
        *,
        user_data: dict[str, Any],
        role_ids: list[int] | None = None,
        ensure_base_role: bool = True,
    ) -> User:
        """
        创建用户并绑定角色

        :param db: 数据库会话
        :param user_data: 用户字段
        :param role_ids: 额外角色 ID 列表
        :param ensure_base_role: 是否补齐基础角色
        :return:
        """
        bind_role_ids = list(role_ids or [])
        if ensure_base_role and settings.USER_BASE_ROLE_ID not in bind_role_ids:
            bind_role_ids.insert(0, settings.USER_BASE_ROLE_ID)

        new_user = self.model(**user_data)
        db.add(new_user)
        await db.flush()
        await self._bind_roles(db, user_id=new_user.id, role_ids=bind_role_ids)
        return new_user


user_dao: CRUDUser = CRUDUser(User)
