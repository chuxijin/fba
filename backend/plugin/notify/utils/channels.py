#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import hashlib
import hmac
import time
import urllib.parse

from base64 import b64encode
from collections.abc import Callable, Coroutine
from email.mime.text import MIMEText
from typing import Any

import httpx

from aiosmtplib import SMTP
from starlette.concurrency import run_in_threadpool

from backend.common.log import log
from backend.core.conf import settings


async def send_dingtalk(*, title: str, content: str, options: dict[str, str] | None = None) -> tuple[bool, str | None]:
    """
    通过钉钉机器人发送通知

    :param title: 通知标题
    :param content: 通知内容
    :param options: 渠道扩展参数
    :return:
    """
    if not settings.NOTIFY_DINGTALK_ACCESS_TOKEN:
        return False, '钉钉 access_token 未配置'

    url = settings.NOTIFY_DINGTALK_API_URL
    params: dict[str, str] = {'access_token': settings.NOTIFY_DINGTALK_ACCESS_TOKEN}

    # 加签
    if settings.NOTIFY_DINGTALK_SECRET:
        timestamp = str(round(time.time() * 1000))
        string_to_sign = f'{timestamp}\n{settings.NOTIFY_DINGTALK_SECRET}'
        hmac_code = hmac.new(
            settings.NOTIFY_DINGTALK_SECRET.encode('utf-8'),
            string_to_sign.encode('utf-8'),
            digestmod=hashlib.sha256,
        ).digest()
        sign = urllib.parse.quote_plus(b64encode(hmac_code))
        params['timestamp'] = timestamp
        params['sign'] = sign

    payload = {
        'msgtype': 'markdown',
        'markdown': {'title': title, 'text': f'### {title}\n\n{content}'},
    }

    try:
        async with httpx.AsyncClient(timeout=settings.NOTIFY_TIMEOUT) as client:
            resp = await client.post(url, params=params, json=payload)
            resp.raise_for_status()
            result = resp.json()
            if result.get('errcode') == 0:
                log.info(f'钉钉通知发送成功: {title}')
                return True, None
            error = result.get('errmsg', '未知错误')
            log.error(f'钉钉通知发送失败: {error}')
            return False, error
    except Exception as e:
        log.error(f'钉钉通知异常: {e}')
        return False, str(e)


async def send_smtp(*, title: str, content: str, options: dict[str, str] | None = None) -> tuple[bool, str | None]:
    """
    通过 SMTP 邮件发送通知

    :param title: 通知标题
    :param content: 通知内容
    :param options: 渠道扩展参数
    :return:
    """
    if not settings.NOTIFY_SMTP_USERNAME or not settings.NOTIFY_SMTP_PASSWORD:
        return False, 'SMTP 账号或密码未配置'
    if not settings.NOTIFY_SMTP_RECIPIENTS:
        return False, 'SMTP 收件人未配置'

    message = MIMEText(content, 'plain', 'utf-8')
    message['Subject'] = title
    message['From'] = settings.NOTIFY_SMTP_USERNAME
    message['To'] = ', '.join(settings.NOTIFY_SMTP_RECIPIENTS)

    try:
        smtp_client = SMTP(
            hostname=settings.NOTIFY_SMTP_HOST,
            port=settings.NOTIFY_SMTP_PORT,
            use_tls=settings.NOTIFY_SMTP_SSL,
            timeout=settings.NOTIFY_TIMEOUT,
        )
        async with smtp_client:
            await smtp_client.login(settings.NOTIFY_SMTP_USERNAME, settings.NOTIFY_SMTP_PASSWORD)
            await smtp_client.sendmail(
                settings.NOTIFY_SMTP_USERNAME,
                settings.NOTIFY_SMTP_RECIPIENTS,
                message.as_bytes(),
            )
        log.info(f'SMTP 通知发送成功: {title}')
        return True, None
    except Exception as e:
        log.error(f'SMTP 通知异常: {e}')
        return False, str(e)

async def send_serverchan(*, title: str, content: str, options: dict[str, str] | None = None) -> tuple[bool, str | None]:
    """
    通过 Server 酱³ SDK 发送通知

    :param title: 通知标题
    :param content: 通知内容
    :param options: 渠道扩展参数(支持 tags)
    :return:
    """
    if not settings.NOTIFY_SERVERCHAN_SEND_KEY:
        return False, 'Server 酱 SendKey 未配置'

    try:
        from serverchan_sdk import sc_send

        sc_options = {}
        tags = (options or {}).get('tags')
        if tags:
            sc_options['tags'] = tags

        response = await run_in_threadpool(
            sc_send,
            settings.NOTIFY_SERVERCHAN_SEND_KEY,
            title,
            content,
            sc_options if sc_options else None,
        )

        if response and response.get('code') == 0:
            log.info(f'Server 酱通知发送成功: {title}')
            return True, None
        error = response.get('message', '未知错误') if response else '无响应'
        log.error(f'Server 酱通知发送失败: {error}')
        return False, error
    except Exception as e:
        log.error(f'Server 酱通知异常: {e}')
        return False, str(e)


async def send_telegram(*, title: str, content: str, options: dict[str, str] | None = None) -> tuple[bool, str | None]:
    """
    通过 Telegram Bot 发送通知

    :param title: 通知标题
    :param content: 通知内容
    :param options: 渠道扩展参数
    :return:
    """
    if not settings.NOTIFY_TELEGRAM_BOT_TOKEN or not settings.NOTIFY_TELEGRAM_CHAT_ID:
        return False, 'Telegram Bot Token 或 Chat ID 未配置'

    url = f'{settings.NOTIFY_TELEGRAM_API_URL}/bot{settings.NOTIFY_TELEGRAM_BOT_TOKEN}/sendMessage'
    payload = {
        'chat_id': settings.NOTIFY_TELEGRAM_CHAT_ID,
        'text': f'{title}\n\n{content}',
        'disable_web_page_preview': True,
    }

    try:
        async with httpx.AsyncClient(timeout=settings.NOTIFY_TIMEOUT) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            result = resp.json()
            if result.get('ok'):
                log.info(f'Telegram 通知发送成功: {title}')
                return True, None
            error = result.get('description', '未知错误')
            log.error(f'Telegram 通知发送失败: {error}')
            return False, error
    except Exception as e:
        log.error(f'Telegram 通知异常: {e}')
        return False, str(e)


async def send_wecom(*, title: str, content: str, options: dict[str, str] | None = None) -> tuple[bool, str | None]:
    """
    通过企业微信机器人发送通知

    :param title: 通知标题
    :param content: 通知内容
    :param options: 渠道扩展参数
    :return:
    """
    if not settings.NOTIFY_WECOM_WEBHOOK_KEY:
        return False, '企业微信 Webhook Key 未配置'

    url = settings.NOTIFY_WECOM_API_URL
    params = {'key': settings.NOTIFY_WECOM_WEBHOOK_KEY}
    payload = {
        'msgtype': 'markdown',
        'markdown': {'content': f'### {title}\n\n{content}'},
    }

    try:
        async with httpx.AsyncClient(timeout=settings.NOTIFY_TIMEOUT) as client:
            resp = await client.post(url, params=params, json=payload)
            resp.raise_for_status()
            result = resp.json()
            if result.get('errcode') == 0:
                log.info(f'企业微信通知发送成功: {title}')
                return True, None
            error = result.get('errmsg', '未知错误')
            log.error(f'企业微信通知发送失败: {error}')
            return False, error
    except Exception as e:
        log.error(f'企业微信通知异常: {e}')
        return False, str(e)


# 渠道名称 -> 发送函数映射
ChannelHandler = Callable[..., Coroutine[Any, Any, tuple[bool, str | None]]]

CHANNEL_HANDLERS: dict[str, ChannelHandler] = {
    'dingtalk': send_dingtalk,
    'smtp': send_smtp,
    'serverchan': send_serverchan,
    'telegram': send_telegram,
    'wecom': send_wecom,
}

# 渠道名称 -> 启用配置属性名映射
CHANNEL_ENABLED_MAP: dict[str, str] = {
    'dingtalk': 'NOTIFY_DINGTALK_ENABLED',
    'smtp': 'NOTIFY_SMTP_ENABLED',
    'serverchan': 'NOTIFY_SERVERCHAN_ENABLED',
    'telegram': 'NOTIFY_TELEGRAM_ENABLED',
    'wecom': 'NOTIFY_WECOM_ENABLED',
}
