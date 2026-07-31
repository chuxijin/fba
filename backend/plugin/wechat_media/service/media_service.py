import asyncio
import base64
import binascii
import json
import time

from pathlib import Path

import httpx

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi import UploadFile

from backend.common.exception import errors
from backend.core.conf import settings

WECHAT_TOKEN_URL = 'https://api.weixin.qq.com/cgi-bin/token'
WECHAT_UPLOAD_IMAGE_URL = 'https://api.weixin.qq.com/cgi-bin/media/uploadimg'
SUPPORTED_IMAGE_EXTENSIONS = {'jpg', 'jpeg', 'png'}
PAYLOAD_MAX_AGE_SECONDS = 600


def _required_setting(name: str) -> str:
    value = str(getattr(settings, name, '')).strip()
    if not value:
        raise errors.ServerError(msg=f'微信公众号素材中转未配置 {name}')
    return value


class WechatMediaService:
    def __init__(self) -> None:
        self._token_cache: dict[str, tuple[str, float]] = {}
        self._token_lock = asyncio.Lock()

    @staticmethod
    def _wechat_error(data: dict, action: str) -> errors.GatewayError:
        code = data.get('errcode', '')
        message = data.get('errmsg', '微信接口返回未知错误')
        return errors.GatewayError(msg=f'{action}失败：{code} {message}')

    def _load_secret_key(self) -> bytes:
        raw = _required_setting('WECHAT_MEDIA_SECRET_KEY')
        try:
            key = base64.b64decode(raw, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise errors.ServerError(msg='微信公众号素材中转密钥格式无效，应为 base64 字符串') from exc
        if len(key) != 32:
            raise errors.ServerError(msg='微信公众号素材中转密钥长度无效，应为 32 字节')
        return key

    def decrypt_credentials(self, payload: str) -> dict[str, str]:
        try:
            raw = base64.b64decode(payload, validate=True)
            if len(raw) <= 12 + 16:
                raise ValueError('payload 长度不足')
            nonce, ciphertext = raw[:12], raw[12:]
            plaintext = AESGCM(self._load_secret_key()).decrypt(nonce, ciphertext, None)
            data = json.loads(plaintext.decode('utf-8'))
        except Exception as exc:
            raise errors.AuthorizationError(msg='素材中转凭证解密失败') from exc

        appid = str(data.get('appid') or '').strip()
        appsecret = str(data.get('appsecret') or '').strip()
        if not appid or not appsecret:
            raise errors.AuthorizationError(msg='素材中转凭证缺少 appid 或 appsecret')
        issued_at = data.get('iat')
        if isinstance(issued_at, (int, float)) and abs(time.time() - float(issued_at)) > PAYLOAD_MAX_AGE_SECONDS:
            raise errors.AuthorizationError(msg='素材中转凭证已过期，请重试')
        return {'appid': appid, 'appsecret': appsecret}

    async def get_access_token(self, appid: str, appsecret: str) -> str:
        cached = self._token_cache.get(appid)
        if cached and time.monotonic() < cached[1]:
            return cached[0]

        async with self._token_lock:
            cached = self._token_cache.get(appid)
            if cached and time.monotonic() < cached[1]:
                return cached[0]

            try:
                async with httpx.AsyncClient(timeout=15) as client:
                    response = await client.get(
                        WECHAT_TOKEN_URL,
                        params={
                            'grant_type': 'client_credential',
                            'appid': appid,
                            'secret': appsecret,
                        },
                    )
                    response.raise_for_status()
                    data = response.json()
            except (httpx.HTTPError, ValueError) as exc:
                raise errors.GatewayError(msg=f'连接微信 token 接口失败：{exc!s}') from exc

            token = data.get('access_token')
            if not token:
                raise self._wechat_error(data, '获取微信 access_token')

            expires_in = max(int(data.get('expires_in', 7200)), 300)
            self._token_cache[appid] = (str(token), time.monotonic() + expires_in - 120)
            return self._token_cache[appid][0]

    @staticmethod
    def _validate_image(file: UploadFile) -> None:
        filename = file.filename or ''
        extension = Path(filename).suffix.lower().lstrip('.')
        if extension not in SUPPORTED_IMAGE_EXTENSIONS:
            raise errors.RequestError(msg='微信公众号文章图片仅支持 JPG 和 PNG 格式')

        max_size = int(getattr(settings, 'WECHAT_MEDIA_IMAGE_SIZE_MAX', 10 * 1024 * 1024))
        if file.size is not None and file.size > max_size:
            raise errors.RequestError(msg=f'图片不能超过 {max_size // 1024 // 1024} MB')

    async def upload_article_image(self, file: UploadFile, appid: str, appsecret: str) -> str:
        self._validate_image(file)
        access_token = await self.get_access_token(appid, appsecret)
        await file.seek(0)
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(
                    WECHAT_UPLOAD_IMAGE_URL,
                    params={'access_token': access_token},
                    files={
                        'media': (
                            file.filename or 'image.jpg',
                            file.file,
                            file.content_type or 'application/octet-stream',
                        )
                    },
                )
                response.raise_for_status()
                data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise errors.GatewayError(msg=f'连接微信图片上传接口失败：{exc!s}') from exc

        url = data.get('url')
        if not url:
            raise self._wechat_error(data, '上传微信公众号文章图片')
        return str(url)


media_service = WechatMediaService()
