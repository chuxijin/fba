#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from tencentcloud.common import credential
from tencentcloud.common.exception.tencent_cloud_sdk_exception import TencentCloudSDKException
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.sms.v20210111 import sms_client, models

from backend.common.log import log
from backend.core.conf import settings
from backend.plugin.sms.schema.sms import SendSmsResponse, SendStatusItem
from backend.plugin.sms.service.providers import SmsProvider


class TencentSmsProvider(SmsProvider):
    """腾讯云短信服务"""

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
        通过腾讯云 SDK 发送短信

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
        try:
            cred = credential.Credential(settings.TENCENTCLOUD_SECRET_ID, settings.TENCENTCLOUD_SECRET_KEY)

            http_profile = HttpProfile()
            http_profile.endpoint = 'sms.tencentcloudapi.com'

            client_profile = ClientProfile()
            client_profile.httpProfile = http_profile

            client = sms_client.SmsClient(cred, 'ap-guangzhou', client_profile)

            req = models.SendSmsRequest()
            req.PhoneNumberSet = phone_numbers
            req.SmsSdkAppId = sms_sdk_app_id
            req.SignName = sign_name
            req.TemplateId = template_id
            req.TemplateParamSet = template_params

            if extend_code:
                req.ExtendCode = extend_code
            if session_context:
                req.SessionContext = session_context
            if sender_id:
                req.SenderId = sender_id

            resp = client.SendSms(req)

            send_status_set = [
                SendStatusItem(
                    serial_no=status.SerialNo,
                    phone_number=status.PhoneNumber,
                    fee=status.Fee,
                    session_context=status.SessionContext,
                    code=status.Code,
                    message=status.Message,
                    iso_code=status.IsoCode,
                )
                for status in resp.SendStatusSet
            ]

            log.info(f'腾讯云短信发送成功: {send_status_set}')
            return SendSmsResponse(send_status_set=send_status_set, request_id=resp.RequestId)

        except TencentCloudSDKException as err:
            log.error(f'腾讯云短信发送失败: {err}')
            raise Exception(f'短信发送失败: {err}')
        except Exception as e:
            log.error(f'短信发送异常: {e}')
            raise Exception(f'短信发送异常: {e}')
