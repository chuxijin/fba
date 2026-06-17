#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import timedelta

import httpx

from backend.common.log import log
from backend.database.db import async_db_session
from backend.plugin.webhook.constant import (
    RESPONSE_BODY_MAX_LENGTH,
    RETRY_INTERVALS,
    DeliveryStatus,
)
from backend.plugin.webhook.crud.crud_delivery import crud_delivery
from backend.plugin.webhook.crud.crud_endpoint import crud_endpoint
from backend.plugin.webhook.model.webhook_delivery import WebhookDelivery
from backend.plugin.webhook.model.webhook_endpoint import WebhookEndpoint
from backend.utils.timezone import timezone


class DeliveryService:
    """Webhook 投递引擎"""

    @staticmethod
    async def process_pending(batch_size: int = 50) -> int:
        """
        处理待投递的记录

        :param batch_size: 每批处理数量
        :return: 处理数量
        """
        async with async_db_session() as db:
            pending = await crud_delivery.get_pending(db, batch_size)
            retryable = await crud_delivery.get_retryable(db, batch_size)

        deliveries = list(pending) + list(retryable)
        if not deliveries:
            return 0

        processed = 0
        for delivery in deliveries:
            success = await DeliveryService._deliver(delivery)
            if success:
                processed += 1

        return processed

    @staticmethod
    async def _deliver(delivery: WebhookDelivery) -> bool:
        """
        执行单次投递

        :param delivery: 投递记录
        :return: 是否成功
        """
        # 获取 Endpoint
        async with async_db_session() as db:
            endpoint = await crud_endpoint.get(db, delivery.endpoint_id)

        if not endpoint or not endpoint.is_active:
            log.warning(f'Endpoint 不可用, 跳过投递: {delivery.uid}')
            return False

        # 构建请求头
        headers = {
            'content-type': 'application/json',
            'user-agent': 'FBA-Webhook/1.0',
        }

        if delivery.event_id and delivery.timestamp and delivery.signature:
            headers['webhook-id'] = delivery.event_id
            headers['webhook-timestamp'] = str(delivery.timestamp)
            headers['webhook-signature'] = delivery.signature

        if endpoint.headers:
            headers.update(endpoint.headers)

        try:
            async with httpx.AsyncClient(timeout=endpoint.timeout_seconds) as client:
                response = await client.post(
                    endpoint.url,
                    content=delivery.payload.encode('utf-8'),
                    headers=headers,
                )

            if 200 <= response.status_code < 300:
                await DeliveryService._mark_success(delivery, endpoint, response)
                return True

            await DeliveryService._mark_retry(delivery, endpoint, response.status_code, response.text)
            return False

        except Exception as e:
            log.error(f'投递异常: {delivery.uid} error={e}')
            await DeliveryService._mark_retry(delivery, endpoint, error=str(e))
            return False

    @staticmethod
    async def _mark_success(
        delivery: WebhookDelivery,
        endpoint: WebhookEndpoint,
        response: httpx.Response,
    ) -> None:
        """标记投递成功"""
        async with async_db_session.begin() as db:
            from sqlalchemy import update

            from backend.plugin.webhook.model.webhook_delivery import WebhookDelivery as DeliveryModel

            stmt = (
                update(DeliveryModel)
                .where(DeliveryModel.id == delivery.id)
                .values(
                    status=DeliveryStatus.SUCCESS,
                    response_code=response.status_code,
                    response_body=response.text[:RESPONSE_BODY_MAX_LENGTH],
                    attempt_count=delivery.attempt_count + 1,
                    completed_at=timezone.now(),
                )
            )
            await db.execute(stmt)

            # 重置 Endpoint 失败计数
            ep_stmt = (
                update(WebhookEndpoint)
                .where(WebhookEndpoint.id == endpoint.id)
                .values(failure_count=0, last_success_at=timezone.now())
            )
            await db.execute(ep_stmt)

        log.info(f'投递成功: {delivery.uid} → {endpoint.url}')

    @staticmethod
    async def _mark_retry(
        delivery: WebhookDelivery,
        endpoint: WebhookEndpoint,
        status_code: int | None = None,
        response_body: str | None = None,
        error: str | None = None,
    ) -> None:
        """标记重试, 计算下次重试时间"""
        attempt = delivery.attempt_count + 1

        if attempt >= endpoint.max_retries:
            await DeliveryService._mark_failed(delivery, endpoint, status_code, response_body, error)
            return

        interval = RETRY_INTERVALS[min(attempt - 1, len(RETRY_INTERVALS) - 1)]
        next_retry = timezone.now() + timedelta(seconds=interval)

        async with async_db_session.begin() as db:
            from sqlalchemy import update

            from backend.plugin.webhook.model.webhook_delivery import WebhookDelivery as DeliveryModel

            stmt = (
                update(DeliveryModel)
                .where(DeliveryModel.id == delivery.id)
                .values(
                    status=DeliveryStatus.RETRYING,
                    response_code=status_code,
                    response_body=(response_body or error or '')[:RESPONSE_BODY_MAX_LENGTH],
                    attempt_count=attempt,
                    next_retry_at=next_retry,
                )
            )
            await db.execute(stmt)

        log.info(f'投递重试: {delivery.uid} attempt={attempt} next_retry={next_retry}')

    @staticmethod
    async def _mark_failed(
        delivery: WebhookDelivery,
        endpoint: WebhookEndpoint,
        status_code: int | None = None,
        response_body: str | None = None,
        error: str | None = None,
    ) -> None:
        """标记永久失败"""
        async with async_db_session.begin() as db:
            from sqlalchemy import update

            from backend.plugin.webhook.model.webhook_delivery import WebhookDelivery as DeliveryModel

            stmt = (
                update(DeliveryModel)
                .where(DeliveryModel.id == delivery.id)
                .values(
                    status=DeliveryStatus.FAILED,
                    response_code=status_code,
                    response_body=(response_body or error or '')[:RESPONSE_BODY_MAX_LENGTH],
                    attempt_count=delivery.attempt_count + 1,
                    completed_at=timezone.now(),
                )
            )
            await db.execute(stmt)

            # 增加 Endpoint 失败计数
            new_failure = endpoint.failure_count + 1
            ep_stmt = (
                update(WebhookEndpoint)
                .where(WebhookEndpoint.id == endpoint.id)
                .values(failure_count=new_failure, last_failure_at=timezone.now())
            )
            await db.execute(ep_stmt)

        log.warning(f'投递永久失败: {delivery.uid} endpoint={endpoint.name} failure_count={new_failure}')

        # 连续失败超过阈值, 自动禁用 Endpoint
        if new_failure >= 10:
            await DeliveryService._auto_disable_endpoint(endpoint)

    @staticmethod
    async def _auto_disable_endpoint(endpoint: WebhookEndpoint) -> None:
        """自动禁用连续失败的 Endpoint"""
        async with async_db_session.begin() as db:
            from sqlalchemy import update

            stmt = update(WebhookEndpoint).where(WebhookEndpoint.id == endpoint.id).values(is_active=False)
            await db.execute(stmt)

        log.error(f'Endpoint 已自动禁用 (连续失败 {endpoint.failure_count} 次): {endpoint.name} ({endpoint.url})')


delivery_service: DeliveryService = DeliveryService()
