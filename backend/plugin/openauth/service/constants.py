#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""开放平台授权中心常量与 Redis 键约定

所有临时态（授权码、access token、refresh token）全部放 Redis，
与 common/security/jwt.py 的既有姿势一致；数据库只存配置与授权关系。
"""

import base64
import hashlib
import secrets

from backend.core.conf import settings

# ------- 有效期（秒） -------
OPENAUTH_CODE_EXPIRE_SECONDS = int(getattr(settings, 'OPENAUTH_CODE_EXPIRE_SECONDS', 300))
OPENAUTH_ACCESS_TOKEN_EXPIRE_SECONDS = int(getattr(settings, 'OPENAUTH_ACCESS_TOKEN_EXPIRE_SECONDS', 7200))
OPENAUTH_REFRESH_TOKEN_EXPIRE_SECONDS = int(getattr(settings, 'OPENAUTH_REFRESH_TOKEN_EXPIRE_SECONDS', 2592000))

# ------- Redis 键前缀 -------
OPENAUTH_CODE_KEY_PREFIX = 'fba:openauth:code'
OPENAUTH_ACCESS_TOKEN_KEY_PREFIX = 'fba:openauth:token'
OPENAUTH_REFRESH_TOKEN_KEY_PREFIX = 'fba:openauth:refresh'
OPENAUTH_SESSION_KEY_PREFIX = 'fba:openauth:session'
OPENAUTH_TOKEN_ISSUER = 'fba:openauth'
OPENAUTH_TOKEN_AUDIENCE = 'fba:openauth:resource'

# ------- token payload 字段 -------
OPENAUTH_TOKEN_SCOPES_KEY = 'scopes'
OPENAUTH_TOKEN_USER_KEY = 'sub'
OPENAUTH_TOKEN_CLIENT_KEY = 'client'


def generate_code() -> str:
    """一次性授权码"""
    return secrets.token_urlsafe(32)


def generate_token() -> str:
    """access / refresh token 值"""
    return secrets.token_urlsafe(48)


def hash_client_secret(raw_secret: str) -> str:
    """客户端密钥哈希（sha256 足够：secret 为高熵随机值，防拖库反查明文）"""
    return hashlib.sha256(raw_secret.encode('utf-8')).hexdigest()


def verify_client_secret(raw_secret: str, secret_hash: str) -> bool:
    return secrets.compare_digest(hash_client_secret(raw_secret), secret_hash)


def code_key(code: str) -> str:
    return f'{OPENAUTH_CODE_KEY_PREFIX}:{hash_client_secret(code)}'


def access_token_key(token: str) -> str:
    return f'{OPENAUTH_ACCESS_TOKEN_KEY_PREFIX}:{hash_client_secret(token)}'


def refresh_token_key(token: str) -> str:
    return f'{OPENAUTH_REFRESH_TOKEN_KEY_PREFIX}:{hash_client_secret(token)}'


def session_key(session_id: str) -> str:
    return f'{OPENAUTH_SESSION_KEY_PREFIX}:{session_id}'


def pkce_challenge(verifier: str) -> str:
    return base64.urlsafe_b64encode(hashlib.sha256(verifier.encode('ascii')).digest()).rstrip(b'=').decode('ascii')


__all__ = [
    'OPENAUTH_ACCESS_TOKEN_EXPIRE_SECONDS',
    'OPENAUTH_ACCESS_TOKEN_KEY_PREFIX',
    'OPENAUTH_CODE_EXPIRE_SECONDS',
    'OPENAUTH_CODE_KEY_PREFIX',
    'OPENAUTH_REFRESH_TOKEN_EXPIRE_SECONDS',
    'OPENAUTH_REFRESH_TOKEN_KEY_PREFIX',
    'OPENAUTH_SESSION_KEY_PREFIX',
    'OPENAUTH_TOKEN_AUDIENCE',
    'OPENAUTH_TOKEN_CLIENT_KEY',
    'OPENAUTH_TOKEN_ISSUER',
    'OPENAUTH_TOKEN_SCOPES_KEY',
    'OPENAUTH_TOKEN_USER_KEY',
    'access_token_key',
    'code_key',
    'generate_code',
    'generate_token',
    'hash_client_secret',
    'pkce_challenge',
    'refresh_token_key',
    'session_key',
    'verify_client_secret',
]
