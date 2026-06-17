#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import base64
import hashlib
import hmac
import time
import uuid

from backend.plugin.webhook.constant import (
    EVENT_ID_PREFIX,
    SECRET_PREFIX,
    TIMESTAMP_TOLERANCE,
)


def generate_id(prefix: str = EVENT_ID_PREFIX) -> str:
    """
    生成唯一 ID

    :param prefix: ID 前缀
    :return:
    """
    return f'{prefix}{uuid.uuid4().hex[:24]}'


def generate_secret() -> str:
    """
    生成 Standard Webhooks 密钥 (whsec_ 前缀 + base64 随机字节)

    :return:
    """
    raw = base64.b64encode(uuid.uuid4().bytes + uuid.uuid4().bytes).decode()
    return f'{SECRET_PREFIX}{raw}'


def sign(secret: str, msg_id: str, timestamp: int, body: bytes) -> str:
    """
    Standard Webhooks 签名生成

    :param secret: whsec_ 开头的密钥
    :param msg_id: webhook-id
    :param timestamp: Unix 时间戳 (秒)
    :param body: 原始请求体
    :return: v1,<base64_signature>
    """
    secret_bytes = _decode_secret(secret)
    to_sign = f'{msg_id}.{timestamp}.{body.decode("utf-8")}'
    signature = hmac.new(secret_bytes, to_sign.encode('utf-8'), hashlib.sha256).digest()
    return f'v1,{base64.b64encode(signature).decode()}'


def verify(
    secret: str,
    msg_id: str,
    timestamp: str,
    signature_header: str,
    body: bytes,
) -> bool:
    """
    Standard Webhooks 签名验证

    :param secret: whsec_ 开头的密钥
    :param msg_id: webhook-id 头部
    :param timestamp: webhook-timestamp 头部
    :param signature_header: webhook-signature 头部
    :param body: 原始请求体
    :return: 验证是否通过
    :raises ValueError: 时间戳过期或签名格式错误
    """
    # 1. 时间戳校验
    try:
        ts = int(timestamp)
    except (ValueError, TypeError):
        raise ValueError('无效的时间戳格式')

    now = int(time.time())
    if abs(now - ts) > TIMESTAMP_TOLERANCE:
        raise ValueError(f'时间戳过期 (偏差 {abs(now - ts)}s > {TIMESTAMP_TOLERANCE}s)')

    # 2. 解析签名 (支持多个签名空格分隔, 用于密钥轮换)
    signatures = signature_header.split(' ')
    secret_bytes = _decode_secret(secret)
    to_sign = f'{msg_id}.{timestamp}.{body.decode("utf-8")}'
    expected = hmac.new(secret_bytes, to_sign.encode('utf-8'), hashlib.sha256).digest()

    for sig in signatures:
        if not sig.startswith('v1,'):
            continue
        try:
            sig_bytes = base64.b64decode(sig[3:])
        except Exception:
            continue
        if hmac.compare_digest(sig_bytes, expected):
            return True

    raise ValueError('签名验证失败')


def _decode_secret(secret: str) -> bytes:
    """
    解码 whsec_ 前缀密钥

    :param secret: 带前缀的密钥
    :return:
    """
    raw = secret
    if raw.startswith(SECRET_PREFIX):
        raw = raw[len(SECRET_PREFIX) :]
    return base64.b64decode(raw)
