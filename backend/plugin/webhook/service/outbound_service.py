#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime, timezone

from backend.common.log import log
from backend.database.db import async_db_session
from backend.plugin.webhook.constant import DELIVERY_ID_PREFIX, DeliveryStatus
from backend.plugin.webhook.crud.crud_delivery import crud_delivery
from backend.plugin.webhook.crud.crud_endpoint import crud_endpoint
from backend.plugin.webhook.model.webhook_delivery import WebhookDelivery
from backend.plugin.webhook.schema.cloud_event import CloudEvent
from backend.plugin.webhook.service import signature


class OutboundService:
    """出站 Webhook 推送服务"""

    @staticmethod
    async def dispatch(
        event_type: str,
        data: dict | None = None,
        subject: str | None = None,
        source: str = '/services/fba',
    ) -> int:
        """
        分发事件到所有匹配的 Endpoint

        :param event_type: 事件类型
        :param data: 事件数据
        :param subject: 关联资源标识
        :param source: 事件来源
        :return: 创建的投递记录数
        """
        # ① 查找订阅了该事件类型的所有活跃 Endpoint
        endpoints = await OutboundService._find_matching_endpoints(event_type)
        if not endpoints:
            log.debug(f'无匹配的 Endpoint, 跳过分发: {event_type}')
            return 0

        # ② 构建 CloudEvents 信封
        event = CloudEvent(
            id=signature.generate_id(),
            type=event_type,
            source=source,
            data=data,
            subject=subject,
        )
        payload = event.model_dump_json()

        # ③ 为每个 Endpoint 创建投递记录
        delivery_count = 0
        now_ts = int(datetime.now(timezone.utc).timestamp())

        async with async_db_session.begin() as db:
            for endpoint in endpoints:
                sig = signature.sign(endpoint.secret, event.id, now_ts, payload.encode())
                uid = signature.generate_id(DELIVERY_ID_PREFIX)

                delivery = WebhookDelivery(
                    uid=uid,
                    endpoint_id=endpoint.id,
                    event_id=event.id,
                    event_type=event_type,
                    payload=payload,
                    signature=sig,
                    timestamp=now_ts,
                    status=DeliveryStatus.PENDING,
                    attempt_count=0,
                )
                db.add(delivery)
                delivery_count += 1

            await db.flush()

        log.info(f'事件 {event_type} 已创建 {delivery_count} 条投递记录')
        return delivery_count

    @staticmethod
    async def _find_matching_endpoints(event_type: str) -> list:
        """
        查找匹配事件类型的活跃 Endpoint

        :param event_type: 事件类型
        :return:
        """
        async with async_db_session() as db:
            active_endpoints = await crud_endpoint.get_active_endpoints(db)

        matched = []
        for ep in active_endpoints:
            if not ep.event_types:
                continue
            for pattern in ep.event_types:
                if OutboundService._match_event_type(pattern, event_type):
                    matched.append(ep)
                    break

        return matched

    @staticmethod
    def _match_event_type(pattern: str, event_type: str) -> bool:
        """
        事件类型通配符匹配

        :param pattern: 订阅模式 (如 "com.fba.order.*")
        :param event_type: 实际事件类型
        :return:
        """
        if pattern == event_type:
            return True
        if pattern.endswith('.*'):
            prefix = pattern[:-2]
            return event_type.startswith(prefix + '.')
        if pattern == '*':
            return True
        return False


outbound_service: OutboundService = OutboundService()
