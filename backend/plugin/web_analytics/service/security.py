import hashlib
import hmac
import ipaddress
import json
import secrets

from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from backend.core.conf import settings
from backend.plugin.web_analytics.constants import SENSITIVE_QUERY_KEYS


def generate_site_key() -> str:
    return f'wa_{secrets.token_urlsafe(12)}'[:32]


def digest_identifier(site_key: str, value: str) -> str:
    salt = str(getattr(settings, 'WEB_ANALYTICS_HASH_SALT', settings.TOKEN_SECRET_KEY))
    if salt == 'change-me-before-production':
        salt = settings.TOKEN_SECRET_KEY
    return hmac.new(salt.encode(), f'{site_key}:{value}'.encode(), hashlib.sha256).hexdigest()


def anonymize_ip(ip: str) -> str:
    try:
        address = ipaddress.ip_address(ip)
    except ValueError:
        return 'unknown'
    prefix = 24 if address.version == 4 else 48
    return str(ipaddress.ip_network(f'{address}/{prefix}', strict=False).network_address)


def sanitize_url(value: str | None, *, default: str = '/') -> str | None:
    if value is None:
        return None
    value = value.strip()
    if not value:
        return default
    parts = urlsplit(value)
    filtered_query = urlencode([
        (key, '[redacted]' if key.lower() in SENSITIVE_QUERY_KEYS else item)
        for key, item in parse_qsl(parts.query, keep_blank_values=True)
    ])
    sanitized = urlunsplit((parts.scheme, parts.netloc, parts.path or '/', filtered_query, ''))
    return sanitized[:2048]


def source_host(origin: str | None, referer: str | None) -> str | None:
    source = origin or referer
    if not source:
        return None
    try:
        return (urlsplit(source).hostname or '').lower().rstrip('.') or None
    except ValueError:
        return None


def domain_allowed(host: str | None, domains: list[str]) -> bool:
    if host is None:
        return False
    return any(host == domain or host.endswith(f'.{domain}') for domain in domains)


def sanitize_properties(properties: dict[str, Any] | None) -> dict[str, Any] | None:
    if not properties:
        return None
    clean: dict[str, Any] = {}
    for index, (key, value) in enumerate(properties.items()):
        if index >= 30:
            break
        normalized_key = str(key)[:64]
        if normalized_key.lower() in SENSITIVE_QUERY_KEYS:
            clean[normalized_key] = '[redacted]'
        elif isinstance(value, (bool, int, float)) or value is None:
            clean[normalized_key] = value
        elif isinstance(value, str):
            clean[normalized_key] = value[:512]
        else:
            clean[normalized_key] = json.dumps(value, ensure_ascii=True, separators=(',', ':'))[:1024]
    return clean or None
