from collections.abc import Callable, Sequence
from typing import Any

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.admin.crud.crud_dept import dept_dao
from backend.app.admin.crud.crud_role import role_dao
from backend.app.admin.crud.crud_user import user_dao
from backend.app.admin.model import Role, User
from backend.app.admin.schema.user import (
    AddUserParam,
    ResetPasswordParam,
    UpdateUserParam,
)
from backend.common.events import publish
from backend.app.admin.schema.user_password_history import CreateUserPasswordHistoryParam
from backend.app.admin.service.user_password_history_service import password_security_service
from backend.app.admin.utils.password_security import password_verify, validate_new_password
from backend.common.context import ctx
from backend.common.enums import UserPermissionType
from backend.common.exception import errors
from backend.common.pagination import paging_data
from backend.common.response.response_code import CustomErrorCode
from backend.common.security.jwt import (
    TokenInvalidReason,
    get_token,
    jwt_decode,
    mark_user_refresh_sessions_invalid,
    mark_user_sessions_invalid,
)
from backend.core.conf import settings
from backend.database.redis import redis_client
from backend.utils.sensitive_words import validate_no_sensitive_words
from backend.utils.serializers import select_join_serialize


class UserService:
    """用户服务类"""

    @staticmethod
    async def get_userinfo(*, db: AsyncSession, pk: int | None = None, username: str | None = None) -> User:
        """
        获取用户信息

        :param db: 数据库会话
        :param pk: 用户 ID
        :param username: 用户名
        :return:
        """
        user = await user_dao.get_join(db, user_id=pk, username=username)
        if not user:
            raise errors.NotFoundError(msg='用户不存在')
        return user

    @staticmethod
    async def get_roles(*, db: AsyncSession, pk: int) -> Sequence[Role]:
        """
        获取用户所有角色

        :param db: 数据库会话
        :param pk: 用户 ID
        :return:
        """
        user = await user_dao.get_join(db, user_id=pk)
        if not user:
            raise errors.NotFoundError(msg='用户不存在')
        return user.roles

    @staticmethod
    async def get_list(*, db: AsyncSession, dept: int, username: str, phone: str, status: int) -> dict[str, Any]:
        """
        获取用户列表

        :param db: 数据库会话
        :param dept: 部门 ID
        :param username: 用户名
        :param phone: 手机号
        :param status: 状态
        :return:
        """
        user_select = await user_dao.get_select(dept=dept, username=username, phone=phone, status=status)
        data = await paging_data(db, user_select)
        if data['items']:
            serialized_items = select_join_serialize(data['items'], relationships=['User-m2o-Dept', 'User-m2m-Role'])
            # 确保返回的是列表，即使只有一个元素
            data['items'] = [serialized_items] if not isinstance(serialized_items, list) else serialized_items
        return data

    @staticmethod
    async def create(*, db: AsyncSession, obj: AddUserParam) -> None:
        """
        创建用户

        :param db: 数据库会话
        :param obj: 用户添加参数
        :return:
        """
        if await user_dao.get_by_username(db, obj.username):
            raise errors.ConflictError(msg='用户名已注册')
        if obj.email and await user_dao.check_email(db, obj.email):
            raise errors.ConflictError(msg='邮箱已被绑定')
        if not obj.password:
            raise errors.RequestError(msg='密码不允许为空')
        if not await dept_dao.get(db, obj.dept_id):
            raise errors.NotFoundError(msg='部门不存在')
        if obj.roles:
            roles = await role_dao.get_all_by_ids(db, list(set(obj.roles)))
            if {role.id for role in roles} != set(obj.roles):
                raise errors.NotFoundError(msg='角色不存在')
        obj.nickname = obj.nickname or obj.username
        await user_dao.add(db, obj)

    @staticmethod
    async def register(
        *,
        db: AsyncSession,
        user_data: dict[str, Any],
        role_ids: list[int] | None = None,
        creator: Callable[..., Any] | None = None,
    ) -> User:
        """
        用户注册（自动触发注册事件）

        :param db: 数据库会话
        :param user_data: 用户字段字典
        :param role_ids: 额外角色 ID 列表
        :param creator: 自定义创建函数, 签名 (db, user_data) -> User, 为 None 时使用默认创建
        :return:
        """
        if creator:
            user = await creator(db, user_data)
        else:
            user = await user_dao.create_user_with_roles(db, user_data=user_data, role_ids=role_ids)
            await db.flush()
        await publish('user.registered', user_id=user.id)
        return user

    @staticmethod
    async def update(*, db: AsyncSession, pk: int, obj: UpdateUserParam) -> int:
        """
        更新用户信息

        :param db: 数据库会话
        :param pk: 用户 ID
        :param obj: 用户更新参数
        :return:
        """
        user = await user_dao.get_join(db, user_id=pk)
        if not user:
            raise errors.NotFoundError(msg='用户不存在')
        if obj.username != user.username and await user_dao.get_by_username(db, obj.username):
            raise errors.ConflictError(msg='用户名已注册')
        if obj.email and obj.email != user.email:
            email_user = await user_dao.check_email(db, obj.email)
            if email_user:
                raise errors.ConflictError(msg='邮箱已被绑定')
        if obj.dept_id and obj.dept_id != user.dept_id and not await dept_dao.get(db, dept_id=obj.dept_id):
            raise errors.NotFoundError(msg='部门不存在')
        if obj.roles:
            roles = await role_dao.get_all_by_ids(db, list(set(obj.roles)))
            if {role.id for role in roles} != set(obj.roles):
                raise errors.NotFoundError(msg='角色不存在')
        count = await user_dao.update(db, user.id, obj)
        await redis_client.delete(f'{settings.JWT_USER_REDIS_PREFIX}:{user.id}')
        return count

    @staticmethod
    async def update_permission(*, db: AsyncSession, request: Request, pk: int, type: UserPermissionType) -> int:  # ruff:ignore[complex-structure]
        """
        更新用户权限

        :param db: 数据库会话
        :param request: FastAPI 请求对象
        :param pk: 用户 ID
        :param type: 权限类型
        :return:
        """
        match type:
            case UserPermissionType.superuser:
                user = await user_dao.get(db, pk)
                if not user:
                    raise errors.NotFoundError(msg='用户不存在')
                if pk == request.user.id:
                    raise errors.ForbiddenError(msg='禁止修改自身权限')
                count = await user_dao.set_super(db, pk, is_super=not user.is_superuser)
            case UserPermissionType.staff:
                user = await user_dao.get(db, pk)
                if not user:
                    raise errors.NotFoundError(msg='用户不存在')
                if pk == request.user.id:
                    raise errors.ForbiddenError(msg='禁止修改自身权限')
                count = await user_dao.set_staff(db, pk, is_staff=not user.is_staff)
            case UserPermissionType.status:
                user = await user_dao.get(db, pk)
                if not user:
                    raise errors.NotFoundError(msg='用户不存在')
                if pk == request.user.id:
                    raise errors.ForbiddenError(msg='禁止修改自身权限')
                count = await user_dao.set_status(db, pk, 0 if user.status == 1 else 1)
            case UserPermissionType.multi_login:
                user = await user_dao.get(db, pk)
                if not user:
                    raise errors.NotFoundError(msg='用户不存在')
                multi_login = user.is_multi_login if pk != user.id else request.user.is_multi_login
                new_multi_login = not multi_login
                count = await user_dao.set_multi_login(db, pk, multi_login=new_multi_login)
                token = get_token(request)
                token_payload = jwt_decode(token)
                if pk == user.id:
                    # 系统管理员修改自身时，除当前 token 外，其他 token 失效
                    if not new_multi_login:
                        key_prefix = f'{settings.TOKEN_REDIS_PREFIX}:{user.id}'
                        await mark_user_sessions_invalid(
                            user.id,
                            reason=TokenInvalidReason.permission_changed,
                            exclude_session_uuid=token_payload.session_uuid,
                        )
                        await mark_user_refresh_sessions_invalid(
                            user.id,
                            reason=TokenInvalidReason.permission_changed,
                            exclude_session_uuid=token_payload.session_uuid,
                        )
                        await redis_client.delete_by_prefix(
                            key_prefix,
                            exclude_keys=f'{key_prefix}:{token_payload.session_uuid}',
                        )
                else:
                    # 系统管理员修改他人时，他人 token 全部失效
                    if not new_multi_login:
                        key_prefix = f'{settings.TOKEN_REDIS_PREFIX}:{user.id}'
                        await mark_user_sessions_invalid(user.id, reason=TokenInvalidReason.permission_changed)
                        await mark_user_refresh_sessions_invalid(user.id, reason=TokenInvalidReason.permission_changed)
                        await redis_client.delete_by_prefix(key_prefix)
            case _:
                raise errors.RequestError(msg='权限类型不存在')

        await redis_client.delete(f'{settings.JWT_USER_REDIS_PREFIX}:{user.id}')
        return count

    @staticmethod
    async def reset_password(*, db: AsyncSession, pk: int, password: str) -> int:
        """
        重置用户密码

        :param db: 数据库会话
        :param pk: 用户 ID
        :param password: 新密码
        :return:
        """
        user = await user_dao.get(db, pk)
        if not user:
            raise errors.NotFoundError(msg='用户不存在')

        await validate_new_password(db, user.id, password)
        count = await user_dao.reset_password(db, user.id, password)

        history_obj = CreateUserPasswordHistoryParam(user_id=user.id, password=user.password)
        await password_security_service.save_password_history(db, history_obj)
        await user_dao.update_password_changed_time(db, user.id)
        await mark_user_sessions_invalid(user.id, reason=TokenInvalidReason.password_changed)
        await mark_user_refresh_sessions_invalid(user.id, reason=TokenInvalidReason.password_changed)
        await redis_client.delete_by_prefix(f'{settings.TOKEN_REDIS_PREFIX}:{user.id}')
        await redis_client.delete_by_prefix(f'{settings.TOKEN_REFRESH_REDIS_PREFIX}:{user.id}')
        await redis_client.delete_by_prefix(f'{settings.JWT_USER_REDIS_PREFIX}:{user.id}')
        return count

    @staticmethod
    async def update_username(*, db: AsyncSession, user_id: int, username: str) -> int:
        """
        一次性设置自定义用户名（仅 wx_ 开头的用户可用）

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param username: 新用户名
        :return:
        """
        import re

        user = await user_dao.get(db, user_id)
        if not user:
            raise errors.NotFoundError(msg='用户不存在')

        if not user.username.startswith('wx_'):
            raise errors.RequestError(msg='用户名已设置，不可再次修改')

        username = username.strip()
        if not (4 <= len(username) <= 20):
            raise errors.RequestError(msg='用户名长度需在 4-20 位之间')

        if not re.match(r'^[a-zA-Z][a-zA-Z0-9_]*$', username):
            raise errors.RequestError(msg='用户名需以字母开头，仅可包含字母、数字和下划线')

        if username.lower().startswith('wx_'):
            raise errors.RequestError(msg='用户名不能以 wx_ 开头')

        validate_no_sensitive_words(username, '用户名')

        if await user_dao.get_by_username(db, username):
            raise errors.ConflictError(msg='用户名已被使用')

        count = await user_dao.update_username(db, user_id, username)
        await redis_client.delete(f'{settings.JWT_USER_REDIS_PREFIX}:{user_id}')
        return count

    @staticmethod
    async def update_nickname(*, db: AsyncSession, user_id: int, nickname: str) -> int:
        """
        更新当前用户昵称

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param nickname: 用户昵称
        :return:
        """
        validate_no_sensitive_words(nickname, '昵称')

        count = await user_dao.update_nickname(db, user_id, nickname)
        await redis_client.delete(f'{settings.JWT_USER_REDIS_PREFIX}:{user_id}')
        return count

    @staticmethod
    async def update_avatar(*, db: AsyncSession, user_id: int, avatar: str) -> int:
        """
        更新当前用户头像

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param avatar: 头像地址
        :return:
        """
        count = await user_dao.update_avatar(db, user_id, avatar)
        await redis_client.delete(f'{settings.JWT_USER_REDIS_PREFIX}:{user_id}')
        return count

    @staticmethod
    async def update_email(*, db: AsyncSession, user_id: int, captcha: str, email: str) -> int:
        """
        更新当前用户邮箱

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param captcha: 邮箱验证码
        :param email: 邮箱
        :return:
        """
        captcha_code = await redis_client.get(f'{settings.EMAIL_CAPTCHA_REDIS_PREFIX}:{ctx.ip}')
        if not captcha_code:
            raise errors.RequestError(msg='验证码已失效，请重新获取')
        if captcha != captcha_code:
            raise errors.CustomError(error=CustomErrorCode.CAPTCHA_ERROR)
        email_user = await user_dao.check_email(db, email)
        if email_user and email_user.id != user_id:
            raise errors.ConflictError(msg='邮箱已被绑定')
        await redis_client.delete(f'{settings.EMAIL_CAPTCHA_REDIS_PREFIX}:{ctx.ip}')
        count = await user_dao.update_email(db, user_id, email)
        await redis_client.delete(f'{settings.JWT_USER_REDIS_PREFIX}:{user_id}')
        return count

    @staticmethod
    async def update_phone(
        *,
        db: AsyncSession,
        user_id: int,
        old_phone_code: str | None,
        new_phone: str,
        new_phone_code: str,
    ) -> int:
        """
        更换手机号（双重验证）

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param old_phone_code: 旧手机验证码
        :param new_phone: 新手机号
        :param new_phone_code: 新手机验证码
        :return:
        """
        user = await user_dao.get(db, user_id)
        if not user:
            raise errors.NotFoundError(msg='用户不存在')

        # 1. 验证旧手机（如果已绑定手机号）
        if user.phone:
            if not old_phone_code:
                raise errors.RequestError(msg='请输入旧手机验证码')
            old_key = f'{settings.SMS_PHONE_CHANGE_REDIS_PREFIX}:{user.phone}'
            cached_old_code = await redis_client.get(old_key)
            if not cached_old_code:
                raise errors.RequestError(msg='旧手机验证码已过期，请重新获取')
            if cached_old_code != old_phone_code:
                raise errors.RequestError(msg='旧手机验证码错误')
            await redis_client.delete(old_key)

        # 2. 验证新手机
        new_key = f'{settings.SMS_PHONE_CHANGE_REDIS_PREFIX}:{new_phone}'
        cached_new_code = await redis_client.get(new_key)
        if not cached_new_code:
            raise errors.RequestError(msg='新手机验证码已过期，请重新获取')
        if cached_new_code != new_phone_code:
            raise errors.RequestError(msg='新手机验证码错误')
        await redis_client.delete(new_key)

        # 3. 检查新手机号是否已被其他用户绑定
        existing_user = await user_dao.get_by_phone(db, new_phone)
        if existing_user and existing_user.id != user_id:
            raise errors.ConflictError(msg='该手机号已被其他用户绑定')

        # 4. 更新手机号
        count = await user_dao.update_phone(db, user_id, new_phone)
        await redis_client.delete(f'{settings.JWT_USER_REDIS_PREFIX}:{user_id}')
        return count

    @staticmethod
    async def update_password(*, db: AsyncSession, user_id: int, obj: ResetPasswordParam) -> int:
        """
        更新当前用户密码

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param obj: 密码重置参数
        :return:
        """
        user = await user_dao.get(db, user_id)

        if user.password and not password_verify(obj.old_password, user.password):
            raise errors.RequestError(msg='原密码错误')

        if obj.new_password != obj.confirm_password:
            raise errors.RequestError(msg='两次密码输入不一致')

        await validate_new_password(db, user_id, obj.new_password)
        count = await user_dao.reset_password(db, user_id, obj.new_password)

        history_obj = CreateUserPasswordHistoryParam(user_id=user.id, password=user.password)
        await password_security_service.save_password_history(db, history_obj)
        await user_dao.update_password_changed_time(db, user.id)
        await mark_user_sessions_invalid(user_id, reason=TokenInvalidReason.password_changed)
        await mark_user_refresh_sessions_invalid(user_id, reason=TokenInvalidReason.password_changed)
        await redis_client.delete_by_prefix(f'{settings.TOKEN_REDIS_PREFIX}:{user_id}')
        await redis_client.delete_by_prefix(f'{settings.TOKEN_REFRESH_REDIS_PREFIX}:{user_id}')
        await redis_client.delete_by_prefix(f'{settings.JWT_USER_REDIS_PREFIX}:{user_id}')
        return count

    @staticmethod
    async def delete(*, db: AsyncSession, pk: int) -> int:
        """
        删除用户

        :param db: 数据库会话
        :param pk: 用户 ID
        :return:
        """
        user = await user_dao.get(db, pk)
        if not user:
            raise errors.NotFoundError(msg='用户不存在')
        count = await user_dao.delete(db, user.id)
        await mark_user_sessions_invalid(user.id, reason=TokenInvalidReason.permission_changed)
        await mark_user_refresh_sessions_invalid(user.id, reason=TokenInvalidReason.permission_changed)
        await redis_client.delete_by_prefix(f'{settings.TOKEN_REDIS_PREFIX}:{user.id}')
        await redis_client.delete_by_prefix(f'{settings.TOKEN_REFRESH_REDIS_PREFIX}:{user.id}')
        await redis_client.delete_by_prefix(f'{settings.JWT_USER_REDIS_PREFIX}:{user.id}')
        return count


user_service: UserService = UserService()
