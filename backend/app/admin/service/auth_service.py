from fastapi import Request, Response
from fastapi.security import HTTPBasicCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.background import BackgroundTask, BackgroundTasks

from backend.app.admin.crud.crud_menu import menu_dao
from backend.app.admin.crud.crud_user import user_dao
from backend.app.admin.model import User
from backend.app.admin.schema.token import GetLoginToken, GetNewToken
from backend.app.admin.schema.user import AuthLoginParam, SmsLoginParam
from backend.app.admin.service.login_log_service import login_log_service
from backend.app.admin.service.user_password_history_service import password_security_service
from backend.app.admin.utils.password_security import password_verify
from backend.common.context import ctx
from backend.common.enums import LoginLogStatusType, StatusType
from backend.common.events import publish
from backend.common.exception import errors
from backend.common.i18n import t
from backend.common.log import log
from backend.common.response.response_code import CustomErrorCode
from backend.common.security.jwt import (
    create_access_token,
    create_new_token,
    create_refresh_token,
    get_token,
    jwt_decode,
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
    ) -> GetLoginToken:
        """
        鍩轰簬鐜版湁鐢ㄦ埛绛惧彂鐧诲綍浠ょ墝

        :param db: 鏁版嵁搴撲細璇?
        :param response: 鍝嶅簲瀵硅薄
        :param user: 鐢ㄦ埛 ORM 瀵硅薄
        :param background_tasks: 鍚庡彴浠诲姟
        :param password_expire_days_remaining: 瀵嗙爜鍒版湡鍓╀綑澶╂暟
        :param success_msg: 鐧诲綍鎴愬姛鏃ュ織
        :return:
        """
        await user_dao.update_login_time(db, user.username)
        await db.refresh(user)

        access_token_data = await create_access_token(
            user.id,
            multi_login=user.is_multi_login,
            username=user.username,
            nickname=user.nickname,
            last_login_time=timezone.to_str(user.last_login_time),
            ip=ctx.ip,
            os=ctx.os,
            browser=ctx.browser,
            device=ctx.device,
        )
        refresh_token_data = await create_refresh_token(
            access_token_data.session_uuid,
            user.id,
            multi_login=user.is_multi_login,
        )
        response.set_cookie(
            key=settings.COOKIE_REFRESH_TOKEN_KEY,
            value=refresh_token_data.refresh_token,
            max_age=settings.COOKIE_REFRESH_TOKEN_EXPIRE_SECONDS,
            expires=timezone.to_utc(refresh_token_data.refresh_token_expire_time),
            httponly=True,
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
            access_token=access_token_data.access_token,
            access_token_expire_time=access_token_data.access_token_expire_time,
            session_uuid=access_token_data.session_uuid,
            password_expire_days_remaining=password_expire_days_remaining,
            user=user,  # type: ignore[arg-type]
        )

    @staticmethod
    async def user_verify(db: AsyncSession, username: str, password: str) -> tuple[User, int | None]:
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
        user, _ = await self.user_verify(db, obj.username, obj.password)
        await user_dao.update_login_time(db, obj.username)
        access_token_data = await create_access_token(
            user.id,
            multi_login=user.is_multi_login,
            # extra info
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
                captcha_code = await redis_client.get(f'{settings.LOGIN_CAPTCHA_REDIS_PREFIX}:{obj.uuid}')
                if not captcha_code:
                    raise errors.RequestError(msg=t('error.captcha.expired'))
                if captcha_code.lower() != obj.captcha.lower():
                    raise errors.CustomError(error=CustomErrorCode.CAPTCHA_ERROR)
                await redis_client.delete(f'{settings.LOGIN_CAPTCHA_REDIS_PREFIX}:{obj.uuid}')

            user, days_remaining = await self.user_verify(db, obj.username, obj.password)
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
    async def refresh_token(*, db: AsyncSession, request: Request, response: Response) -> GetNewToken:
        """
        刷新令牌

        :param db: 数据库会话
        :param request: FastAPI 请求对象
        :param response: FastAPI 响应对象
        :return:
        """
        refresh_token = request.cookies.get(settings.COOKIE_REFRESH_TOKEN_KEY)
        if not refresh_token:
            raise errors.TokenError(msg='Refresh Token 已过期，请重新登录')

        token_payload = jwt_decode(refresh_token)
        user = await user_dao.get(db, token_payload.user_id)
        if not user:
            raise errors.NotFoundError(msg='用户不存在')
        if not user.status:
            raise errors.AuthorizationError(msg='用户已被锁定, 请联系统管理员')
        token_keys = await redis_client.get_by_prefix(f'{settings.TOKEN_REDIS_PREFIX}:{user.id}')
        if not user.is_multi_login and [
            key for key in token_keys if not key.endswith(f':{token_payload.session_uuid}')
        ]:
            raise errors.TokenError(msg='此用户已在异地登录，请重新登录并及时修改密码')
        new_token = await create_new_token(
            refresh_token,
            token_payload.session_uuid,
            user.id,
            multi_login=user.is_multi_login,
            # extra info
            username=user.username,
            nickname=user.nickname,
            last_login_time=timezone.to_str(user.last_login_time),
            ip=ctx.ip,
            os=ctx.os,
            browser=ctx.browser,
            device_type=ctx.device,
        )
        response.set_cookie(
            key=settings.COOKIE_REFRESH_TOKEN_KEY,
            value=new_token.new_refresh_token,
            max_age=settings.COOKIE_REFRESH_TOKEN_EXPIRE_SECONDS,
            expires=timezone.to_utc(new_token.new_refresh_token_expire_time),
            httponly=True,
        )
        data = GetNewToken(
            access_token=new_token.new_access_token,
            access_token_expire_time=new_token.new_access_token_expire_time,
            session_uuid=new_token.session_uuid,
        )
        return data

    @staticmethod
    async def logout(*, request: Request, response: Response) -> None:
        """
        用户登出

        :param request: FastAPI 请求对象
        :param response: FastAPI 响应对象
        :return:
        """
        try:
            token = get_token(request)
            token_payload = jwt_decode(token)
            user_id = token_payload.user_id
            session_uuid = token_payload.session_uuid
            refresh_token = request.cookies.get(settings.COOKIE_REFRESH_TOKEN_KEY)
        except errors.TokenError:
            return
        finally:
            response.delete_cookie(settings.COOKIE_REFRESH_TOKEN_KEY)

        await redis_client.delete(f'{settings.TOKEN_REDIS_PREFIX}:{user_id}:{session_uuid}')
        await redis_client.delete(f'{settings.TOKEN_EXTRA_INFO_REDIS_PREFIX}:{user_id}:{session_uuid}')
        if refresh_token:
            await redis_client.delete(f'{settings.TOKEN_REFRESH_REDIS_PREFIX}:{user_id}:{session_uuid}')

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
