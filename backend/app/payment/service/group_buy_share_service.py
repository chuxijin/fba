#!/usr/bin/env python3
import base64
import json

import httpx

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.payment.crud.crud_group_buy import group_buy_dao
from backend.common.exception import errors
from backend.core.conf import settings
from backend.database.redis import redis_client
from backend.plugin.oauth2.service.wechat_scan_service import WechatScanService
from backend.utils.timezone import timezone


class GroupBuyShareService:
    @staticmethod
    async def qrcode(db: AsyncSession, *, code: str, user_id: int) -> dict:
        team = await group_buy_dao.team(db, code)
        if not team or team.status != 'forming' or not team.deadline or timezone.now() >= team.deadline:
            raise errors.RequestError(msg='只有进行中的拼团可以生成邀请小程序码')
        members = await group_buy_dao.members(db, team.id)
        if not any(m.user_id == user_id and m.status == 'paid' for m in members):
            raise errors.ForbiddenError(msg='请先完成本人参团付款，再邀请好友')
        version = 'release' if settings.ENVIRONMENT == 'prod' else 'trial'
        key = f'payment:group-buy:qrcode:{version}:{code}'
        cached = await redis_client.get(key)
        if cached:
            return json.loads(cached)
        token = await WechatScanService.get_access_token()
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                'https://api.weixin.qq.com/wxa/getwxacodeunlimit',
                params={'access_token': token},
                json={
                    'scene': f'gb_{code}',
                    'page': 'pkg/mine/group-buy/index',
                    'width': 430,
                    'env_version': version,
                    'check_path': settings.ENVIRONMENT == 'prod',
                    'auto_color': False,
                    'line_color': {'r': 15, 'g': 118, 'b': 110},
                },
            )
        content_type = response.headers.get('content-type', '').split(';')[0]
        if response.status_code != 200 or content_type not in ('image/png', 'image/jpeg'):
            raise errors.GatewayError(msg='小程序码生成失败，请确认该页面已上传到对应微信版本，或先复制拼团码邀请')
        result = {
            'data_url': f'data:{content_type};base64,{base64.b64encode(response.content).decode()}',
            'share_code': code,
            'deadline': team.deadline.isoformat(),
        }
        await redis_client.set(
            key, json.dumps(result), ex=max(1, min(3600, int((team.deadline - timezone.now()).total_seconds())))
        )
        return result


group_buy_share_service = GroupBuyShareService()
