from fastapi import Request, Response
from fastapi.security import HTTPBasicCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.background import BackgroundTask, BackgroundTasks

from backend.app.admin.crud.crud_menu import menu_dao
from backend.app.admin.crud.crud_user import user_dao
from backend.app.admin.model import User
from backend.app.admin.schema.token import GetLoginToken, GetNewToken, RefreshTokenParam
from backend.app.admin.schema.user import AuthLoginParam, AuthRegisterParam, SmsLoginParam
from backend.app.admin.service.login_log_service import login_log_service
from backend.app.admin.service.user_password_history_service import password_security_service
from backend.app.admin.utils.password_security import password_verify
from backend.common.context import ctx
from backend.common.dataclasses import TokenPayload
from backend.common.enums import LoginLogStatusType, StatusType
from backend.common.events import publish
from backend.common.exception import errors
from backend.common.i18n import t
from backend.common.log import log
from backend.common.response.response_code import CustomErrorCode
from backend.common.security.client import (
    LoginClientType,
    get_login_client_type,
    refresh_cookie_key,
    set_refresh_cookie,
)
from backend.common.security.jwt import jwt_authentication, jwt_decode
from backend.common.security.token import (
    create_access_token,
    create_new_token,
    create_token_pair,
    get_token,
    revoke_token,
)
from backend.common.security.token_reason import (
    TokenAuthReason,
    TokenInvalidReason,
    auth_reason_data,
    auth_reason_message,
    get_token_invalid_reason,
)
from backend.core.conf import settings
from backend.database.db import uuid4_str
from backend.database.redis import redis_client
from backend.utils.dynamic_config import load_login_config
from backend.utils.timezone import timezone


class AuthService:
    """认证服务类"""

    @staticmethod
    async def issue_login_token(
        *,
        db: AsyncSession,
        response: Response,
        user: User,
        background_tasks: BackgroundTasks | None = None,
        password_expire_days_remaining: int | None = None,
        success_msg: str | None = None,
        client_type: LoginClientType | None = None,
        session_info: dict | None = None,
    ) -> GetLoginToken:
        """
        基于现有用户签发登录令牌

        :param db: 数据库会话
        :param response: 响应对象
        :param user: 用户 ORM 对象
        :param background_tasks: 后台任务
        :param password_expire_days_remaining: 密码到期剩余天数
        :param success_msg: 登录成功日志
        :param client_type: 登录目标客户端，默认读取当前请求
        :param session_info: 扫码发起端的会话信息
        :return:
        """
        client_type = LoginClientType(client_type or get_login_client_type())
        if not user.status:
            raise errors.AuthorizationError(msg='用户已被锁定，请联系管理员')
        if client_type == LoginClientType.admin and not user.is_staff:
            raise errors.AuthorizationError(msg='该账号没有后台登录权限')
        await user_dao.update_login_time(db, user.username)
        await db.refresh(user)

        token_data = await create_token_pair(
            user.id,
            multi_login=user.is_multi_login,
            client_type=client_type,
            username=user.username,
            nickname=user.nickname,
            last_login_time=timezone.to_str(user.last_login_time),
            **{key: value or '未知' for key, value in (
                session_info or {'ip': ctx.ip, 'os': ctx.os, 'browser': ctx.browser, 'device': ctx.device}
            ).items()},
        )
        set_refresh_cookie(
            response, client_type, token_data.new_refresh_token, token_data.new_refresh_token_expire_time,
        )

        if background_tasks is not None:
            background_tasks.add_task(
                login_log_service.create,
                user_uuid=user.uuid,
                username=user.username,
                login_time=timezone.now(),
                status=LoginLogStatusType.success.value,
                msg=success_msg or t('success.login.success'),
            )

        await publish('user.logged_in', user_id=user.id)

        return GetLoginToken(
            access_token=token_data.new_access_token,
            access_token_expire_time=token_data.new_access_token_expire_time,
            session_uuid=token_data.session_uuid,
            client_type=client_type,
            refresh_token=token_data.new_refresh_token if client_type == LoginClientType.extension else None,
            password_expire_days_remaining=password_expire_days_remaining,
            user=user,  # type: ignore[arg-type]
        )

    @staticmethod
    async def user_verify(*, db: AsyncSession, username: str, password: str) -> tuple[User, int | None]:
        """
        验证用户名和密码

        :param db: 数据库会话
        :param username: 用户名
        :param password: 密码
        :return:
        """
        user = await user_dao.get_by_username_or_email(db, username)
        if not user:
            raise errors.NotFoundError(msg='用户名或密码有误')
        await password_security_service.check_status(user.id, user.status)
        if user.password is None or not password_verify(password, user.password):
            await password_security_service.handle_login_failure(db, user.id)
            raise errors.AuthorizationError(msg='用户名或密码有误')

        days_remaining = await password_security_service.check_password_expiry_status(
            db, user.last_password_changed_time
        )
        await password_security_service.handle_login_success(user.id)

        return user, days_remaining

    async def swagger_login(self, *, db: AsyncSession, obj: HTTPBasicCredentials) -> tuple[str, User]:
        """
        Swagger 文档登录

        :param db: 数据库会话
        :param obj: 登录凭证
        :return:
        """
        if settings.ENVIRONMENT == 'prod':
            raise errors.NotFoundError(msg='生产环境不提供调试登录')
        user, _ = await self.user_verify(db=db, username=obj.username, password=obj.password)
        if not user.is_staff:
            raise errors.AuthorizationError(msg='调试登录仅对管理员开放')
        await user_dao.update_login_time(db, obj.username)
        access_token_data = await create_access_token(
            user.id,
            multi_login=user.is_multi_login,
            swagger=True,
        )
        return access_token_data.access_token, user

    async def login(
        self,
        *,
        db: AsyncSession,
        response: Response,
        obj: AuthLoginParam,
        background_tasks: BackgroundTasks,
    ) -> GetLoginToken:
        """
        用户登录

        :param db: 数据库会话
        :param response: 响应对象
        :param obj: 登录参数
        :param background_tasks: 后台任务
        :return:
        """
        user = None
        try:
            await load_login_config(db)
            if settings.LOGIN_CAPTCHA_ENABLED:
                if not obj.uuid or not obj.captcha:
                    raise errors.RequestError(msg=t('error.captcha.invalid'))
                captcha_key = f'{settings.LOGIN_CAPTCHA_REDIS_PREFIX}:{obj.uuid}'
                captcha_code = await redis_client.get(captcha_key)
                if not captcha_code:
                    raise errors.RequestError(msg=t('error.captcha.expired'))
                if captcha_code.lower() != obj.captcha.lower():
                    raise errors.CustomError(error=CustomErrorCode.CAPTCHA_ERROR)
                await redis_client.delete(captcha_key)

            user, days_remaining = await self.user_verify(db=db, username=obj.username, password=obj.password)
        except errors.NotFoundError as e:
            log.error('登陆错误: 用户名不存在')
            raise errors.NotFoundError(msg=e.msg)
        except (errors.RequestError, errors.CustomError) as e:
            if not user:
                log.error(f'登陆错误: {e.msg}')
            task = BackgroundTask(
                login_log_service.create,
                user_uuid=user.uuid if user else uuid4_str(),
                username=obj.username,
                login_time=timezone.now(),
                status=LoginLogStatusType.fail.value,
                msg=e.msg,
            )
            raise errors.RequestError(code=e.code, msg=e.msg, background=task)
        except Exception as e:
            log.error(f'登陆错误: {e}')
            raise
        else:
            data = await self.issue_login_token(
                db=db,
                response=response,
                user=user,
                background_tasks=background_tasks,
                password_expire_days_remaining=days_remaining,
            )
            return data

    @staticmethod
    async def get_codes(*, db: AsyncSession, request: Request) -> list[str]:
        """
        获取用户权限码

        :param db: 数据库会话
        :param request: FastAPI 请求对象
        :return:
        """
        codes = set()
        if request.user.is_superuser:
            menus = await menu_dao.get_all(db, None, None)
            for menu in menus:
                if menu.status == StatusType.enable and menu.perms:
                    codes.update(menu.perms.split(','))
        else:
            roles = [role for role in request.user.roles if role.status == StatusType.enable]
            if roles:
                for role in roles:
                    for menu in role.menus:
                        if menu.status == StatusType.enable and menu.perms:
                            codes.update(menu.perms.split(','))

        return list(codes)

    @staticmethod
    def _refresh_credentials(
        request: Request, obj: RefreshTokenParam | None,
    ) -> tuple[str, TokenPayload, LoginClientType]:
        """选择当前端的凭据，并校验调用者仍持有对应会话，禁止串端或换账号续期。"""
        client_type = get_login_client_type(request)
        refresh_token = request.cookies.get(refresh_cookie_key(client_type))
        if obj and obj.refresh_token:
            if client_type != LoginClientType.extension:
                raise errors.RequestError(msg='此客户端请使用刷新 Cookie')
            refresh_token = obj.refresh_token
        if not refresh_token:
            raise errors.TokenError(
                msg=auth_reason_message(TokenAuthReason.refresh_expired.value),
                data=auth_reason_data(TokenAuthReason.refresh_expired.value),
            )

        token_payload = jwt_decode(refresh_token, verify_exp=False)
        if token_payload.client_type != client_type:
            raise errors.TokenError(
                msg=auth_reason_message(TokenInvalidReason.policy_changed.value),
                data=auth_reason_data(TokenInvalidReason.policy_changed.value),
            )
        expected_session = request.headers.get('X-Session-ID')
        if request.headers.get('Authorization'):
            access_payload = jwt_decode(get_token(request), verify_exp=False)
            expected_session = access_payload.session_uuid
        if expected_session and expected_session != token_payload.session_uuid:
            raise errors.TokenError(
                msg=auth_reason_message(TokenInvalidReason.session_replaced.value),
                data=auth_reason_data(TokenInvalidReason.session_replaced.value),
            )
        return refresh_token, token_payload, client_type

    @staticmethod
    async def refresh_token(
        *, db: AsyncSession, request: Request, response: Response, obj: RefreshTokenParam | None = None
    ) -> GetNewToken:
        """轮换原会话的凭据，保持客户端类型及会话 ID 不变。"""
        refresh_token, token_payload, client_type = AuthService._refresh_credentials(request, obj)

        invalid_reason = await get_token_invalid_reason(token_payload.user_id, token_payload.session_uuid)
        if invalid_reason:
            raise errors.TokenError(
                msg=auth_reason_message(invalid_reason),
                data=auth_reason_data(invalid_reason),
            )
        if token_payload.expire_time <= timezone.now():
            raise errors.TokenError(
                msg=auth_reason_message(TokenAuthReason.refresh_expired.value),
                data=auth_reason_data(TokenAuthReason.refresh_expired.value),
            )

        user = await user_dao.get(db, token_payload.user_id)
        if not user:
            raise errors.NotFoundError(msg='用户不存在')
        if not user.status:
            raise errors.AuthorizationError(msg='用户已被锁定, 请联系统管理员')
        if client_type == LoginClientType.admin and not user.is_staff:
            raise errors.AuthorizationError(msg='该账号没有后台登录权限')
        new_token = await create_new_token(
            refresh_token,
            token_payload.session_uuid,
            user.id,
            multi_login=user.is_multi_login,
            # extra info
            username=user.username,
            nickname=user.nickname,
            ip=ctx.ip or '未知',
            os=ctx.os or '未知',
            browser=ctx.browser or '未知',
            device=ctx.device or '未知',
        )
        set_refresh_cookie(response, client_type, new_token.new_refresh_token, new_token.new_refresh_token_expire_time)

        data = GetNewToken(
            access_token=new_token.new_access_token,
            access_token_expire_time=new_token.new_access_token_expire_time,
            session_uuid=new_token.session_uuid,
            client_type=client_type,
            refresh_token=new_token.new_refresh_token if client_type == LoginClientType.extension else None,
        )
        return data

    async def exchange_extension_session(
        self, *, db: AsyncSession, request: Request, response: Response
    ) -> GetLoginToken:
        """已登录官网为插件签发独立会话；不把官网凭据直接作为插件凭据。"""
        token = get_token(request)
        user_info = await jwt_authentication(token)
        source = jwt_decode(token)
        if source.client_type != LoginClientType.web or get_login_client_type(request) != LoginClientType.extension:
            raise errors.ForbiddenError(msg='仅支持官网登录换取插件会话')
        user = await user_dao.get(db, user_info.id)
        if not user:
            raise errors.NotFoundError(msg='用户不存在')
        return await self.issue_login_token(
            db=db, response=response, user=user, client_type=LoginClientType.extension,
        )

    @staticmethod
    async def logout(*, request: Request, response: Response) -> None:
        """
        用户登出

        :param request: FastAPI 请求对象
        :param response: FastAPI 响应对象
        :return:
        """
        client_type = get_login_client_type(request)
        try:
            token = get_token(request)
            token_payload = jwt_decode(token, verify_exp=False)
            if token_payload.client_type is not None and token_payload.client_type != client_type:
                raise errors.TokenError(msg='登录客户端不匹配')
        except errors.TokenError:
            return

        # 旧标签页的退出不能删除刚登录的新会话的同端 Cookie。
        cookie_key = refresh_cookie_key(client_type)
        cookie = request.cookies.get(cookie_key)
        if cookie:
            try:
                cookie_payload = jwt_decode(cookie, verify_exp=False)
            except errors.TokenError:
                pass
            else:
                if cookie_payload.session_uuid == token_payload.session_uuid:
                    response.delete_cookie(cookie_key)

        await revoke_token(
            token_payload.user_id,
            token_payload.session_uuid,
            reason=TokenInvalidReason.logout,
        )

    async def register_user(self, *, db: AsyncSession, obj: AuthRegisterParam) -> User:
        """
        用户名密码注册（C 端）

        :param db: 数据库会话
        :param obj: 注册参数
        :return: 新注册的用户
        """
        import bcrypt

        from backend.app.admin.service.user_service import user_service
        from backend.app.admin.utils.password_security import get_hash_password

        await load_login_config(db)
        if settings.LOGIN_CAPTCHA_ENABLED:
            if not obj.uuid or not obj.captcha:
                raise errors.RequestError(msg=t('error.captcha.invalid'))
            captcha_code = await redis_client.get(f'{settings.LOGIN_CAPTCHA_REDIS_PREFIX}:{obj.uuid}')
            if not captcha_code:
                raise errors.RequestError(msg=t('error.captcha.expired'))
            if captcha_code.lower() != obj.captcha.lower():
                raise errors.CustomError(error=CustomErrorCode.CAPTCHA_ERROR)
            await redis_client.delete(f'{settings.LOGIN_CAPTCHA_REDIS_PREFIX}:{obj.uuid}')

        if await user_dao.get_by_username(db, obj.username):
            raise errors.ConflictError(msg='用户名已注册')

        salt = bcrypt.gensalt()
        user = await user_service.register(
            db=db,
            user_data={
                'username': obj.username,
                'password': get_hash_password(obj.password, salt),
                'salt': salt,
                'nickname': obj.nickname or obj.username,
                'status': 1,
            },
        )
        log.info(f'新用户注册: {obj.username}')
        return user

    async def login_by_sms(
        self,
        *,
        db: AsyncSession,
        response: Response,
        obj: SmsLoginParam,
        background_tasks: BackgroundTasks,
    ) -> GetLoginToken:
        """
        短信验证码登录（用户不存在则自动注册）

        :param db: 数据库会话
        :param response: 响应对象
        :param obj: 短信登录参数
        :param background_tasks: 后台任务
        :return:
        """
        # 1. 验证短信验证码
        redis_key = f'{settings.SMS_LOGIN_REDIS_PREFIX}:{obj.phone}'
        cached_code = await redis_client.get(redis_key)
        if not cached_code:
            raise errors.RequestError(msg='验证码已过期，请重新获取')
        if cached_code != obj.code:
            raise errors.RequestError(msg='验证码错误')

        await redis_client.delete(redis_key)

        # 2. 查找用户，不存在则自动注册
        user = await user_dao.get_by_phone(db, obj.phone)
        if not user:
            import secrets

            import bcrypt

            from backend.app.admin.service.user_service import user_service
            from backend.app.admin.utils.password_security import get_hash_password

            salt = bcrypt.gensalt()
            random_password = secrets.token_urlsafe(16)
            nickname = f'用户_{obj.phone[-4:]}'

            user = await user_service.register(
                db=db,
                user_data={
                    'username': obj.phone,
                    'password': get_hash_password(random_password, salt),
                    'salt': salt,
                    'phone': obj.phone,
                    'nickname': nickname,
                    'status': 1,
                },
            )
            log.info(f'短信登录自动注册用户: {obj.phone}')

        # 3. 检查用户状态
        if not user.status:
            raise errors.AuthorizationError(msg='用户已被锁定，请联系管理员')

        # 4. 签发令牌
        return await self.issue_login_token(
            db=db,
            response=response,
            user=user,
            background_tasks=background_tasks,
            success_msg=f'短信验证码登录成功: {obj.phone}',
        )


auth_service: AuthService = AuthService()
