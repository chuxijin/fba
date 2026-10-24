import json

from io import BytesIO
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx

from fast_captcha import text_captcha
from fastapi import BackgroundTasks, Response, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.admin.crud.crud_user import user_dao
from backend.app.admin.model import User
from backend.app.admin.schema.token import GetLoginToken
from backend.app.admin.schema.user import AddOAuth2UserParam
from backend.app.admin.service.auth_service import auth_service
from backend.app.admin.service.user_service import user_service
from backend.common.context import ctx
from backend.common.exception import errors
from backend.common.i18n import t
from backend.common.log import log
from backend.common.security.client import LoginClientType
from backend.core.conf import settings
from backend.database.redis import redis_client
from backend.plugin.oauth2.crud.crud_user_social import user_social_dao
from backend.plugin.oauth2.enums import UserSocialAuthType, UserSocialType
from backend.plugin.oauth2.schema.user_social import CreateUserSocialParam
from backend.plugin.oauth2.service.user_social_service import user_social_service
from backend.utils.nickname import generate_default_nickname


class OAuth2Service:
    """OAuth2 认证服务类"""

    # 历史遗留的占位昵称：不具区分性，登录时会被替换成带随机后缀的默认昵称
    PLACEHOLDER_NICKNAMES = frozenset({'微信用户', '微信测试考生'})

    @staticmethod
    def _resolve_nickname(nickname: str | None) -> str:
        """
        解析微信授权登录的昵称

        微信 jscode2session 不返回昵称，小程序端也刻意不申请头像昵称权限；
        因此客户端没给昵称时必须自己生成一个可区分的默认昵称，而不是写死「微信用户」。

        :param nickname: 客户端授权得到的昵称
        :return: 最终使用的昵称
        """
        return (nickname or '').strip() or generate_default_nickname()

    @staticmethod
    async def _replace_placeholder_nickname(*, db: AsyncSession, user: Any, nickname: str) -> None:
        """
        修复历史遗留的占位昵称

        老账号在微信未授权昵称时会留下「微信用户」这种重复值，登录时顺手替换成可区分的默认昵称；
        用户自己设置过的真实昵称永远不会被覆盖。

        :param db: 数据库会话
        :param user: 登录用户对象
        :param nickname: 本次应当使用的昵称
        :return:
        """
        current = (user.nickname or '').strip()
        if current and current not in OAuth2Service.PLACEHOLDER_NICKNAMES:
            return

        await user_dao.update_nickname(db, user.id, nickname)
        user.nickname = nickname
        log.info(f'替换占位昵称为默认昵称: user_id={user.id} nickname={nickname}')

    @staticmethod
    def _normalize_avatar_url(avatar: str | None) -> str | None:
        """
        标准化头像地址

        :param avatar: 原始头像地址
        :return:
        """
        if not avatar:
            return None
        value = avatar.strip()
        if not value:
            return None
        return value

    @staticmethod
    def _is_signed_avatar_url(avatar: str | None) -> bool:
        """
        Check whether avatar url is signed.

        :param avatar: avatar url
        :return:
        """
        if not avatar:
            return False

        parsed = urlparse(avatar)
        query = parse_qs(parsed.query)
        query_keys = {key.lower() for key in query}
        signed_markers = {
            'e',
            'token',
            'expires',
            'signature',
            'ossaccesskeyid',
            'x-oss-signature',
            'x-oss-credential',
            'x-oss-date',
        }
        return bool(query_keys & signed_markers)

    @staticmethod
    def _guess_avatar_extension(avatar_url: str, content_type: str | None) -> str:
        """
        推断头像后缀

        :param avatar_url: 头像地址
        :param content_type: 文件类型
        :return:
        """
        parsed = urlparse(avatar_url)
        path = parsed.path or ''
        if '.' in path:
            ext = path.rsplit('.', 1)[-1].lower()
            if ext in {'jpg', 'jpeg', 'png', 'webp', 'gif', 'bmp'}:
                return '.jpg' if ext == 'jpeg' else f'.{ext}'

        content_type_value = str(content_type or '').lower().split(';')[0].strip()
        content_type_mapping = {
            'image/jpeg': '.jpg',
            'image/jpg': '.jpg',
            'image/png': '.png',
            'image/webp': '.webp',
            'image/gif': '.gif',
            'image/bmp': '.bmp',
        }
        return content_type_mapping.get(content_type_value, '.jpg')

    @staticmethod
    async def upload_avatar_to_oss(
        *,
        db: AsyncSession,
        user_id: int,
        avatar: str | None,
    ) -> str | None:
        """
        将第三方头像同步到 OSS

        :param db: 数据库会话
        :param user_id: 系统用户 ID
        :param avatar: 第三方头像 URL
        :return:
        """
        avatar_url = OAuth2Service._normalize_avatar_url(avatar)
        if not avatar_url:
            return None

        if not avatar_url.startswith(('http://', 'https://')):
            return avatar_url

        try:
            from backend.plugin.oss.service.storage_service import storage_service
        except Exception as exc:
            log.warning(f'OSS 插件不可用，跳过头像转存: {exc!s}')
            return avatar_url

        timeout = httpx.Timeout(timeout=10.0, connect=5.0)
        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                response = await client.get(avatar_url)
                response.raise_for_status()
        except Exception as exc:
            log.warning(f'下载微信头像失败，使用原始头像地址: {exc!s}')
            return avatar_url

        content = response.content
        if not content:
            log.warning('下载微信头像为空，使用原始头像地址')
            return avatar_url

        content_type = response.headers.get('content-type')
        extension = OAuth2Service._guess_avatar_extension(avatar_url, content_type)
        filename = f'wx_{user_id}{extension}'
        upload_file = UploadFile(file=BytesIO(content), filename=filename)

        try:
            uploaded_url, _ = await storage_service.upload_with_filename(
                db=db,
                file=upload_file,
                filename=filename,
                path='avatar/wechat',
                use_signed_url=False,
            )
        except Exception as exc:
            log.warning(f'上传微信头像到 OSS 失败，使用原始头像地址: {exc!s}')
            return avatar_url
        else:
            return uploaded_url
        finally:
            upload_file.file.close()

    @staticmethod
    async def ensure_qbank_user_account(
        *,
        db: AsyncSession,
        user_id: int,
        register_channel: str | None = None,
    ) -> None:
        """
        确保题库用户扩展账户存在

        :param db: 数据库会话
        :param user_id: 系统用户 ID
        :param register_channel: 注册渠道
        :return:
        """
        try:
            from backend.app.question_bank.service.user_account_service import user_account_service
        except Exception:
            return

        await user_account_service.ensure_by_sys_user_id(
            db=db,
            sys_user_id=user_id,
            register_channel=register_channel,
        )

    @staticmethod
    async def login(
        *,
        db: AsyncSession,
        response: Response,
        background_tasks: BackgroundTasks,
        sid: str | None = None,
        source: UserSocialType,
        openid: str | None = None,
        unionid: str | None = None,
        username: str | None = None,
        nickname: str | None = None,
        email: str | None = None,
        avatar: str | None = None,
        client_type: LoginClientType | None = None,
        session_info: dict | None = None,
    ) -> GetLoginToken:
        """
        OAuth2 用户登录

        :param db: 数据库会话
        :param response: FastAPI 响应对象
        :param background_tasks: FastAPI 后台任务
        :param sid: 社交账号唯一编码
        :param source: 社交平台
        :param openid: 平台 OpenID
        :param unionid: 跨端 UnionID
        :param username: 用户名
        :param nickname: 昵称
        :param email: 邮箱
        :param avatar: 头像地址
        :param client_type: 登录目标客户端
        :param session_info: 扫码发起端信息
        :return:
        """
        if not sid and not openid:
            raise errors.RequestError(msg='第三方身份唯一凭证(sid或openid)不能为空')

        search_id = sid or openid
        user_social = await user_social_dao.get_by_sid(db, search_id, source.value) or (
            await user_social_dao.get_by_openid(db, openid, source.value) if openid else None
        )

        original_avatar_url = OAuth2Service._normalize_avatar_url(avatar)

        if user_social:
            sys_user = await user_dao.get(db, user_social.user_id)
        else:
            sys_user = None
            # 检测系统用户是否已存在
            if email:
                sys_user = await user_dao.check_email(db, email)

            # 创建系统用户
            if not sys_user:
                base_username = username or text_captcha(5)
                username_candidates = [base_username, *[f'{base_username}_{text_captcha(5)}' for _ in range(10)]]
                existing_users = await user_dao.get_all_by_usernames(db, username_candidates)
                existing_usernames = {user.username for user in existing_users}
                username = next(
                    (candidate for candidate in username_candidates if candidate not in existing_usernames),
                    None,
                )
                if username is None:
                    raise errors.ConflictError(msg='用户名已存在，请重试')
                new_sys_user = AddOAuth2UserParam(
                    username=username,
                    password=None,
                    nickname=nickname,
                    email=email,
                    avatar=original_avatar_url,
                )

                async def _create_oauth2_user(_db: AsyncSession, _data: dict) -> User:
                    await user_dao.add_by_oauth2(_db, AddOAuth2UserParam(**_data))
                    await _db.flush()
                    return await user_dao.get_by_username(_db, _data['username'])

                sys_user = await user_service.register(
                    db=db,
                    user_data=new_sys_user.model_dump(),
                    creator=_create_oauth2_user,
                )

            # 绑定社交账号
            new_user_social = CreateUserSocialParam(
                sid=sid,
                source=source.value,
                user_id=sys_user.id,
                openid=openid,
                unionid=unionid,
            )
            await user_social_dao.create(db, new_user_social)

        if source == UserSocialType.wechat_miniapp:
            await OAuth2Service.ensure_qbank_user_account(
                db=db,
                user_id=sys_user.id,
                register_channel='miniapp',
            )

        need_upload_avatar = bool(original_avatar_url) and (
            not sys_user.avatar
            or sys_user.avatar == original_avatar_url
            or OAuth2Service._is_signed_avatar_url(sys_user.avatar)
        )
        uploaded_avatar_url = None
        if need_upload_avatar:
            uploaded_avatar_url = await OAuth2Service.upload_avatar_to_oss(
                db=db,
                user_id=sys_user.id,
                avatar=original_avatar_url,
            )
        if uploaded_avatar_url and (
            not sys_user.avatar or (
                original_avatar_url
                and sys_user.avatar == original_avatar_url
                and uploaded_avatar_url != original_avatar_url
            )
        ):
            await user_dao.update_avatar(db, sys_user.id, uploaded_avatar_url)
            sys_user.avatar = uploaded_avatar_url

        data = await auth_service.issue_login_token(
            db=db, response=response, user=sys_user, background_tasks=background_tasks,
            success_msg=t('success.login.oauth2_success'), client_type=client_type, session_info=session_info,
        )
        await redis_client.delete(f'{settings.LOGIN_CAPTCHA_REDIS_PREFIX}:{ctx.ip}')
        return data

    async def login_or_binding(
        self,
        *,
        db: AsyncSession,
        response: Response,
        background_tasks: BackgroundTasks,
        user: dict[str, Any],
        social: UserSocialType,
        state: str | None = None,
    ) -> GetLoginToken | None:
        """
        OAuth2 登录或绑定

        :param db: 数据库会话
        :param response: FastAPI 响应对象
        :param background_tasks: FastAPI 后台任务
        :param user: OAuth2 用户信息
        :param social: 社交平台类型
        :param state: OAuth2 state 参数
        :return:
        """

        sid = user.get('uuid')
        username = user.get('username')
        nickname = user.get('nickname')
        email = user.get('email')
        avatar = user.get('avatar_url')

        match social:
            case UserSocialType.github:
                sid = user.get('id')
                username = user.get('login')
                nickname = user.get('name')
            case UserSocialType.google:
                sid = user.get('id')
                username = user.get('name')
                nickname = user.get('given_name')
                avatar = user.get('picture')
            case _:
                raise errors.ForbiddenError(msg=f'暂不支持 {social} OAuth2 登录')

        if not state:
            raise errors.ForbiddenError(msg='OAuth2 状态信息缺失')

        state_data = await redis_client.get(f'{settings.OAUTH2_STATE_REDIS_PREFIX}:{state}')
        if not state_data:
            raise errors.ForbiddenError(msg='OAuth2 状态信息无效或缺失')

        state_info = json.loads(state_data)
        await redis_client.delete(f'{settings.OAUTH2_STATE_REDIS_PREFIX}:{state}')

        # 绑定流程
        if state_info.get('type') == UserSocialAuthType.binding.value:
            user_id = state_info.get('user_id')
            if not user_id:
                raise errors.ForbiddenError(msg='非法操作，OAuth2 状态信息无效')
            await user_social_service.binding_with_oauth2(
                db=db,
                user_id=user_id,
                sid=str(sid),
                source=social,
            )
            return None

        # 登录流程
        if state_info.get('type') != UserSocialAuthType.login.value:
            raise errors.ForbiddenError(msg='OAuth2 状态信息无效')

        return await self.login(
            db=db,
            response=response,
            background_tasks=background_tasks,
            sid=str(sid),
            source=social,
            username=username,
            nickname=nickname,
            email=email,
            avatar=avatar,
            client_type=LoginClientType(state_info.get('client_type', LoginClientType.admin)),
        )

    @staticmethod
    async def wechat_miniapp_login(
        *,
        db: AsyncSession,
        response: Response,
        background_tasks: BackgroundTasks,
        code: str,
        nickname: str | None = None,
        avatar: str | None = None,
        client_type: LoginClientType = LoginClientType.miniapp,
        session_info: dict | None = None,
    ) -> GetLoginToken:
        """
        微信小程序授权业务逻辑

        :param db: 数据库会话
        :param response: FastAPI 响应对象
        :param background_tasks: FastAPI 后台任务
        :param code: 微信 jscode
        :param nickname: 昵称
        :param avatar: 头像
        :param client_type: 登录目标客户端；扫码登录从服务端场景读取
        :param session_info: 扫码发起端信息
        :return:
        """
        appid = getattr(settings, 'WX_MINIAPP_APPID', '')
        secret = getattr(settings, 'WX_MINIAPP_SECRET', '')
        if not appid or not secret:
            raise errors.ServerError(msg='微信小程序配置缺失，缺少 WX_MINIAPP_APPID 或 WX_MINIAPP_SECRET')

        url = 'https://api.weixin.qq.com/sns/jscode2session'
        params = {
            'appid': appid,
            'secret': secret,
            'js_code': code,
            'grant_type': 'authorization_code',
        }

        async with httpx.AsyncClient() as client:
            wx_resp = await client.get(url, params=params)
            wx_data = wx_resp.json()

            if 'errcode' in wx_data and wx_data['errcode'] != 0:
                raise errors.AuthorizationError(msg=f'微信登录失败: {wx_data.get("errmsg", "未知错误")}')

        openid = wx_data.get('openid')
        unionid = wx_data.get('unionid')

        if not openid:
            raise errors.AuthorizationError(msg='获取微信 openid 失败，请检查 code 是否有效')

        user_info = {
            'username': f'wx_{openid[-8:]}',
            'nickname': OAuth2Service._resolve_nickname(nickname),
            'avatar_url': avatar,
        }

        token_info = await OAuth2Service.login(
            db=db,
            response=response,
            background_tasks=background_tasks,
            sid=openid,
            source=UserSocialType.wechat_miniapp,
            openid=openid,
            unionid=unionid,
            username=user_info['username'],
            nickname=user_info['nickname'],
            avatar=user_info['avatar_url'],
            client_type=client_type,
            session_info=session_info,
        )

        # 老账号可能还停在「微信用户」这种占位昵称上，登录时一并修掉，保证能互相区分
        await OAuth2Service._replace_placeholder_nickname(
            db=db,
            user=token_info.user,
            nickname=user_info['nickname'],
        )
        return token_info


oauth2_service: OAuth2Service = OAuth2Service()
