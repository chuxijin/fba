#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import uuid

import httpx

from backend.common.log import log
from backend.core.conf import settings
from backend.plugin.sms.schema.sms import SendSmsResponse, SendStatusItem
from backend.plugin.sms.service.providers import SmsProvider

# 短信宝错误码映射
SMSBAO_STATUS_MAP: dict[str, str] = {
    '0': '短信发送成功',
    '-1': '参数不全',
    '-2': '服务器空间不支持',
    '30': '密码错误',
    '40': '账号不存在',
    '41': '余额不足',
    '42': '账户已过期',
    '43': 'IP 地址限制',
    '50': '内容含有敏感词',
    '51': '手机号码不正确',
}


class SmsBaoSmsProvider(SmsProvider):
    """短信宝短信服务"""

    SMSBAO_API_URL: str = 'https://api.smsbao.com/sms'

    async def send_sms(
        self,
        phone_numbers: list[str],
        template_id: str,
        template_params: list[str],
        sign_name: str,
        sms_sdk_app_id: str,
        extend_code: str | None = None,
        session_context: str | None = None,
        sender_id: str | None = None,
    ) -> SendSmsResponse:
        """
        通过短信宝 HTTP API 发送短信

        :param phone_numbers: 手机号码列表
        :param template_id: 模板 ID（短信宝不使用，通过 content 传递完整内容）
        :param template_params: 模板参数列表（用于拼接短信内容）
        :param sign_name: 短信签名
        :param sms_sdk_app_id: 短信应用 ID（短信宝不使用）
        :param extend_code: 扩展码（短信宝不使用）
        :param session_context: 会话上下文（短信宝不使用）
        :param sender_id: 发送者 ID（短信宝不使用）
        :return:
        """
        username = settings.SMSBAO_USERNAME
        api_key = settings.SMSBAO_API_KEY

        # 拼接短信内容：【签名】+ 模板内容
        # 短信宝的内容格式为完整文本，验证码场景下参数即验证码
        content_body = ','.join(template_params) if template_params else ''
        content = f'【{sign_name}】您的验证码为{content_body}，请在5分钟内使用。'

        # 如果配置了短信模板，使用模板内容
        if hasattr(settings, 'SMSBAO_CONTENT_TEMPLATE') and settings.SMSBAO_CONTENT_TEMPLATE:
            content = settings.SMSBAO_CONTENT_TEMPLATE.format(
                sign_name=sign_name,
                params=content_body,
            )

        send_status_set: list[SendStatusItem] = []

        async with httpx.AsyncClient(timeout=10) as client:
            for phone in phone_numbers:
                try:
                    resp = await client.get(
                        self.SMSBAO_API_URL,
                        params={
                            'u': username,
                            'p': api_key,
                            'm': phone,
                            'c': content,
                        },
                    )
                    status_code = resp.text.strip()
                    is_success = status_code == '0'
                    message = SMSBAO_STATUS_MAP.get(status_code, f'未知错误: {status_code}')

                    send_status_set.append(SendStatusItem(
                        serial_no=uuid.uuid4().hex[:16],
                        phone_number=phone,
                        fee=1 if is_success else 0,
                        session_context=session_context,
                        code='Ok' if is_success else f'smsbao:{status_code}',
                        message=message,
                        iso_code='CN',
                    ))

                    if is_success:
                        log.info(f'短信宝发送成功: {phone}')
                    else:
                        log.warning(f'短信宝发送失败: {phone}, 错误: {message}')

                except Exception as e:
                    log.error(f'短信宝发送异常: {phone}, 错误: {e}')
                    send_status_set.append(SendStatusItem(
                        serial_no=uuid.uuid4().hex[:16],
                        phone_number=phone,
                        fee=0,
                        session_context=session_context,
                        code='smsbao:exception',
                        message=str(e),
                        iso_code='CN',
                    ))

        # 检查是否全部失败
        all_failed = all(s.code != 'Ok' for s in send_status_set)
        if all_failed and send_status_set:
            raise Exception(f'短信发送失败: {send_status_set[0].message}')

        return SendSmsResponse(
            send_status_set=send_status_set,
            request_id=uuid.uuid4().hex,
        )
