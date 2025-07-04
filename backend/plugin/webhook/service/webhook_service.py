#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import hashlib
import hmac
import json
import re
from datetime import datetime
from typing import Any, Sequence

from fastapi import Request
from sqlalchemy import Select

from backend.common.exception import errors
from backend.common.log import log
from backend.database.db import async_db_session
from backend.plugin.webhook.crud.crud_webhook import webhook_dao, webhook_config_dao
from backend.plugin.webhook.model import Webhook
from backend.plugin.webhook.model.webhook_config import WebhookConfig
from backend.plugin.webhook.schema.webhook import (
    CreateWebhookParam,
    DeleteWebhookParam,
    HeaderValidationRule,
    UpdateWebhookParam,
    WebhookListParam,
    WebhookReceiveParam,
    CreateWebhookConfigParam,
    UpdateWebhookConfigParam,
    WebhookConfigListParam,
    GetWebhookConfigDetail,
    DeleteWebhookConfigParam,
)


class WebhookService:
    """Webhook事件服务类"""

    @staticmethod
    async def get(*, pk: int) -> Webhook:
        """
        获取Webhook事件

        :param pk: Webhook事件 ID
        :return:
        """
        async with async_db_session() as db:
            webhook = await webhook_dao.get(db, pk)
            if not webhook:
                raise errors.NotFoundError(msg='Webhook事件不存在')
            return webhook

    @staticmethod
    async def get_select(params: WebhookListParam | None = None) -> Select:
        """
        获取Webhook事件查询对象

        :param params: 查询参数
        :return:
        """
        return await webhook_dao.get_list(params)

    @staticmethod
    async def get_all() -> Sequence[Webhook]:
        """获取所有Webhook事件"""
        async with async_db_session() as db:
            webhooks = await webhook_dao.get_all(db)
            return webhooks

    @staticmethod
    async def create(*, obj: CreateWebhookParam) -> Webhook:
        """
        创建Webhook事件

        :param obj: 创建Webhook事件参数
        :return:
        """
        async with async_db_session.begin() as db:
            webhook = await webhook_dao.create(db, obj)
            return webhook

    @staticmethod
    async def update(*, pk: int, obj: UpdateWebhookParam) -> int:
        """
        更新Webhook事件

        :param pk: Webhook事件 ID
        :param obj: 更新Webhook事件参数
        :return:
        """
        async with async_db_session.begin() as db:
            webhook = await webhook_dao.get(db, pk)
            if not webhook:
                raise errors.NotFoundError(msg='Webhook事件不存在')
            count = await webhook_dao.update(db, pk, obj)
            return count

    @staticmethod
    async def delete(*, obj: DeleteWebhookParam) -> int:
        """
        批量删除Webhook事件

        :param obj: Webhook事件 ID 列表
        :return:
        """
        async with async_db_session.begin() as db:
            count = await webhook_dao.delete(db, obj.pks)
            return count

    @staticmethod
    async def receive_webhook(
        *, 
        request: Request, 
        obj: WebhookReceiveParam,
        validation_rules: list[HeaderValidationRule] | None = None,
        secret_key: str | None = None
    ) -> dict[str, Any]:
        """
        接收Webhook事件

        :param request: FastAPI请求对象
        :param obj: 接收Webhook事件参数
        :param validation_rules: Header验证规则列表
        :param secret_key: 签名验证密钥
        :return:
        """
        try:
            # 获取请求头信息
            headers = dict(request.headers)
            
            # 获取请求来源信息
            origin = headers.get('origin')
            referer = headers.get('referer')
            user_agent = headers.get('user-agent', 'unknown')
            
            # 获取所有启用的配置
            async with async_db_session() as db:
                active_configs = await webhook_config_dao.get_active_configs(db)
            
            # 检查是否为本地测试请求
            is_local_test = (
                origin and origin.startswith('http://localhost') or
                referer and 'localhost' in referer or
                not origin and not referer  # 直接API调用
            )
            
            # 如果有配置且不是本地测试，则进行验证
            if active_configs and not is_local_test:
                valid_config = None
                
                # 检查是否有匹配的配置
                for config in active_configs:
                    # 检查事件类型是否允许
                    if config.allowed_event_types and obj.event_type:
                        if obj.event_type not in config.allowed_event_types:
                            continue
                    
                    # 检查请求头是否匹配
                    if config.required_headers:
                        headers_valid = True
                        for required_key, required_value in config.required_headers.items():
                            if headers.get(required_key.lower()) != required_value:
                                headers_valid = False
                                break
                        if not headers_valid:
                            continue
                    
                    # 检查来源域名（从origin或referer中提取）
                    request_domain = None
                    if origin:
                        request_domain = origin
                    elif referer:
                        request_domain = referer.split('/')[0:3]  # 获取协议+域名部分
                        request_domain = '/'.join(request_domain) if len(request_domain) >= 3 else referer
                    
                    # 检查来源域名是否在允许列表中
                    # 这里endpoint_url作为允许的发送方域名
                    if config.endpoint_url and request_domain:
                        config_domain = config.endpoint_url.split('/')[0:3]
                        config_domain = '/'.join(config_domain) if len(config_domain) >= 3 else config.endpoint_url
                        
                        # 对于接收webhook，检查请求是否来自配置的域名
                        if not request_domain.startswith(config_domain):
                            continue
                    
                    # 验证签名（如果配置了密钥且请求包含签名头）
                    if config.secret_key:
                        # 检查请求是否包含签名相关的头
                        has_signature = any(
                            key.lower() in ['x-signature', 'x-hub-signature', 'x-hub-signature-256', 'signature']
                            for key in headers.keys()
                        )
                        if has_signature:
                            try:
                                await WebhookService._validate_signature(request, config.secret_key)
                            except Exception:
                                continue
                        # 如果没有签名头，记录日志但不拒绝请求
                        else:
                            log.info(f'配置了密钥但请求未包含签名，跳过签名验证: {config.name}')
                    
                    # 找到有效配置
                    valid_config = config
                    break
                
                # 如果没有找到有效配置，拒绝请求
                if not valid_config:
                    raise errors.ForbiddenError(msg=f'请求未通过配置验证：来源域名({request_domain})、事件类型({obj.event_type})或请求头不匹配任何启用的配置')
            
            # 使用传入的验证规则（向后兼容）
            if validation_rules:
                await WebhookService._validate_headers(headers, validation_rules)
            
            # 使用传入的密钥验证（向后兼容）
            if secret_key:
                await WebhookService._validate_signature(request, secret_key)
            
            # 获取请求URL
            webhook_url = str(request.url)
            
            # 处理payload数据
            if isinstance(obj.data, dict):
                payload = json.dumps(obj.data, ensure_ascii=False)
            else:
                payload = str(obj.data)
            
            # 确定事件类型
            event_type = obj.event_type or headers.get('x-event-type', 'unknown')
            
            # 确定事件来源（截断到500字符以内）
            source = headers.get('x-source', user_agent)[:500]
            
            # 创建Webhook记录
            create_param = CreateWebhookParam(
                event_type=event_type,
                source=source,
                webhook_url=webhook_url,
                headers=headers,
                payload=payload
            )
            
            async with async_db_session.begin() as db:
                webhook = await webhook_dao.create(db, create_param)
                
                # 记录日志
                log.info(f'接收到Webhook事件: ID={webhook.id}, 类型={event_type}, 来源={source[:100]}...')
                
                # 这里可以添加业务逻辑处理
                await WebhookService._process_webhook_event(webhook, obj.data)
                
                return {
                    'webhook_id': webhook.id,
                    'event_type': event_type,
                    'source': source,
                    'status': 'received',
                    'message': 'Webhook事件已成功接收'
                }
                
        except Exception as e:
            log.error(f'处理Webhook事件失败: {str(e)}')
            raise errors.ForbiddenError(msg=f'处理Webhook事件失败: {str(e)}')

    @staticmethod
    async def _process_webhook_event(webhook: Webhook, data: Any) -> None:
        """
        处理Webhook事件的业务逻辑

        :param webhook: Webhook对象
        :param data: 事件数据
        :return:
        """
        try:
            # 根据事件类型处理不同的业务逻辑
            event_type = webhook.event_type.lower()
            
            if event_type == 'user.created':
                await WebhookService._handle_user_created(data)
            elif event_type == 'user.updated':
                await WebhookService._handle_user_updated(data)
            elif event_type == 'order.created':
                await WebhookService._handle_order_created(data)
            elif event_type == 'payment.completed':
                await WebhookService._handle_payment_completed(data)
            else:
                log.info(f'未知事件类型: {event_type}，跳过处理')
            
            # 更新处理状态为成功
            async with async_db_session.begin() as db:
                update_param = UpdateWebhookParam(
                    status=1,
                    error_message=None,
                    processed_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    retry_count=0
                )
                await webhook_dao.update(db, webhook.id, update_param)
                
        except Exception as e:
            log.error(f'处理Webhook事件业务逻辑失败: {str(e)}')
            # 更新处理状态为失败
            async with async_db_session.begin() as db:
                update_param = UpdateWebhookParam(
                    status=0,
                    error_message=str(e),
                    processed_at=None,
                    retry_count=webhook.retry_count + 1
                )
                await webhook_dao.update(db, webhook.id, update_param)

    @staticmethod
    async def _handle_user_created(data: Any) -> None:
        """处理用户创建事件"""
        log.info(f'处理用户创建事件: {data}')
        # 在这里添加用户创建的业务逻辑

    @staticmethod
    async def _handle_user_updated(data: Any) -> None:
        """处理用户更新事件"""
        log.info(f'处理用户更新事件: {data}')
        # 在这里添加用户更新的业务逻辑

    @staticmethod
    async def _handle_order_created(data: Any) -> None:
        """处理订单创建事件"""
        log.info(f'处理订单创建事件: {data}')
        # 在这里添加订单创建的业务逻辑

    @staticmethod
    async def _handle_payment_completed(data: Any) -> None:
        """处理支付完成事件"""
        log.info(f'处理支付完成事件: {data}')
        # 在这里添加支付完成的业务逻辑

    @staticmethod
    async def get_pending_webhooks(limit: int = 100) -> Sequence[Webhook]:
        """
        获取待处理的Webhook事件

        :param limit: 限制数量
        :return:
        """
        async with async_db_session() as db:
            return await webhook_dao.get_pending_webhooks(db, limit)

    @staticmethod
    async def retry_failed_webhooks() -> int:
        """
        重试失败的Webhook事件

        :return: 重试的事件数量
        """
        async with async_db_session() as db:
            failed_webhooks = await webhook_dao.get_failed_webhooks(db)
            retry_count = 0
            
            for webhook in failed_webhooks:
                try:
                    # 重新处理事件
                    data = json.loads(webhook.payload) if webhook.payload else {}
                    await WebhookService._process_webhook_event(webhook, data)
                    retry_count += 1
                except Exception as e:
                    log.error(f'重试Webhook事件失败: ID={webhook.id}, 错误={str(e)}')
            
            return retry_count

    @staticmethod
    async def _validate_headers(headers: dict[str, str], validation_rules: list[HeaderValidationRule]) -> None:
        """
        验证请求头

        :param headers: 请求头字典
        :param validation_rules: 验证规则列表
        :return:
        """
        for rule in validation_rules:
            header_value = headers.get(rule.header_name.lower())
            
            if rule.is_required and not header_value:
                raise errors.ForbiddenError(msg=f'缺少必需的请求头: {rule.header_name}')
            
            if header_value:
                if rule.validation_type == 'exact':
                    if header_value != rule.header_value:
                        raise errors.ForbiddenError(msg=f'请求头 {rule.header_name} 值不匹配')
                elif rule.validation_type == 'contains':
                    if rule.header_value not in header_value:
                        raise errors.ForbiddenError(msg=f'请求头 {rule.header_name} 不包含期望值')
                elif rule.validation_type == 'regex':
                    if not re.match(rule.header_value, header_value):
                        raise errors.ForbiddenError(msg=f'请求头 {rule.header_name} 不匹配正则表达式')

    @staticmethod
    async def _validate_signature(request: Request, secret_key: str) -> None:
        """
        验证Webhook签名

        :param request: FastAPI请求对象
        :param secret_key: 密钥
        :return:
        """
        # 获取签名头（支持多种常见的签名头格式）
        signature_headers = [
            'x-hub-signature-256',  # GitHub
            'x-signature-256',      # GitLab
            'x-webhook-signature',  # 自定义
            'signature'             # 通用
        ]
        
        received_signature = None
        for header in signature_headers:
            received_signature = request.headers.get(header)
            if received_signature:
                break
        
        if not received_signature:
            raise errors.ForbiddenError(msg='缺少签名头')
        
        # 获取请求体
        body = await request.body()
        
        # 计算期望的签名
        if received_signature.startswith('sha256='):
            # GitHub 风格的签名
            expected_signature = 'sha256=' + hmac.new(
                secret_key.encode('utf-8'),
                body,
                hashlib.sha256
            ).hexdigest()
        else:
            # 简单的HMAC签名
            expected_signature = hmac.new(
                secret_key.encode('utf-8'),
                body,
                hashlib.sha256
            ).hexdigest()
        
        # 验证签名
        if not hmac.compare_digest(received_signature, expected_signature):
            raise errors.ForbiddenError(msg='签名验证失败')

    # ==================== WebhookConfig 相关方法 ====================

    @staticmethod
    async def get_config(*, pk: int) -> GetWebhookConfigDetail:
        """
        获取WebhookConfig详情

        :param pk: 主键
        :return: WebhookConfig详情
        """
        async with async_db_session() as db:
            webhook_config = await webhook_config_dao.get(db, pk)
            if not webhook_config:
                raise errors.NotFoundError(msg='WebhookConfig不存在')
            return GetWebhookConfigDetail.model_validate(webhook_config)

    @staticmethod
    async def get_config_select(params: WebhookConfigListParam | None = None) -> Select:
        """
        获取WebhookConfig查询对象

        :param params: 查询参数
        :return:
        """
        return await webhook_config_dao.get_list(params)

    @staticmethod
    async def get_all_configs() -> Sequence[WebhookConfig]:
        """获取所有WebhookConfig"""
        async with async_db_session() as db:
            return await webhook_config_dao.get_all(db)

    @staticmethod
    async def create_config(*, obj: CreateWebhookConfigParam) -> WebhookConfig:
        """
        创建WebhookConfig

        :param obj: 创建参数
        :return:
        """
        async with async_db_session.begin() as db:
            # 检查配置名称是否已存在
            existing_config = await webhook_config_dao.get_by_name(db, obj.name)
            if existing_config:
                raise errors.ForbiddenError(msg='配置名称已存在')
            
            webhook_config = await webhook_config_dao.create(db, obj)
            return webhook_config

    @staticmethod
    async def update_config(*, pk: int, obj: UpdateWebhookConfigParam) -> int:
        """
        更新WebhookConfig

        :param pk: 主键
        :param obj: 更新参数
        :return:
        """
        async with async_db_session.begin() as db:
            webhook_config = await webhook_config_dao.get(db, pk)
            if not webhook_config:
                raise errors.NotFoundError(msg='WebhookConfig不存在')
            
            # 如果更新配置名称，检查是否已存在
            if obj.name and obj.name != webhook_config.name:
                existing_config = await webhook_config_dao.get_by_name(db, obj.name)
                if existing_config:
                    raise errors.ForbiddenError(msg='配置名称已存在')
            
            count = await webhook_config_dao.update(db, pk, obj)
            return count

    @staticmethod
    async def delete_config(*, obj: DeleteWebhookConfigParam) -> int:
        """
        删除WebhookConfig

        :param obj: 删除参数
        :return:
        """
        async with async_db_session.begin() as db:
            count = await webhook_config_dao.delete(db, obj.pks)
            return count

    @staticmethod
    async def update_config_status(*, pk: int, is_active: bool) -> int:
        """
        更新WebhookConfig状态

        :param pk: 主键
        :param is_active: 是否启用
        :return:
        """
        async with async_db_session.begin() as db:
            webhook_config = await webhook_config_dao.get(db, pk)
            if not webhook_config:
                raise errors.NotFoundError(msg='WebhookConfig不存在')
            
            count = await webhook_config_dao.update_status(db, pk, is_active)
            return count

    @staticmethod
    async def get_active_configs() -> Sequence[WebhookConfig]:
        """
        获取所有启用的WebhookConfig

        :return: 启用的WebhookConfig列表
        """
        async with async_db_session() as db:
            return await webhook_config_dao.get_active_configs(db)

    @staticmethod
    async def get_config_by_name(*, name: str) -> WebhookConfig | None:
        """
        根据配置名称获取WebhookConfig

        :param name: 配置名称
        :return: WebhookConfig对象或None
        """
        async with async_db_session() as db:
            return await webhook_config_dao.get_by_name(db, name)


webhook_service: WebhookService = WebhookService() 