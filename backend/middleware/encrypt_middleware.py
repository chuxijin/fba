import base64
import json

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from backend.core.conf import settings
from backend.utils.encrypt import AESCipher


class EncryptMiddleware(BaseHTTPMiddleware):
    """响应加密中间件：对匹配路径的 JSON 响应 data 字段进行 AES 加密"""

    def __init__(self, app) -> None:
        super().__init__(app)
        if settings.RESPONSE_ENCRYPT_SECRET_KEY:
            self._cipher = AESCipher(settings.RESPONSE_ENCRYPT_SECRET_KEY)
        else:
            self._cipher = None

    def _should_encrypt(self, path: str) -> bool:
        """判断该路径是否需要加密"""
        # 如果配置了 include 列表，则只加密匹配的路径
        if settings.RESPONSE_ENCRYPT_INCLUDE:
            return any(path.startswith(prefix) for prefix in settings.RESPONSE_ENCRYPT_INCLUDE)

        # include 为空则加密所有 API 路径
        return path.startswith(settings.FASTAPI_API_V1_PATH)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)

        # 前置检查：未启用 / 无密钥 / 路径不匹配 / 非 JSON 响应
        if not settings.RESPONSE_ENCRYPT_ENABLED or not self._cipher:
            return response
        if not self._should_encrypt(request.url.path):
            return response

        content_type = response.headers.get('content-type', '')
        if 'application/json' not in content_type:
            return response

        # 读取响应体
        body_chunks = []
        async for chunk in response.body_iterator:
            if isinstance(chunk, str):
                body_chunks.append(chunk.encode('utf-8'))
            else:
                body_chunks.append(chunk)
        body = b''.join(body_chunks)

        # 解析 JSON，加密 data 字段
        try:
            payload = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return Response(content=body, status_code=response.status_code, headers=dict(response.headers))

        if not isinstance(payload, dict) or 'data' not in payload or payload.get('data') is None:
            return Response(content=body, status_code=response.status_code, headers=dict(response.headers))

        data_json = json.dumps(payload['data'], ensure_ascii=False)
        encrypted_bytes = self._cipher.encrypt(data_json)
        payload['data'] = base64.b64encode(encrypted_bytes).decode('ascii')
        payload['encrypted'] = True

        new_body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        headers = dict(response.headers)
        headers['content-length'] = str(len(new_body))

        return Response(content=new_body, status_code=response.status_code, headers=headers)
