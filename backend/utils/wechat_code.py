#!/usr/bin/env python3
import base64
import hashlib

import httpx

from backend.common.exception import errors
from backend.core.conf import settings
from backend.database.redis import redis_client
from backend.plugin.oauth2.service.wechat_scan_service import WechatScanService


async def create_miniapp_code(*, page: str, scene: str, ttl: int = 3600) -> str:
    """业务服务完成权限/有效期校验后调用，二维码只包含公开落地参数。"""
    version = 'release' if settings.ENVIRONMENT == 'prod' else 'trial'
    identity = hashlib.sha256(f'{version}:{page}:{scene}'.encode()).hexdigest()
    key = f'miniapp:share-code:{identity}'
    cached = await redis_client.get(key)
    if cached:
        return cached.decode() if isinstance(cached, bytes) else cached
    token = await WechatScanService.get_access_token()
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(
            'https://api.weixin.qq.com/wxa/getwxacodeunlimit',
            params={'access_token': token},
            json={
                'scene': scene,
                'page': page,
                'width': 430,
                'env_version': version,
                'check_path': settings.ENVIRONMENT == 'prod',
                'auto_color': False,
                'line_color': {'r': 22, 'g': 128, 'b': 96},
            },
        )
    content_type = response.headers.get('content-type', '').split(';')[0]
    if response.status_code != 200 or content_type not in ('image/png', 'image/jpeg'):
        raise errors.GatewayError(msg='小程序码生成失败，请确认页面已上传到对应微信版本')
    data_url = f'data:{content_type};base64,{base64.b64encode(response.content).decode()}'
    await redis_client.set(key, data_url, ex=max(1, min(ttl, 3600)))
    return data_url
