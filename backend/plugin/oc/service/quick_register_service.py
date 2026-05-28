"""快速注册服务"""

import random

import bcrypt
from sqlalchemy import select, insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.admin.model import User, user_role
from backend.app.admin.schema.user import AddUserRoleParam
from backend.app.admin.utils.password_security import get_hash_password
from backend.common.exception import errors
from backend.plugin.oc.schema.quick_register import QuickRegisterParam, QuickRegisterResponse


# OC 默认部门和角色 ID（已在数据库中创建）
OC_DEPT_ID = 5   # OC 部门
OC_ROLE_ID = 14  # OC普通用户


class QuickRegisterService:
    """快速注册服务"""

    @staticmethod
    async def check_user_exists(db: AsyncSession, phone: str) -> bool:
        """检查用户是否已存在（通过用户名/手机号）"""
        stmt = select(User).where((User.username == phone) | (User.phone == phone))
        result = await db.execute(stmt)
        return result.scalars().first() is not None

    async def quick_register(self, db: AsyncSession, obj: QuickRegisterParam) -> QuickRegisterResponse:
        """
        快速注册用户

        :param db: 数据库会话
        :param obj: 注册参数（手机号）
        :return: 注册结果
        """
        # 检查是否已注册
        if await self.check_user_exists(db, obj.phone):
            raise errors.ConflictError(msg='该手机号已注册')

        # 生成用户信息
        username = obj.phone
        password = obj.phone  # 原始密码
        nickname = f'用户#{random.randrange(10000, 99999)}'

        # 加密密码
        salt = bcrypt.gensalt()
        hashed_password = get_hash_password(password, salt)

        # 创建用户
        new_user = User(
            username=username,
            password=hashed_password,
            salt=salt,
            nickname=nickname,
            phone=obj.phone,
            dept_id=OC_DEPT_ID,
            status=1,  # 正常状态
            is_superuser=False,
            is_staff=False,
            is_multi_login=False,
        )
        db.add(new_user)
        await db.flush()

        # 关联角色
        user_role_stmt = insert(user_role).values(
            AddUserRoleParam(user_id=new_user.id, role_id=OC_ROLE_ID).model_dump()
        )
        await db.execute(user_role_stmt)

        # 提交事务
        await db.commit()

        return QuickRegisterResponse(
            username=username,
            password=password,  # 返回明文密码供测试
            message='注册成功'
        )


quick_register_service: QuickRegisterService = QuickRegisterService()
