"""开放平台资源接口必须在服务端验证 Bearer 和 scope，不能信任 CLI 的预先 check。"""

from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.common.exception import errors
from backend.database.db import CurrentSessionTransaction
from backend.plugin.openauth.schema.authorization import GetOpenAuthCheckResult
from backend.plugin.openauth.service.authorization_service import openauth_authorization_service

_bearer = HTTPBearer(auto_error=False, scheme_name='OpenAuthBearer')


def get_openauth_bearer(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> str:
    if credentials is None:
        raise errors.TokenError(msg='缺少开放平台 Bearer token')
    return credentials.credentials


OpenAuthBearerToken = Annotated[str, Depends(get_openauth_bearer)]


class RequireOpenAuth:
    def __init__(self, *scopes: str) -> None:
        self.scopes = frozenset(scopes)

    async def __call__(self, db: CurrentSessionTransaction, token: OpenAuthBearerToken) -> GetOpenAuthCheckResult:
        identity = await openauth_authorization_service.check(db, token=token)
        if not self.scopes <= set(identity.scopes):
            raise errors.ForbiddenError(msg='缺少所需开放平台权限')
        return identity
