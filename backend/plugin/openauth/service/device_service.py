import json
import secrets

from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.exception import errors
from backend.database.redis import redis_client
from backend.plugin.openauth.schema.device import GetOpenAuthDeviceRevokePreview, GetOpenAuthDeviceRevokeTicket
from backend.plugin.openauth.service.authorization_service import _decode_openauth_token, openauth_authorization_service
from backend.plugin.openauth.service.client_service import openauth_client_service
from backend.plugin.openauth.service.constants import hash_client_secret, session_key


def ticket_key(ticket: str) -> str:
    return f'fba:openauth:revoke_ticket:{hash_client_secret(ticket)}'


class OpenAuthDeviceService:
    @staticmethod
    async def create_ticket(db: AsyncSession, *, token: str) -> GetOpenAuthDeviceRevokeTicket:
        await openauth_authorization_service.check(db, token=token)
        payload = _decode_openauth_token(token)
        ticket = secrets.token_urlsafe(32)
        await redis_client.set(
            ticket_key(ticket),
            json.dumps({
                'user_id': int(payload['sub']),
                'client_id': payload['client'],
                'sid': payload['sid'],
            }),
            ex=600,
        )
        return GetOpenAuthDeviceRevokeTicket(ticket=ticket, expires_in=600)

    @staticmethod
    async def _owned_ticket(*, user_id: int, ticket: str) -> tuple[str, dict]:
        raw = await redis_client.get(ticket_key(ticket))
        if not raw:
            raise errors.NotFoundError(msg='解绑链接已失效，请重新发起')
        data = json.loads(raw)
        if data['user_id'] != user_id:
            raise errors.ForbiddenError(msg='请使用发起解绑时的同一账号登录')
        return raw, data

    @staticmethod
    async def preview(db: AsyncSession, *, user_id: int, ticket: str) -> GetOpenAuthDeviceRevokePreview:
        _, data = await OpenAuthDeviceService._owned_ticket(user_id=user_id, ticket=ticket)
        client = await openauth_client_service.get_by_client_id(db, client_id=data['client_id'])
        return GetOpenAuthDeviceRevokePreview(
            application_name=client.name,
            active=bool(await redis_client.get(session_key(data['sid']))),
        )

    @staticmethod
    async def revoke(*, user_id: int, ticket: str) -> None:
        _, data = await OpenAuthDeviceService._owned_ticket(user_id=user_id, ticket=ticket)
        # 先删除目标会话，再消耗票据；网络/Redis 故障下可以安全重试，不丢失注销能力。
        await redis_client.delete(session_key(data['sid']))
        await redis_client.delete(ticket_key(ticket))


openauth_device_service = OpenAuthDeviceService()
