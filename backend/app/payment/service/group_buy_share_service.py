#!/usr/bin/env python3
import base64
import json
import re

from datetime import datetime, timedelta
from typing import Literal
from urllib.parse import urlsplit

import httpx

from redis.exceptions import LockError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.payment.crud.crud_group_buy import group_buy_dao
from backend.common.exception import errors
from backend.core.conf import settings
from backend.database.redis import redis_client
from backend.plugin.oauth2.service.wechat_scan_service import WechatScanService
from backend.utils.timezone import timezone

PAGE = 'pkg/mine/group-buy/index'


class GroupBuyShareService:
    @staticmethod
    async def _eligible(db: AsyncSession, code: str, user_id: int) -> dict:
        if not re.fullmatch(r'[a-f0-9]{24}', code):
            raise errors.RequestError(msg='拼团码无效')
        context = await group_buy_dao.share_context(db, code, user_id)
        if (
            not context
            or context['status'] != 'forming'
            or not context['deadline']
            or timezone.now() >= context['deadline']
        ):
            raise errors.RequestError(msg='只有进行中且未到期的拼团可以生成邀请内容')
        if context['member_status'] != 'paid':
            raise errors.ForbiddenError(msg='请先完成本人参团付款，再邀请好友')
        return context

    @staticmethod
    async def _post(endpoint: str, payload: dict) -> httpx.Response:
        try:
            token = await WechatScanService.get_access_token()
            async with httpx.AsyncClient(timeout=15) as client:
                return await client.post(
                    f'https://api.weixin.qq.com/{endpoint}',
                    params={'access_token': token},
                    json=payload,
                )
        except (httpx.HTTPError, errors.BaseExceptionError) as exc:
            # 不把包含 access_token 的请求地址或微信原始响应返回给客户端。
            raise errors.GatewayError(msg='微信分享服务暂不可用，请稍后重试或使用卡片／口令') from exc

    @staticmethod
    def _json(response: httpx.Response) -> dict:
        try:
            data = response.json()
        except (ValueError, UnicodeError):
            data = {}
        if not isinstance(data, dict):
            data = {}
        if response.status_code != 200 or data.get('errcode', 0):
            if data.get('errcode') in (40002, 43104, 85407):
                raise errors.GatewayError(msg='当前小程序暂无此链接权限，请使用另一种链接或卡片／口令')
            if data.get('errcode') in (85079, 40165, 40066):
                raise errors.GatewayError(msg='请先发布包含拼团详情页的小程序正式版，再生成此分享内容')
            raise errors.GatewayError(msg='微信分享内容生成失败，请稍后重试或使用卡片／口令')
        return data

    @staticmethod
    async def _cached(key: str) -> dict | None:
        cached = await redis_client.get(key)
        if cached:
            try:
                value = json.loads(cached)
                return value if isinstance(value, dict) else None
            except (ValueError, TypeError):
                pass
        return None

    @staticmethod
    async def _store(key: str, result: dict, deadline: datetime) -> None:
        remaining = int((deadline - timezone.now()).total_seconds())
        if remaining <= 0:
            raise errors.RequestError(msg='拼团已到期，不能继续生成邀请内容')
        await redis_client.set(key, json.dumps(result), ex=remaining)

    @staticmethod
    def _validated_link(data: dict, kind: Literal['short', 'url']) -> str:
        link = data.get('link' if kind == 'short' else 'url_link', '')
        valid = isinstance(link, str) and len(link) <= 2048 and not re.search(r'[\x00-\x1f\x7f]', link)
        if valid and kind == 'short':
            valid = link.startswith('#小程序://') and len(link) > len('#小程序://')
        elif valid:
            try:
                parsed = urlsplit(link)
                valid = (
                    parsed.scheme == 'https'
                    and parsed.netloc in ('wxaurl.cn', 'wxmpurl.cn')
                    and bool(parsed.path.strip('/'))
                )
            except ValueError:
                valid = False
        if not valid:
            raise errors.GatewayError(msg='微信返回的邀请链接无效，请使用卡片或口令')
        return link

    @staticmethod
    async def qrcode(
        db: AsyncSession, *, code: str, user_id: int, style: Literal['miniapp', 'square'] = 'miniapp'
    ) -> dict:
        if style not in ('miniapp', 'square'):
            raise errors.RequestError(msg='不支持的邀请二维码类型')
        await GroupBuyShareService._eligible(db, code, user_id)
        # 微信方形二维码接口只支持已发布页面，不把正式码伪装成开发／体验码。
        version = 'release' if style == 'square' or settings.ENVIRONMENT == 'prod' else 'trial'
        key = f'payment:group-buy:share-code:{style}:{version}:{code}'
        cached = await GroupBuyShareService._cached(key)
        if cached:
            return cached
        try:
            async with redis_client.lock(f'{key}:lock', timeout=45, blocking_timeout=3):
                await GroupBuyShareService._eligible(db, code, user_id)
                cached = await GroupBuyShareService._cached(key)
                if cached:
                    return cached
                if style == 'square':
                    endpoint = 'cgi-bin/wxaapp/createwxaqrcode'
                    payload = {'path': f'{PAGE}?group_code={code}', 'width': 430}
                else:
                    endpoint = 'wxa/getwxacodeunlimit'
                    payload = {
                        'scene': f'gb_{code}',
                        'page': PAGE,
                        'width': 430,
                        'env_version': version,
                        'check_path': settings.ENVIRONMENT == 'prod',
                        'auto_color': False,
                        'line_color': {'r': 15, 'g': 118, 'b': 110},
                    }
                response = await GroupBuyShareService._post(endpoint, payload)
                content_type = response.headers.get('content-type', '').split(';')[0].strip().lower()
                if response.status_code != 200 or content_type not in ('image/png', 'image/jpeg'):
                    GroupBuyShareService._json(response)
                    raise errors.GatewayError(msg='邀请二维码生成失败，请确认页面已发布，或先使用卡片／口令')
                if not response.content:
                    raise errors.GatewayError(msg='微信返回的邀请二维码为空，请重试')
                context = await GroupBuyShareService._eligible(db, code, user_id)
                result = {
                    'data_url': f'data:{content_type};base64,{base64.b64encode(response.content).decode()}',
                    'share_code': code,
                    'deadline': context['deadline'].isoformat(),
                    'style': style,
                    'env_version': version,
                }
                await GroupBuyShareService._store(key, result, context['deadline'])
                return result
        except LockError as exc:
            raise errors.RequestError(msg='邀请内容正在生成，请稍后重试') from exc

    @staticmethod
    async def link(
        db: AsyncSession, *, code: str, user_id: int, kind: Literal['short', 'url'] = 'short'
    ) -> dict:
        if kind not in ('short', 'url'):
            raise errors.RequestError(msg='不支持的邀请链接类型')
        await GroupBuyShareService._eligible(db, code, user_id)
        key = f'payment:group-buy:share-link:{kind}:release:{code}'
        cached = await GroupBuyShareService._cached(key)
        if cached:
            return cached
        try:
            async with redis_client.lock(f'{key}:lock', timeout=45, blocking_timeout=3):
                context = await GroupBuyShareService._eligible(db, code, user_id)
                cached = await GroupBuyShareService._cached(key)
                if cached:
                    return cached
                now = timezone.now()
                if kind == 'short':
                    name = str(context['snapshot'].get('base', {}).get('name') or '订阅套餐')
                    payload = {
                        'page_url': f'{PAGE}?group_code={code}',
                        'page_title': f'一起拼「{name}」'[:20],
                        'is_permanent': False,
                    }
                    endpoint = 'wxa/genwxashortlink'
                    expires_at = now + timedelta(days=30)
                else:
                    expires_at = context['deadline']
                    if (expires_at - now).total_seconds() <= 60:
                        raise errors.RequestError(msg='本团剩余时间不足一分钟，请使用卡片或口令')
                    endpoint = 'wxa/generate_urllink'
                    payload = {
                        'path': PAGE,
                        'query': f'group_code={code}',
                        'expire_type': 0,
                        'expire_time': int(expires_at.timestamp()),
                        'env_version': 'release',
                    }
                data = GroupBuyShareService._json(await GroupBuyShareService._post(endpoint, payload))
                link = GroupBuyShareService._validated_link(data, kind)
                context = await GroupBuyShareService._eligible(db, code, user_id)
                result = {
                    'link': link,
                    'kind': kind,
                    'share_code': code,
                    'deadline': context['deadline'].isoformat(),
                    'expires_at': expires_at.isoformat(),
                }
                await GroupBuyShareService._store(key, result, min(context['deadline'], expires_at))
                return result
        except LockError as exc:
            raise errors.RequestError(msg='邀请链接正在生成，请稍后重试') from exc


group_buy_share_service = GroupBuyShareService()
