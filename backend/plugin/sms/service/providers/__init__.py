#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from abc import ABC, abstractmethod

from backend.plugin.sms.schema.sms import SendSmsResponse


class SmsProvider(ABC):
    """短信服务商抽象基类"""

    @abstractmethod
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
        发送短信

        :param phone_numbers: 手机号码列表
        :param template_id: 模板 ID
        :param template_params: 模板参数列表
        :param sign_name: 短信签名
        :param sms_sdk_app_id: 短信应用 ID
        :param extend_code: 扩展码
        :param session_context: 会话上下文
        :param sender_id: 国际/港澳台短信发送者 ID
        :return:
        """
        ...
