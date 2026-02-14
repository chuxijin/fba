#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import bcrypt

from sqlalchemy import insert, select

from backend.app.actcode.crud.crud_actcode import actcode_dao
from backend.app.admin.model import user_role
from backend.app.admin.model.user import User
from backend.app.admin.schema.user import AddUserRoleParam
from backend.app.admin.utils.password_security import get_hash_password
from backend.common.exception import errors
from backend.common.log import log
from backend.database.db import async_db_session

# 激活相关常量
DEPT_ID = 3  # 公考运营部门
ROLE_ID = 10  # 公考会员用户角色


class ActivateService:
    """激活服务：通过订单号激活账户"""

    @staticmethod
    async def activate_by_order(
        order_no: str,
        username: str,
        password: str,
    ) -> dict:
        """
        用户通过订单号激活账户

        流程：验证激活码 → 创建用户(dept_id=3) → 关联角色(role_id=10) → 标记激活码已使用

        :param order_no: 订单号（即激活码）
        :param username: 用户自定义用户名
        :param password: 用户自定义密码
        :return:
        """
        async with async_db_session.begin() as db:
            # 1. 查找激活码
            actcode = await actcode_dao.get_by_code(db, order_no)
            if not actcode:
                raise errors.NotFoundError(msg='订单号无效或不存在')

            if actcode.status == 1:
                raise errors.RequestError(msg='该订单号已被激活使用')

            if actcode.status == 2:
                raise errors.RequestError(msg='该订单号已过期')

            # 2. 检查用户名是否已存在
            existing_user = await db.execute(
                select(User).where(User.username == username)
            )
            if existing_user.scalar_one_or_none():
                raise errors.ConflictError(msg='用户名已被使用，请更换')

            # 3. 创建用户
            salt = bcrypt.gensalt()
            hashed_password = get_hash_password(password, salt)

            new_user = User(
                username=username,
                nickname=username,
                password=hashed_password,
                salt=salt,
                dept_id=DEPT_ID,
            )
            db.add(new_user)
            await db.flush()

            # 4. 关联角色
            user_role_data = AddUserRoleParam(user_id=new_user.id, role_id=ROLE_ID).model_dump()
            await db.execute(insert(user_role).values(user_role_data))

            # 5. 标记激活码已使用
            await actcode_dao.update_status(db, actcode.id, status=1, used_count=actcode.used_count + 1)

            log.info(f'用户激活成功: username={username}, order_no={order_no}, user_id={new_user.id}')

            return {
                'username': username,
                'user_id': new_user.id,
                'message': '激活成功，请使用用户名和密码登录',
            }


activate_service: ActivateService = ActivateService()
