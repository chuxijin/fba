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
from backend.database.redis import redis_client


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


async def send_wecom_app(*, title: str, content: str, options: dict[str, str] | None = None) -> tuple[bool, str | None]:
    """
    通过企业微信自建应用发送通知 (类似 wecomchan)

    :param title: 通知标题
    :param content: 通知内容
    :param options: 渠道扩展参数
    :return:
    """
    if not settings.NOTIFY_WECOM_APP_CORPID or not settings.NOTIFY_WECOM_APP_CORPSECRET:
        return False, '企业微信自建应用 CORPID 或 CORPSECRET 未配置'
    if not settings.NOTIFY_WECOM_APP_AGENTID:
        return False, '企业微信自建应用 AGENTID 未配置'

    # 获取 access_token (从 Redis 缓存或直接请求)
    token_cache_key = 'fba:notify:wecom_app:access_token'
    try:
        access_token = await redis_client.get(token_cache_key)
    except Exception as e:
        log.warning(f'从 Redis 读取 wecom_app access_token 失败: {e}')
        access_token = None

    if not access_token:
        try:
            async with httpx.AsyncClient(timeout=settings.NOTIFY_TIMEOUT) as client:
                url = 'https://qyapi.weixin.qq.com/cgi-bin/gettoken'
                params = {
                    'corpid': settings.NOTIFY_WECOM_APP_CORPID,
                    'corpsecret': settings.NOTIFY_WECOM_APP_CORPSECRET,
                }
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                result = resp.json()
                if result.get('errcode') == 0:
                    access_token = result.get('access_token')
                    expires_in = result.get('expires_in', 7200)
                    try:
                        # 缓存 token，并提前 5 分钟失效以防边界情况
                        await redis_client.set(token_cache_key, access_token, ex=max(60, expires_in - 300))
                    except Exception as e:
                        log.warning(f'缓存 wecom_app access_token 到 Redis 失败: {e}')
                else:
                    error_msg = result.get('errmsg', '未知错误')
                    log.error(f'获取企业微信自建应用 access_token 失败: {error_msg}')
                    return False, f'获取 token 失败: {error_msg}'
        except Exception as e:
            log.error(f'获取企业微信自建应用 access_token 异常: {e}')
            return False, f'获取 token 异常: {e}'

    # 发送应用消息
    send_url = f'https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={access_token}'
    
    opts = options or {}
    msgtype = opts.get('msgtype') or settings.NOTIFY_WECOM_APP_MSGTYPE or 'markdown'
    touser = settings.NOTIFY_WECOM_APP_TOUSER or '@all'

    if msgtype == 'markdown':
        payload = {
            'touser': touser,
            'msgtype': 'markdown',
            'agentid': settings.NOTIFY_WECOM_APP_AGENTID,
            'markdown': {'content': f'### {title}\n\n{content}'},
            'safe': 0,
            'enable_id_trans': 0,
            'enable_duplicate_check': 0,
        }
    elif msgtype == 'textcard':
        payload = {
            'touser': touser,
            'msgtype': 'textcard',
            'agentid': settings.NOTIFY_WECOM_APP_AGENTID,
            'textcard': {
                'title': title,
                'description': content,
                'url': opts.get('url') or 'https://work.weixin.qq.com',
                'btntxt': opts.get('btntxt') or '详情',
            },
            'safe': 0,
            'enable_id_trans': 0,
            'enable_duplicate_check': 0,
        }
    elif msgtype == 'template_card':
        template_card_data = opts.get('template_card')
        if isinstance(template_card_data, str):
            import json
            try:
                template_card_data = json.loads(template_card_data)
            except Exception as e:
                log.error(f'解析 template_card JSON 异常: {e}')
                return False, f'解析 template_card JSON 异常: {e}'
        if not template_card_data:
            return False, '发送 template_card 时缺少 template_card 配置参数'
        payload = {
            'touser': touser,
            'msgtype': 'template_card',
            'agentid': settings.NOTIFY_WECOM_APP_AGENTID,
            'template_card': template_card_data,
            'enable_id_trans': int(opts.get('enable_id_trans', 0)),
            'enable_duplicate_check': int(opts.get('enable_duplicate_check', 0)),
        }
        if 'duplicate_check_interval' in opts:
            payload['duplicate_check_interval'] = int(opts['duplicate_check_interval'])
    else:
        payload = {
            'touser': touser,
            'msgtype': 'text',
            'agentid': settings.NOTIFY_WECOM_APP_AGENTID,
            'text': {'content': f'{title}\n\n{content}'},
            'safe': 0,
            'enable_id_trans': 0,
            'enable_duplicate_check': 0,
        }

    try:
        async with httpx.AsyncClient(timeout=settings.NOTIFY_TIMEOUT) as client:
            resp = await client.post(send_url, json=payload)
            resp.raise_for_status()
            result = resp.json()
            if result.get('errcode') == 0:
                log.info(f'企业微信自建应用通知发送成功: {title}')
                return True, None

            errcode = result.get('errcode')
            # 如果是 token 失效相关的错误，主动清除 Redis 缓存
            if errcode in (40014, 42001):
                try:
                    await redis_client.delete(token_cache_key)
                except Exception as e:
                    log.warning(f'删除 wecom_app access_token 缓存失败: {e}')

            error = result.get('errmsg', '未知错误')
            log.error(f'企业微信自建应用通知发送失败: {error}')
            return False, error
    except Exception as e:
        log.error(f'企业微信自建应用通知异常: {e}')
        return False, str(e)


async def update_wecom_app_template_card(
    *,
    response_code: str,
    replace_text: str,
    userids: list[str] | None = None,
    atall: int = 0
) -> tuple[bool, str | None]:
    """
    更新企业微信自建应用交互卡片状态

    :param response_code: 模板卡片事件推送中的 response_code
    :param replace_text: 替换的文案
    :param userids: 指定更新卡片的用户列表
    :param atall: 是否更新所有收到卡片的人（0为否，1为是）
    :return:
    """
    if not settings.NOTIFY_WECOM_APP_CORPID or not settings.NOTIFY_WECOM_APP_CORPSECRET:
        return False, '企业微信自建应用 CORPID 或 CORPSECRET 未配置'
    if not settings.NOTIFY_WECOM_APP_AGENTID:
        return False, '企业微信自建应用 AGENTID 未配置'

    token_cache_key = 'fba:notify:wecom_app:access_token'
    try:
        access_token = await redis_client.get(token_cache_key)
    except Exception as e:
        log.warning(f'从 Redis 读取 wecom_app access_token 失败: {e}')
        access_token = None

    if not access_token:
        try:
            async with httpx.AsyncClient(timeout=settings.NOTIFY_TIMEOUT) as client:
                url = 'https://qyapi.weixin.qq.com/cgi-bin/gettoken'
                params = {
                    'corpid': settings.NOTIFY_WECOM_APP_CORPID,
                    'corpsecret': settings.NOTIFY_WECOM_APP_CORPSECRET,
                }
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                result = resp.json()
                if result.get('errcode') == 0:
                    access_token = result.get('access_token')
                    expires_in = result.get('expires_in', 7200)
                    try:
                        await redis_client.set(token_cache_key, access_token, ex=max(60, expires_in - 300))
                    except Exception as e:
                        log.warning(f'缓存 wecom_app access_token 到 Redis 失败: {e}')
                else:
                    error_msg = result.get('errmsg', '未知错误')
                    return False, f'获取 token 失败: {error_msg}'
        except Exception as e:
            return False, f'获取 token 异常: {e}'

    update_url = f'https://qyapi.weixin.qq.com/cgi-bin/message/update_template_card?access_token={access_token}'
    payload = {
        'agentid': settings.NOTIFY_WECOM_APP_AGENTID,
        'response_code': response_code,
        'button': {
            'replace_name': replace_text
        }
    }

    if userids:
        payload['userids'] = userids
    else:
        payload['atall'] = atall

    try:
        async with httpx.AsyncClient(timeout=settings.NOTIFY_TIMEOUT) as client:
            resp = await client.post(update_url, json=payload)
            resp.raise_for_status()
            result = resp.json()
            if result.get('errcode') == 0:
                log.info(f'更新企业微信交互卡片成功, response_code: {response_code}')
                return True, None

            errcode = result.get('errcode')
            if errcode in (40014, 42001):
                try:
                    await redis_client.delete(token_cache_key)
                except Exception as e:
                    log.warning(f'删除 wecom_app access_token 缓存失败: {e}')

            error = result.get('errmsg', '未知错误')
            log.error(f'更新企业微信交互卡片失败: {error}')
            return False, error
    except Exception as e:
        log.error(f'更新企业微信交互卡片异常: {e}')
        return False, str(e)


# 渠道名称 -> 发送函数映射
ChannelHandler = Callable[..., Coroutine[Any, Any, tuple[bool, str | None]]]

CHANNEL_HANDLERS: dict[str, ChannelHandler] = {
    'dingtalk': send_dingtalk,
    'smtp': send_smtp,
    'serverchan': send_serverchan,
    'telegram': send_telegram,
    'wecom': send_wecom,
    'wecom_app': send_wecom_app,
}

# 渠道名称 -> 启用配置属性名映射
CHANNEL_ENABLED_MAP: dict[str, str] = {
    'dingtalk': 'NOTIFY_DINGTALK_ENABLED',
    'smtp': 'NOTIFY_SMTP_ENABLED',
    'serverchan': 'NOTIFY_SERVERCHAN_ENABLED',
    'telegram': 'NOTIFY_TELEGRAM_ENABLED',
    'wecom': 'NOTIFY_WECOM_ENABLED',
    'wecom_app': 'NOTIFY_WECOM_APP_ENABLED',
}

