#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import Select

from backend.common.exception import errors
from backend.database.db import async_db_session
from backend.plugin.webhook.constant import ENDPOINT_ID_PREFIX
from backend.plugin.webhook.crud.crud_endpoint import crud_endpoint
from backend.plugin.webhook.model.webhook_endpoint import WebhookEndpoint
from backend.plugin.webhook.schema.endpoint import (
    CreateEndpointParam,
    EndpointListParam,
    RotateSecretResult,
    TestEndpointResult,
    UpdateEndpointParam,
)
from backend.plugin.webhook.service import signature


class EndpointService:
    """出站端点管理服务"""

    @staticmethod
    async def get(*, pk: int) -> WebhookEndpoint:
        """
        获取端点详情

        :param pk: 主键 ID
        :return:
        """
        async with async_db_session() as db:
            endpoint = await crud_endpoint.get(db, pk)
            if not endpoint:
                raise errors.NotFoundError(msg='端点不存在')
            return endpoint

    @staticmethod
    async def get_select(params: EndpointListParam | None = None) -> Select:
        """
        获取端点查询对象

        :param params: 查询参数
        :return:
        """
        return await crud_endpoint.get_list(params)

    @staticmethod
    async def create(*, obj: CreateEndpointParam) -> WebhookEndpoint:
        """
        创建端点

        :param obj: 创建参数
        :return:
        """
        uid = signature.generate_id(ENDPOINT_ID_PREFIX)
        secret = signature.generate_secret()

        async with async_db_session.begin() as db:
            endpoint = WebhookEndpoint(
                uid=uid,
                name=obj.name,
                url=obj.url,
                description=obj.description,
                secret=secret,
                event_types=obj.event_types,
                headers=obj.headers,
                max_retries=obj.max_retries,
                timeout_seconds=obj.timeout_seconds,
            )
            db.add(endpoint)
            await db.flush()
            await db.refresh(endpoint)
            return endpoint

    @staticmethod
    async def update(*, pk: int, obj: UpdateEndpointParam) -> int:
        """
        更新端点

        :param pk: 主键 ID
        :param obj: 更新参数
        :return:
        """
        async with async_db_session.begin() as db:
            endpoint = await crud_endpoint.get(db, pk)
            if not endpoint:
                raise errors.NotFoundError(msg='端点不存在')
            count = await crud_endpoint.update(db, pk, obj)
            return count

    @staticmethod
    async def delete(*, pks: list[int]) -> int:
        """
        批量删除端点

        :param pks: 主键列表
        :return:
        """
        async with async_db_session.begin() as db:
            count = await crud_endpoint.delete(db, pks)
            return count

    @staticmethod
    async def rotate_secret(*, pk: int) -> RotateSecretResult:
        """
        轮换端点密钥

        :param pk: 主键 ID
        :return:
        """
        async with async_db_session.begin() as db:
            endpoint = await crud_endpoint.get(db, pk)
            if not endpoint:
                raise errors.NotFoundError(msg='端点不存在')

            new_secret = signature.generate_secret()
            await crud_endpoint.update_secret(db, pk, new_secret)

            return RotateSecretResult(
                uid=endpoint.uid,
                new_secret=new_secret,
                message='密钥已轮换, 请妥善保存新密钥, 旧密钥将立即失效',
            )

    @staticmethod
    async def test_push(*, pk: int) -> TestEndpointResult:
        """
        测试推送到端点

        :param pk: 主键 ID
        :return:
        """
        import httpx

        async with async_db_session() as db:
            endpoint = await crud_endpoint.get(db, pk)
            if not endpoint:
                raise errors.NotFoundError(msg='端点不存在')

        # 构建测试 payload
        test_payload = '{"specversion":"1.0","id":"test_msg","type":"test.ping","source":"/services/fba","data":{"message":"hello"}}'
        timestamp = int(__import__('time').time())
        sig = signature.sign(endpoint.secret, 'test_msg', timestamp, test_payload.encode())

        headers = {
            'content-type': 'application/json',
            'webhook-id': 'test_msg',
            'webhook-timestamp': str(timestamp),
            'webhook-signature': sig,
            'user-agent': 'FBA-Webhook/1.0 (test)',
        }

        if endpoint.headers:
            headers.update(endpoint.headers)

        try:
            async with httpx.AsyncClient(timeout=endpoint.timeout_seconds) as client:
                response = await client.post(endpoint.url, content=test_payload, headers=headers)

            success = 200 <= response.status_code < 300
            return TestEndpointResult(
                success=success,
                status_code=response.status_code,
                response_body=response.text[:2048],
                message='测试推送成功' if success else f'测试推送失败 (HTTP {response.status_code})',
            )
        except Exception as e:
            return TestEndpointResult(
                success=False,
                status_code=None,
                response_body=None,
                message=f'测试推送异常: {e}',
            )


endpoint_service: EndpointService = EndpointService()
