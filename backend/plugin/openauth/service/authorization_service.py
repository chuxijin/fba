"""OpenAuth 授权码 + PKCE、刷新、资源鉴权和授权撤销。

数据库保存授权代次；Redis 保存一次性凭据与设备会话。旧代次永不恢复，
无需扫描 Redis 即可解绑应用。事务由 API 的 CurrentSessionTransaction 提交。
"""

import json
import secrets

from datetime import datetime

from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.exception import errors
from backend.common.security.jwt import get_current_user
from backend.core.conf import settings
from backend.database.redis import redis_client
from backend.plugin.openauth.crud.crud_openauth import openauth_user_authorization_dao
from backend.plugin.openauth.model import OpenAuthClient, OpenAuthUserAuthorization
from backend.plugin.openauth.schema.authorization import (
    CreateOpenAuthAuthorizationParam,
    CreateOpenAuthRefreshParam,
    CreateOpenAuthRevokeParam,
    CreateOpenAuthTokenParam,
    GetOpenAuthAuthorizationPreview,
    GetOpenAuthAuthorizationResult,
    GetOpenAuthCheckResult,
    GetOpenAuthTokenResult,
    GetOpenAuthUserAuthorizationDetail,
)
from backend.plugin.openauth.service.client_service import openauth_client_service
from backend.plugin.openauth.service.constants import (
    OPENAUTH_ACCESS_TOKEN_EXPIRE_SECONDS,
    OPENAUTH_CODE_EXPIRE_SECONDS,
    OPENAUTH_REFRESH_TOKEN_EXPIRE_SECONDS,
    OPENAUTH_TOKEN_AUDIENCE,
    OPENAUTH_TOKEN_ISSUER,
    access_token_key,
    code_key,
    generate_code,
    generate_token,
    pkce_challenge,
    refresh_token_key,
    session_key,
    verify_client_secret,
)
from backend.utils.timezone import timezone


def _decode_openauth_token(token: str, *, verify_exp: bool = True) -> dict:
    try:
        payload = jwt.decode(
            token,
            settings.TOKEN_SECRET_KEY,
            algorithms=[settings.TOKEN_ALGORITHM],
            audience=OPENAUTH_TOKEN_AUDIENCE,
            issuer=OPENAUTH_TOKEN_ISSUER,
            options={
                'verify_exp': verify_exp,
                # python-jose 的 require_exp=True 会强制开启 verify_exp，注销场景手动检查必需字段。
                'require_exp': verify_exp,
                'require_iat': True,
                'require_sub': True,
                'require_aud': True,
                'require_iss': True,
                'require_jti': True,
            },
        )
        if (
            not isinstance(payload.get('exp'), (int, float))
            or not isinstance(payload.get('scopes'), list)
            or not all(isinstance(s, str) for s in payload['scopes'])
            or not all(isinstance(payload.get(k), str) and payload[k] for k in ('client', 'sid', 'grant_version'))
            or int(payload['sub']) <= 0
        ):
            raise ValueError('Invalid identity')
    except (JWTError, ValueError, TypeError, KeyError) as exc:
        raise errors.TokenError(msg='开放平台 token 无效或已过期') from exc
    return payload


class OpenAuthAuthorizationService:
    @staticmethod
    async def get_authorize_preview(
        db: AsyncSession,
        *,
        user_id: int,
        client: OpenAuthClient,
        obj: CreateOpenAuthAuthorizationParam,
    ) -> GetOpenAuthAuthorizationPreview:
        OpenAuthAuthorizationService._validate_request(client, obj)
        active = await openauth_user_authorization_dao.get_active_by_user_and_client(
            db,
            user_id=user_id,
            client_pk=client.id,
        )
        return GetOpenAuthAuthorizationPreview(
            client_id=client.client_id,
            name=client.name,
            description=client.description,
            icon=client.icon,
            scopes=obj.scopes,
            already_authorized=bool(active and set(obj.scopes) <= set(active.scopes)),
        )

    @staticmethod
    async def authorize(
        db: AsyncSession,
        *,
        user_id: int,
        client: OpenAuthClient,
        obj: CreateOpenAuthAuthorizationParam,
    ) -> GetOpenAuthAuthorizationResult:
        OpenAuthAuthorizationService._validate_request(client, obj)
        auth = await openauth_user_authorization_dao.upsert_authorization(
            db,
            user_id=user_id,
            client_pk=client.id,
            obj=obj,
        )
        code = generate_code()
        data = {
            'user_id': user_id,
            'client_pk': client.id,
            'scopes': obj.scopes,
            'redirect_uri': obj.redirect_uri,
            'code_challenge': obj.code_challenge,
            'grant_version': auth.grant_version,
        }
        await redis_client.set(code_key(code), json.dumps(data), ex=OPENAUTH_CODE_EXPIRE_SECONDS)
        return GetOpenAuthAuthorizationResult(
            code=code,
            redirect_uri=obj.redirect_uri,
            state=obj.state,
            expires_in=OPENAUTH_CODE_EXPIRE_SECONDS,
        )

    @staticmethod
    async def create_token(db: AsyncSession, *, obj: CreateOpenAuthTokenParam) -> GetOpenAuthTokenResult:
        client = await openauth_client_service.get_enabled_by_client_id(db, client_id=obj.client_id)
        OpenAuthAuthorizationService._authenticate_client(client, obj.client_secret)
        raw = await redis_client.get(code_key(obj.code))
        if not raw:
            raise errors.TokenError(msg='授权码无效或已过期，请重新授权')
        data = json.loads(raw)
        if data['client_pk'] != client.id or data['redirect_uri'] != obj.redirect_uri:
            raise errors.ForbiddenError(msg='授权码的客户端或回调地址不匹配')
        if obj.redirect_uri not in client.redirect_uris:
            raise errors.ForbiddenError(msg='回调地址已取消注册')
        if not secrets.compare_digest(pkce_challenge(obj.code_verifier), data['code_challenge']):
            raise errors.ForbiddenError(msg='PKCE 校验失败')
        auth = await OpenAuthAuthorizationService._active_grant(db, client=client, data=data)
        if not set(data['scopes']) <= (set(auth.scopes) & set(client.scopes)):
            raise errors.ForbiddenError(msg='授权权限已变更，请重新授权')
        # GETDEL 是原子的；校验错误不会消耗合法用户的授权码。
        if await redis_client.getdel(code_key(obj.code)) != raw:
            raise errors.TokenError(msg='授权码已使用，请重新授权')
        return await OpenAuthAuthorizationService._issue_tokens(
            user_id=data['user_id'],
            client=client,
            scopes=data['scopes'],
            grant_version=auth.grant_version,
        )

    @staticmethod
    async def check(db: AsyncSession, *, token: str) -> GetOpenAuthCheckResult:
        payload = _decode_openauth_token(token)
        raw = await redis_client.get(access_token_key(token))
        if not raw or not await redis_client.get(session_key(payload['sid'])):
            raise errors.TokenError(msg='token 已被吊销或已过期')
        data = json.loads(raw)
        client = await openauth_client_service.get_enabled_by_client_id(db, client_id=payload['client'])
        if (
            data['user_id'] != int(payload['sub'])
            or data['client_pk'] != client.id
            or data['grant_version'] != payload['grant_version']
            or data['sid'] != payload['sid']
            or data['scopes'] != payload['scopes']
        ):
            raise errors.TokenError(msg='token 身份不匹配')
        auth = await OpenAuthAuthorizationService._active_grant(db, client=client, data=data)
        scopes = [s for s in data['scopes'] if s in auth.scopes and s in client.scopes]
        await openauth_user_authorization_dao.touch_last_used(db, row=auth)
        return GetOpenAuthCheckResult(
            user_id=data['user_id'],
            client_id=client.client_id,
            scopes=scopes,
            authorized=True,
            expires_at=datetime.fromtimestamp(payload['exp'], tz=timezone.tz_info),
            last_used_time=auth.last_used_time,
        )

    @staticmethod
    async def refresh(db: AsyncSession, *, obj: CreateOpenAuthRefreshParam) -> GetOpenAuthTokenResult:
        client = await openauth_client_service.get_enabled_by_client_id(db, client_id=obj.client_id)
        OpenAuthAuthorizationService._authenticate_client(client, obj.client_secret)
        raw = await redis_client.get(refresh_token_key(obj.refresh_token))
        if not raw:
            raise errors.TokenError(msg='refresh_token 无效或已过期，请重新授权')
        data = json.loads(raw)
        if data['client_pk'] != client.id:
            raise errors.ForbiddenError(msg='refresh_token 与客户端不匹配')
        auth = await OpenAuthAuthorizationService._active_grant(db, client=client, data=data)
        if not await redis_client.get(session_key(data['sid'])):
            raise errors.TokenError(msg='设备会话已退出，请重新授权')
        scopes = [s for s in data['scopes'] if s in auth.scopes and s in client.scopes]
        if not scopes:
            raise errors.ForbiddenError(msg='已无可用权限，请重新授权')
        if await redis_client.getdel(refresh_token_key(obj.refresh_token)) != raw:
            raise errors.TokenError(msg='refresh_token 已使用，请重新授权')
        return await OpenAuthAuthorizationService._issue_tokens(
            user_id=data['user_id'],
            client=client,
            scopes=scopes,
            grant_version=auth.grant_version,
            session_id=data['sid'],
        )

    @staticmethod
    async def revoke(
        db: AsyncSession,
        *,
        user_id: int,
        client: OpenAuthClient,
        obj: CreateOpenAuthRevokeParam,
    ) -> None:
        """授权代次失效立即阻断所有设备的 code/access/refresh，无需 Redis KEYS 扫描。"""
        await openauth_user_authorization_dao.revoke(db, user_id=user_id, client_pk=client.id)

    @staticmethod
    async def logout(db: AsyncSession, *, token: str) -> None:
        # 退出只降低权限：接受签名有效的过期访问令牌，避免卸载时刷新、重放或丢失注销能力。
        # 仍严格验证签名、issuer、audience、必需 claims；不能用于读取或签发凭据。
        payload = _decode_openauth_token(token, verify_exp=False)
        await redis_client.delete(session_key(payload['sid']), access_token_key(token))

    @staticmethod
    async def list_authorizations(db: AsyncSession, *, user_id: int) -> list[GetOpenAuthUserAuthorizationDetail]:
        rows = await openauth_user_authorization_dao.list_with_clients(db, user_id=user_id)
        return [
            GetOpenAuthUserAuthorizationDetail(
                id=row.id,
                user_id=row.user_id,
                client_id=row.client_id,
                application_client_id=client_id,
                application_name=name,
                scopes=row.scopes,
                status=row.status,
                authorized_time=row.authorized_time,
                last_used_time=row.last_used_time,
                created_time=row.created_time,
            )
            for row, client_id, name in rows
        ]

    @staticmethod
    def _validate_request(client: OpenAuthClient, obj: CreateOpenAuthAuthorizationParam) -> None:
        if client.status != 1 or client.deleted:
            raise errors.ForbiddenError(msg='应用已停用或删除')
        if not set(obj.scopes) <= set(client.scopes):
            raise errors.ForbiddenError(msg='申请了未开放的权限')
        if obj.redirect_uri not in client.redirect_uris:
            raise errors.ForbiddenError(msg='回调地址未注册')

    @staticmethod
    def _authenticate_client(client: OpenAuthClient, secret: str | None) -> None:
        if client.client_type == 'public':
            return
        if not secret or not verify_client_secret(secret, client.client_secret_hash):
            raise errors.ForbiddenError(msg='客户端密钥错误')

    @staticmethod
    async def _active_grant(db: AsyncSession, *, client: OpenAuthClient, data: dict) -> OpenAuthUserAuthorization:
        auth = await openauth_user_authorization_dao.get_active_by_user_and_client(
            db,
            user_id=data['user_id'],
            client_pk=client.id,
        )
        if not auth or auth.grant_version != data['grant_version']:
            raise errors.TokenError(msg='授权关系已失效，请重新授权')
        # 不把已禁用/删除用户的第三方凭据当作有效登录态。
        await get_current_user(db, data['user_id'])
        return auth

    @staticmethod
    async def _issue_tokens(
        *,
        user_id: int,
        client: OpenAuthClient,
        scopes: list[str],
        grant_version: str,
        session_id: str | None = None,
    ) -> GetOpenAuthTokenResult:
        now = int(timezone.now().timestamp())
        if session_id is None:
            session_id = generate_token()
            await redis_client.set(session_key(session_id), '1', ex=OPENAUTH_REFRESH_TOKEN_EXPIRE_SECONDS)
        elif not await redis_client.expire(session_key(session_id), OPENAUTH_REFRESH_TOKEN_EXPIRE_SECONDS):
            # 并发 logout 后不能通过刷新重建已经退出的设备会话。
            raise errors.TokenError(msg='设备会话已退出，请重新授权')
        payload = {
            'sub': str(user_id),
            'client': client.client_id,
            'scopes': scopes,
            'grant_version': grant_version,
            'sid': session_id,
            'jti': generate_token(),
            'iss': OPENAUTH_TOKEN_ISSUER,
            'aud': OPENAUTH_TOKEN_AUDIENCE,
            'iat': now,
            'exp': now + OPENAUTH_ACCESS_TOKEN_EXPIRE_SECONDS,
        }
        access_token = jwt.encode(payload, settings.TOKEN_SECRET_KEY, algorithm=settings.TOKEN_ALGORITHM)
        refresh_token = generate_token()
        identity = json.dumps({
            'user_id': user_id,
            'client_pk': client.id,
            'scopes': scopes,
            'grant_version': grant_version,
            'sid': session_id,
        })
        await redis_client.set(access_token_key(access_token), identity, ex=OPENAUTH_ACCESS_TOKEN_EXPIRE_SECONDS)
        await redis_client.set(refresh_token_key(refresh_token), identity, ex=OPENAUTH_REFRESH_TOKEN_EXPIRE_SECONDS)
        return GetOpenAuthTokenResult(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=OPENAUTH_ACCESS_TOKEN_EXPIRE_SECONDS,
        )


openauth_authorization_service = OpenAuthAuthorizationService()
