from fastapi import Request

from backend.app.admin.schema.user import GetUserInfoWithRelationDetail
from backend.common.exception import errors
from backend.common.security.jwt import jwt_authentication


async def get_public_user(*, request: Request) -> GetUserInfoWithRelationDetail | None:
    """公开接口仅允许无凭据游客；已提交的凭据必须通过完整会话校验。"""
    authorization = request.headers.get('authorization')
    if not authorization:
        return None
    scheme, _, token = authorization.partition(' ')
    if scheme.lower() != 'bearer' or not token.strip():
        raise errors.TokenError(msg='登录凭据无效，请重新登录')
    return await jwt_authentication(token.strip())
