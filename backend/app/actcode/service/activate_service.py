#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import bcrypt

from sqlalchemy import insert, select

from backend.app.actcode.crud.crud_actcode import actcode_batch_dao, actcode_dao
from backend.app.actcode.model.actcode import ActcodeUsage
from backend.app.admin.model import user_role
from backend.app.admin.model.user import User
from backend.app.admin.schema.user import AddUserRoleParam
from backend.app.admin.utils.password_security import get_hash_password
from backend.common.exception import errors
from backend.common.log import log
from backend.database.db import async_db_session


class ActivateService:
    """激活服务：通过订单号激活账户"""

    @staticmethod
    async def activate_by_order(
        order_input: str,
        username: str,
        password: str,
    ) -> dict:
        """
        用户通过订单号激活账户

        流程：从用户输入中匹配订单号 → 查批次获取权益配置 → 创建用户 → 关联角色 → 写入使用记录 → 标记激活码已使用

        :param order_input: 用户输入的原始文本（可能包含订单号的文段）
        :param username: 用户自定义用户名
        :param password: 用户自定义密码
        :return:
        """
        async with async_db_session.begin() as db:
            # 1. 从用户输入中匹配激活码
            actcode = await actcode_dao.find_code_in_text(db, order_input)
            if not actcode:
                raise errors.NotFoundError(msg='未识别到有效的订单号，请检查输入内容')

            if actcode.status == 1:
                raise errors.RequestError(msg='该订单号已被激活使用')

            if actcode.status == 2:
                raise errors.RequestError(msg='该订单号已过期')

            # 2. 查批次获取权益配置
            batch = await actcode_batch_dao.select_model(db, actcode.batch_id)
            if not batch:
                raise errors.NotFoundError(msg='激活码批次不存在')

            reward_data = batch.reward_data or {}
            dept_id = reward_data.get('dept_id')
            role_id = reward_data.get('role_id')
            if dept_id is None or role_id is None:
                raise errors.RequestError(msg='批次权益配置不完整，缺少 dept_id 或 role_id')

            # 3. 检查用户名是否已存在
            existing_user = await db.execute(
                select(User).where(User.username == username)
            )
            if existing_user.scalar_one_or_none():
                raise errors.ConflictError(msg='用户名已被使用，请更换')

            # 4. 创建用户
            salt = bcrypt.gensalt()
            hashed_password = get_hash_password(password, salt)

            new_user = User(
                username=username,
                nickname=username,
                password=hashed_password,
                salt=salt,
                dept_id=dept_id,
            )
            db.add(new_user)
            await db.flush()

            # 5. 关联角色
            user_role_data = AddUserRoleParam(user_id=new_user.id, role_id=role_id).model_dump()
            await db.execute(insert(user_role).values(user_role_data))

            # 6. 写入激活码使用记录
            usage_record = ActcodeUsage(
                code_id=actcode.id,
                app_id=batch.app_id,
                user_id=str(new_user.id),
            )
            db.add(usage_record)

            # 7. 标记激活码已使用
            await actcode_dao.update_status(db, actcode.id, status=1, used_count=actcode.used_count + 1)

            log.info(f'用户激活成功: username={username}, order_no={actcode.code}, user_id={new_user.id}')

            return {
                'username': username,
                'user_id': new_user.id,
                'order_no': actcode.code,
                'message': '激活成功，请使用用户名和密码登录',
            }

    @staticmethod
    async def verify_order(order_input: str) -> dict:
        """
        验证用户输入中是否包含有效的订单号

        :param order_input: 用户输入的原始文本
        :return: {'valid': bool, 'order_no': str | None, 'message': str}
        """
        if not order_input or not order_input.strip():
            return {'valid': False, 'order_no': None, 'message': '请输入订单号'}

        async with async_db_session() as db:
            actcode = await actcode_dao.find_code_in_text(db, order_input)

        if not actcode:
            return {'valid': False, 'order_no': None, 'message': '未识别到有效的订单号'}

        if actcode.status == 1:
            return {'valid': False, 'order_no': actcode.code, 'message': '该订单号已被激活使用'}

        if actcode.status == 2:
            return {'valid': False, 'order_no': actcode.code, 'message': '该订单号已过期'}

        return {'valid': True, 'order_no': actcode.code, 'message': '订单号有效，可以激活'}


activate_service: ActivateService = ActivateService()

