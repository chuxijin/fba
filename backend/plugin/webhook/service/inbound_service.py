#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
from typing import Any

from fastapi import Request

from backend.common.exception import errors
from backend.common.log import log
from backend.database.db import async_db_session
from backend.plugin.webhook.constant import EventLogStatus
from backend.plugin.webhook.crud.crud_event_log import crud_event_log
from backend.plugin.webhook.model.webhook_event_log import WebhookEventLog
from backend.plugin.webhook.schema.inbound import InboundReceiveParam, InboundReceiveResult
from backend.plugin.webhook.service import signature


class InboundService:
    """入站 Webhook 处理服务"""

    @staticmethod
    async def receive(
        *,
        request: Request,
        source: str,
        event_type: str | None = None,
        secret: str | None = None,
    ) -> InboundReceiveResult:
        """
        接收入站 Webhook (原始 HTTP 模式)

        流程: 验签 → 幂等检查 → 入库 → 异步分发

        :param request: FastAPI 请求对象
        :param source: 事件来源标识 (github/stripe/generic)
        :param event_type: 事件类型 (可选, 不传则自动推断)
        :param secret: 签名密钥 (可选, 不传则跳过签名验证)
        :return:
        """
        headers = dict(request.headers)
        body = await request.body()

        # ① 签名验证
        signature_valid = False
        if secret:
            InboundService._verify_signature(headers, body, secret)
            signature_valid = True

        # ② 提取事件 ID (用于幂等)
        event_id = InboundService._extract_event_id(headers, body)

        # ③ 幂等检查
        if event_id:
            async with async_db_session() as db:
                existing = await crud_event_log.get_by_event_id(db, event_id)
            if existing:
                log.info(f'重复事件, 跳过处理: {event_id}')
                return InboundReceiveResult(status='duplicate', event_id=event_id)

        # ④ 推断事件类型
        if not event_type:
            event_type = InboundService._infer_event_type(headers, body)

        # ⑤ 入库记录
        source_ip = request.client.host if request.client else None
        event_log = await InboundService._save_event_log(
            source=source,
            event_type=event_type,
            event_id=event_id,
            body=body,
            headers=headers,
            source_ip=source_ip,
            signature_valid=signature_valid,
        )

        # ⑥ 异步分发到 Handler
        try:
            payload_data = json.loads(body) if body else {}
        except (json.JSONDecodeError, UnicodeDecodeError):
            payload_data = {}

        await InboundService._dispatch_to_handlers(event_type, payload_data, event_id)

        return InboundReceiveResult(
            status='received',
            event_id=event_id,
            event_type=event_type,
            log_id=event_log.id,
        )

    @staticmethod
    async def receive_structured(
        *,
        obj: InboundReceiveParam,
        source: str = 'api',
    ) -> InboundReceiveResult:
        """
        接收入站 Webhook (结构化模式)

        :param obj: 结构化入站参数
        :param source: 事件来源
        :return:
        """
        # 幂等检查
        if obj.event_id:
            async with async_db_session() as db:
                existing = await crud_event_log.get_by_event_id(db, obj.event_id)
            if existing:
                log.info(f'重复事件, 跳过处理: {obj.event_id}')
                return InboundReceiveResult(status='duplicate', event_id=obj.event_id)

        # 入库
        payload_str = json.dumps(obj.data, ensure_ascii=False) if isinstance(obj.data, dict) else str(obj.data)
        payload_bytes = payload_str.encode('utf-8')

        event_log = await InboundService._save_event_log(
            source=source,
            event_type=obj.event_type,
            event_id=obj.event_id,
            body=payload_bytes,
            headers=None,
            source_ip=None,
            signature_valid=False,
        )

        # 异步分发
        await InboundService._dispatch_to_handlers(obj.event_type, obj.data, obj.event_id)

        return InboundReceiveResult(
            status='received',
            event_id=obj.event_id,
            event_type=obj.event_type,
            log_id=event_log.id,
        )

    @staticmethod
    def _verify_signature(headers: dict[str, str], body: bytes, secret: str) -> None:
        """
        验证 Standard Webhooks 签名

        :param headers: 请求头
        :param body: 请求体
        :param secret: 密钥
        :return:
        """
        msg_id = headers.get('webhook-id')
        ts = headers.get('webhook-timestamp')
        sig = headers.get('webhook-signature')

        if not all([msg_id, ts, sig]):
            raise errors.RequestError(msg='缺少 Standard Webhooks 必需头部')

        try:
            signature.verify(secret, msg_id, ts, sig, body)
        except ValueError as e:
            raise errors.ForbiddenError(msg=f'签名验证失败: {e}')

    @staticmethod
    def _extract_event_id(headers: dict[str, str], body: bytes) -> str | None:
        """
        从头部或 body 中提取事件 ID

        :param headers: 请求头
        :param body: 请求体
        :return:
        """
        # Standard Webhooks 的 webhook-id
        wh_id = headers.get('webhook-id')
        if wh_id:
            return wh_id

        # 尝试从 JSON body 中提取
        try:
            data = json.loads(body)
            if isinstance(data, dict):
                for key in ('id', 'event_id', 'eventId'):
                    if key in data:
                        return str(data[key])
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass

        return None

    @staticmethod
    def _infer_event_type(headers: dict[str, str], body: bytes) -> str:
        """
        自动推断事件类型

        :param headers: 请求头
        :param body: 请求体
        :return:
        """
        # 从头部推断
        for key in ('x-event-type', 'x-github-event', 'x-gitlab-event'):
            if key in headers:
                return headers[key]

        # 从 User-Agent 推断
        user_agent = headers.get('user-agent', '').lower()
        for source in ('github', 'gitlab', 'stripe', 'wechat'):
            if source in user_agent:
                return f'{source}.webhook'

        # 从 body 推断
        try:
            data = json.loads(body)
            if isinstance(data, dict):
                for key in ('event_type', 'event', 'type', 'action'):
                    if key in data:
                        return str(data[key])
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass

        return 'generic.unknown'

    @staticmethod
    async def _save_event_log(
        *,
        source: str,
        event_type: str,
        event_id: str | None,
        body: bytes,
        headers: dict[str, str] | None,
        source_ip: str | None,
        signature_valid: bool,
    ) -> WebhookEventLog:
        """
        保存入站事件日志

        :return:
        """
        # 脱敏处理
        safe_headers = None
        if headers:
            safe_headers = {
                k: ('***' if k in ('authorization', 'x-api-key', 'cookie') else v) for k, v in headers.items()
            }

        uid = signature.generate_id('log_')
        payload_str = body.decode('utf-8') if body else '{}'

        async with async_db_session.begin() as db:
            from backend.plugin.webhook.model.webhook_event_log import WebhookEventLog as EventLogModel

            event_log = EventLogModel(
                uid=uid,
                source=source[:100],
                event_type=event_type[:200],
                event_id=event_id,
                payload=payload_str,
                headers=safe_headers,
                signature_valid=signature_valid,
                status=EventLogStatus.RECEIVED,
                source_ip=source_ip,
            )
            db.add(event_log)
            await db.flush()
            await db.refresh(event_log)

        return event_log

    @staticmethod
    async def _dispatch_to_handlers(
        event_type: str,
        data: dict[str, Any] | None,
        event_id: str | None,
    ) -> None:
        """
        异步分发事件到 Handler

        :param event_type: 事件类型
        :param data: 事件数据
        :param event_id: 事件 ID
        :return:
        """
        try:
            from backend.plugin.webhook.handler import registry

            executed = await registry.dispatch(event_type, data, event_id)
            if executed:
                log.info(f'事件 {event_type} 已分发到处理器: {executed}')
            else:
                log.debug(f'事件 {event_type} 无匹配的处理器')
        except Exception as e:
            log.error(f'事件分发失败: {event_type} error={e}')


inbound_service: InboundService = InboundService()
