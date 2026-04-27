#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from backend.common.log import log
from backend.core.conf import settings
from backend.plugin.sms.schema.sms import SendSmsResponse
from backend.plugin.sms.service.providers import SmsProvider


class SmsService:
    """短信服务（统一入口）"""

    _provider: SmsProvider | None = None

    @classmethod
    def _get_provider(cls) -> SmsProvider:
        """
        根据配置获取短信服务商实例

        :return:
        """
        if cls._provider is not None:
            return cls._provider

        provider_name = getattr(settings, 'SMS_PROVIDER', 'tencent')

        if provider_name == 'tencent':
            from backend.plugin.sms.service.providers.tencent_provider import TencentSmsProvider

            cls._provider = TencentSmsProvider()
        elif provider_name == 'smsbao':
            from backend.plugin.sms.service.providers.smsbao_provider import SmsBaoSmsProvider

            cls._provider = SmsBaoSmsProvider()
        else:
            raise ValueError(f'不支持的短信服务商: {provider_name}')

        log.info(f'短信服务商已初始化: {provider_name}')
        return cls._provider

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
        发送短信（委托给当前配置的服务商）

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
        provider = self._get_provider()
        return await provider.send_sms(
            phone_numbers=phone_numbers,
            template_id=template_id,
            template_params=template_params,
            sign_name=sign_name,
            sms_sdk_app_id=sms_sdk_app_id,
            extend_code=extend_code,
            session_context=session_context,
            sender_id=sender_id,
        )


# 创建服务实例
sms_service = SmsService()
