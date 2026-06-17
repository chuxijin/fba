#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import xml.etree.ElementTree as ET
from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse

from backend.common.log import log
from backend.common.response.response_schema import ResponseModel, response_base
from backend.core.conf import settings
from backend.plugin.notify.schema.notify import CreateNotifyParam
from backend.plugin.notify.service.notify_service import notify_service
from backend.plugin.notify.utils.wecom_crypt import WecomMsgCrypt
from backend.plugin.notify.utils.channels import update_wecom_app_template_card

router = APIRouter()


@router.post('/send', summary='发送通知')
async def send_notification(obj: CreateNotifyParam) -> ResponseModel:
    """
    发送多渠道通知（按优先级降级）

    :param obj: 发送通知参数
    :return:
    """
    result = await notify_service.send(
        title=obj.title,
        content=obj.content,
        channels=obj.channels,
        options=obj.options,
        source='api',
    )
    return response_base.success(data=result.model_dump())


@router.get('/wecom/callback', summary='企业微信应用回调验证')
async def wecom_callback_verify(msg_signature: str, timestamp: str, nonce: str, echostr: str) -> PlainTextResponse:
    """
    企业微信自建应用回调验证接口 (GET)

    :param msg_signature: 签名
    :param timestamp: 时间戳
    :param nonce: 随机数
    :param echostr: 加密的随机字符串
    :return:
    """
    if not settings.NOTIFY_WECOM_APP_TOKEN or not settings.NOTIFY_WECOM_APP_ENCODING_AES_KEY:
        log.error('企业微信回调配置缺失')
        return PlainTextResponse('配置错误', status_code=500)

    crypt = WecomMsgCrypt(
        token=settings.NOTIFY_WECOM_APP_TOKEN,
        encoding_aes_key=settings.NOTIFY_WECOM_APP_ENCODING_AES_KEY,
        receive_id=settings.NOTIFY_WECOM_APP_CORPID,
    )

    if not crypt.verify_signature(msg_signature, timestamp, nonce, echostr):
        log.warning('企业微信签名验证失败')
        return PlainTextResponse('签名校验失败', status_code=400)

    try:
        decrypted_echostr = crypt.decrypt(echostr)
        return PlainTextResponse(content=decrypted_echostr)
    except Exception as e:
        log.error(f'企业微信验证 echostr 解密失败: {e}')
        return PlainTextResponse('解密失败', status_code=400)


@router.post('/wecom/callback', summary='企业微信接收消息与事件')
async def wecom_callback_event(request: Request, msg_signature: str, timestamp: str, nonce: str) -> PlainTextResponse:
    """
    接收企业微信自建应用的消息与事件回调 (POST)

    :param request: 请求对象
    :param msg_signature: 签名
    :param timestamp: 时间戳
    :param nonce: 随机数
    :return:
    """
    if not settings.NOTIFY_WECOM_APP_TOKEN or not settings.NOTIFY_WECOM_APP_ENCODING_AES_KEY:
        log.error('企业微信回调配置缺失')
        return PlainTextResponse('配置错误', status_code=500)

    body = await request.body()
    if not body:
        return PlainTextResponse('empty body', status_code=400)

    try:
        root = ET.fromstring(body)
        encrypt_node = root.find('Encrypt')
        if encrypt_node is None or not encrypt_node.text:
            return PlainTextResponse('encrypt node not found', status_code=400)
        encrypt = encrypt_node.text
    except Exception as e:
        log.error(f'解析微信 XML 发生异常: {e}')
        return PlainTextResponse('bad xml', status_code=400)

    crypt = WecomMsgCrypt(
        token=settings.NOTIFY_WECOM_APP_TOKEN,
        encoding_aes_key=settings.NOTIFY_WECOM_APP_ENCODING_AES_KEY,
        receive_id=settings.NOTIFY_WECOM_APP_CORPID,
    )

    if not crypt.verify_signature(msg_signature, timestamp, nonce, encrypt):
        log.warning('企业微信签名验证失败')
        return PlainTextResponse('签名校验失败', status_code=400)

    try:
        xml_content = crypt.decrypt(encrypt)
        log.info(f'解密后的企业微信消息明文: {xml_content}')

        event_root = ET.fromstring(xml_content.encode('utf-8'))
        msg_type = event_root.findtext('MsgType')
        event = event_root.findtext('Event')

        if msg_type == 'event' and event == 'template_card_event':
            event_key = event_root.findtext('EventKey')
            response_code = event_root.findtext('ResponseCode')
            from_username = event_root.findtext('FromUserName')

            log.info(f'用户 {from_username} 点击了微信卡片按钮: {event_key}, response_code: {response_code}')

            replace_text = '操作已受理'
            if event_key in ('accept', 'button_key_1'):
                replace_text = '已接受处理'
            elif event_key in ('reject', 'button_key_2'):
                replace_text = '已拒绝处理'

            import asyncio

            asyncio.create_task(
                update_wecom_app_template_card(
                    response_code=response_code, replace_text=replace_text, userids=[from_username]
                )
            )

        return PlainTextResponse('success')
    except Exception as e:
        log.error(f'处理微信事件发生异常: {e}')
        return PlainTextResponse('success')
