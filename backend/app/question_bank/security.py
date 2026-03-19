from fastapi import Depends
from fastapi import Request
from sqlalchemy.exc import IntegrityError

from backend.app.question_bank.crud.crud_user import user_account_dao
from backend.app.question_bank.model import UserAccount
from backend.common.exception import errors
from backend.common.security.auth_strategy import AuthUser
from backend.database.db import async_db_session


async def ensure_user_account(sys_user_id: int, username: str | None) -> UserAccount:
    """
    确保存在对应的 C 端账户

    :param sys_user_id: 系统用户 ID
    :param username: 用户名
    :return:
    """
    async with async_db_session.begin() as db:
        account = await user_account_dao.get_by_sys_user_id(db, sys_user_id)
        if account:
            return account

        account = UserAccount(user_id=sys_user_id, register_channel='admin')
        db.add(account)
        try:
            await db.flush()
        except IntegrityError:
            await db.rollback()
            account = await user_account_dao.get_by_sys_user_id(db, sys_user_id)
            if account:
                return account
            raise errors.ServerError(msg='创建用户账户失败')

        return account


async def get_current_user(request: Request) -> AuthUser:
    """
    获取当前用户（统一登录）

    :param request: 请求对象
    :return: AuthUser
    """
    # 新格式：从 request.state 获取（由中间件设置）
    if hasattr(request.state, 'auth_user'):
        user: AuthUser = request.state.auth_user
        if user.user_type == 'customer':
            return user
        account = await ensure_user_account(user.user_id, user.username)
        return AuthUser(user_id=account.id, user_type=user.user_type, username=user.username)

    # 旧格式：Admin 用户（向后兼容）
    if hasattr(request, 'user') and request.user:
        legacy_user = request.user
        legacy_id = getattr(legacy_user, 'id', None) or getattr(legacy_user, 'user_id', None)
        legacy_name = getattr(legacy_user, 'username', None)
        if legacy_id:
            account = await ensure_user_account(int(legacy_id), legacy_name)
            return AuthUser(user_id=account.id, user_type='admin', username=legacy_name)

    raise errors.AuthorizationError(msg='未登录')


# 依赖注入快捷方式
DependsCurrentUser = Depends(get_current_user)
