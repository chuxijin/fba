#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import base64
import hashlib
import hmac
import json
import re
import time
import uuid
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
                            key.lower() in ['x-signature', 'x-hub-signature', 'x-hub-signature-256', 'signature', 'webhook-signature']
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
                    raise errors.ForbiddenError(msg='请求不匹配任何有效的webhook配置')
            
            # 如果提供了验证规则，执行验证
            if validation_rules:
                await WebhookService._validate_headers(headers, validation_rules)
            
            # 如果提供了密钥，验证签名
            if secret_key:
                await WebhookService._validate_signature(request, secret_key)
            
            # 处理payload数据
            if isinstance(obj.data, dict):
                payload_str = json.dumps(obj.data, ensure_ascii=False)
                payload_data = obj.data
            else:
                payload_str = str(obj.data)
                payload_data = obj.data
            
            # 创建webhook事件记录
            webhook_data = {
                'event_type': obj.event_type,
                'source': user_agent[:500] if user_agent else 'unknown',  # 限制长度
                'webhook_url': str(request.url),
                'headers': headers,
                'payload': payload_str,
                'status': 1,  # 使用整数状态
                'processed_at': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
                'retry_count': 0,
                'error_message': None,
            }
            
            # 创建webhook记录
            async with async_db_session.begin() as db:
                webhook = await webhook_dao.create(db, CreateWebhookParam(**webhook_data))
            
            # 处理webhook事件
            await WebhookService._process_webhook_event(webhook, payload_data)
            
            return {
                'success': True,
                'message': 'Webhook事件处理成功',
                'webhook_id': webhook.id,
                'event_type': obj.event_type,
                'processed_at': webhook.processed_at if webhook.processed_at else None
            }
            
        except Exception as e:
            # 记录失败的webhook事件
            error_message = str(e)[:1000]  # 限制错误信息长度
            
            # 处理payload数据
            if isinstance(obj.data, dict):
                payload_str = json.dumps(obj.data, ensure_ascii=False)
            else:
                payload_str = str(obj.data)
            
            webhook_data = {
                'event_type': obj.event_type,
                'source': user_agent[:500] if user_agent else 'unknown',
                'webhook_url': str(request.url),
                'headers': dict(request.headers),
                'payload': payload_str,
                'status': 0,  # 失败状态
                'error_message': error_message,
                'retry_count': 0,
                'processed_at': None,
            }
            
            try:
                async with async_db_session.begin() as db:
                    await webhook_dao.create(db, CreateWebhookParam(**webhook_data))
            except Exception as db_error:
                log.error(f'保存失败的webhook事件时出错: {db_error}')
            
            # 重新抛出原始异常
            raise e

    @staticmethod
    async def _process_webhook_event(webhook: Webhook, data: Any) -> None:
        """
        处理Webhook事件

        :param webhook: Webhook对象
        :param data: 事件数据
        :return:
        """
        try:
            # 根据事件类型处理不同的业务逻辑
            if webhook.event_type == 'user.created':
                await WebhookService._handle_user_created(data)
            elif webhook.event_type == 'user.updated':
                await WebhookService._handle_user_updated(data)
            elif webhook.event_type == 'order.created':
                await WebhookService._handle_order_created(data)
            elif webhook.event_type == 'payment.completed':
                await WebhookService._handle_payment_completed(data)
            else:
                log.info(f'未知的事件类型: {webhook.event_type}')
                
        except Exception as e:
            log.error(f'处理Webhook事件时出错: {e}')
            # 更新webhook状态为失败
            async with async_db_session.begin() as db:
                await webhook_dao.update(db, webhook.id, UpdateWebhookParam(
                    status=0,  # 失败状态
                    error_message=str(e)[:1000],
                    processed_at=None,
                    retry_count=webhook.retry_count
                ))

    @staticmethod
    async def _handle_user_created(data: Any) -> None:
        """处理用户创建事件"""
        log.info(f'处理用户创建事件: {data}')
        # 这里可以添加具体的业务逻辑

    @staticmethod
    async def _handle_user_updated(data: Any) -> None:
        """处理用户更新事件"""
        log.info(f'处理用户更新事件: {data}')
        # 这里可以添加具体的业务逻辑

    @staticmethod
    async def _handle_order_created(data: Any) -> None:
        """处理订单创建事件"""
        log.info(f'处理订单创建事件: {data}')
        # 这里可以添加具体的业务逻辑

    @staticmethod
    async def _handle_payment_completed(data: Any) -> None:
        """处理支付完成事件"""
        log.info(f'处理支付完成事件: {data}')
        # 这里可以添加具体的业务逻辑

    @staticmethod
    async def get_pending_webhooks(limit: int = 100) -> Sequence[Webhook]:
        """
        获取待处理的Webhook事件

        :param limit: 限制数量
        :return:
        """
        async with async_db_session() as db:
            webhooks = await webhook_dao.get_pending_webhooks(db, limit)
            return webhooks

    @staticmethod
    async def retry_failed_webhooks() -> int:
        """
        重试失败的Webhook事件

        :return: 重试的数量
        """
        async with async_db_session() as db:
            failed_webhooks = await webhook_dao.get_failed_webhooks(db)
            retry_count = 0
            
            for webhook in failed_webhooks:
                if webhook.retry_count < 3:  # 最多重试3次
                    try:
                        await WebhookService._process_webhook_event(webhook, webhook.payload)
                        # 更新状态为成功
                        await webhook_dao.update(db, webhook.id, UpdateWebhookParam(
                            status=1,  # 成功状态
                            processed_at=datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
                            retry_count=webhook.retry_count + 1,
                            error_message=None
                        ))
                        retry_count += 1
                    except Exception as e:
                        # 更新重试次数和错误信息
                        await webhook_dao.update(db, webhook.id, UpdateWebhookParam(
                            status=0,  # 失败状态
                            retry_count=webhook.retry_count + 1,
                            error_message=str(e)[:1000],
                            processed_at=None
                        ))
            
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
        验证Webhook签名 - 支持Standard Webhooks和传统格式

        :param request: FastAPI请求对象
        :param secret_key: 密钥
        :return:
        """
        # 获取请求体
        body = await request.body()
        
        # 优先检查Standard Webhooks格式
        webhook_signature = request.headers.get('webhook-signature')
        webhook_id = request.headers.get('webhook-id')
        webhook_timestamp = request.headers.get('webhook-timestamp')
        
        if webhook_signature and webhook_id and webhook_timestamp:
            # Standard Webhooks格式验证
            await WebhookService._validate_standard_webhook_signature(
                webhook_signature, webhook_id, webhook_timestamp, body, secret_key
            )
            return
        
        # 回退到传统格式验证
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

    @staticmethod
    async def _validate_standard_webhook_signature(
        webhook_signature: str, 
        webhook_id: str, 
        webhook_timestamp: str, 
        body: bytes, 
        secret_key: str
    ) -> None:
        """
        验证Standard Webhooks格式的签名

        :param webhook_signature: webhook签名
        :param webhook_id: webhook ID
        :param webhook_timestamp: webhook时间戳
        :param body: 请求体
        :param secret_key: 密钥
        :return:
        """
        # 验证时间戳（防止重放攻击）
        try:
            timestamp = int(webhook_timestamp)
            current_time = int(time.time())
            
            # 允许5分钟的时间偏差
            if abs(current_time - timestamp) > 300:
                raise errors.ForbiddenError(msg='请求时间戳过期')
        except ValueError:
            raise errors.ForbiddenError(msg='无效的时间戳格式')
        
        # 解析签名（格式：v1,<base64-signature>）
        if not webhook_signature.startswith('v1,'):
            raise errors.ForbiddenError(msg='不支持的签名版本')
        
        signature_b64 = webhook_signature[3:]  # 去掉 'v1,' 前缀
        
        try:
            received_signature = base64.b64decode(signature_b64)
        except Exception:
            raise errors.ForbiddenError(msg='无效的签名格式')
        
        # 构造签名载荷：webhook_id.webhook_timestamp.body
        signed_payload = f"{webhook_id}.{webhook_timestamp}.{body.decode('utf-8')}"
        
        # 计算期望的签名
        expected_signature = hmac.new(
            secret_key.encode('utf-8'),
            signed_payload.encode('utf-8'),
            hashlib.sha256
        ).digest()
        
        # 验证签名
        if not hmac.compare_digest(received_signature, expected_signature):
            raise errors.ForbiddenError(msg='Standard Webhook签名验证失败')

    @staticmethod
    def generate_standard_webhook_headers(payload: str, secret_key: str) -> dict[str, str]:
        """
        生成Standard Webhooks格式的请求头

        :param payload: 请求载荷
        :param secret_key: 密钥
        :return: 包含标准头的字典
        """
        # 生成唯一ID
        webhook_id = f"msg_{uuid.uuid4().hex[:24]}"
        
        # 生成时间戳
        webhook_timestamp = str(int(time.time()))
        
        # 构造签名载荷
        signed_payload = f"{webhook_id}.{webhook_timestamp}.{payload}"
        
        # 计算签名
        signature = hmac.new(
            secret_key.encode('utf-8'),
            signed_payload.encode('utf-8'),
            hashlib.sha256
        ).digest()
        
        # Base64编码签名
        signature_b64 = base64.b64encode(signature).decode('utf-8')
        
        # 返回标准头
        return {
            'webhook-id': webhook_id,
            'webhook-timestamp': webhook_timestamp,
            'webhook-signature': f'v1,{signature_b64}'
        }

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

    async def receive_generic_webhook(self, request: Request) -> dict[str, Any]:
        """
        接收通用格式的Webhook事件（支持任意格式）

        Args:
            request: FastAPI请求对象
            \n
        Returns:
            dict: 处理结果
        """
        try:
            # 获取请求体
            body = await request.body()
            body_str = body.decode('utf-8') if body else '{}'
            
            # 尝试解析JSON
            try:
                body_json = json.loads(body_str) if body_str else {}
            except json.JSONDecodeError:
                body_json = {'raw_data': body_str}
            
            # 获取请求头
            headers = dict(request.headers)
            user_agent = headers.get('user-agent', 'unknown')
            
            # 自动推断事件类型
            event_type = self._infer_event_type(body_json, headers, str(request.url))
            
            # 简化验证逻辑：仅记录日志，不阻止处理
            try:
                active_configs = await self.get_active_webhook_configs()
                if active_configs:
                    log.info(f"找到 {len(active_configs)} 个活跃的webhook配置")
            except Exception as e:
                log.warning(f"获取webhook配置失败: {e}")
                active_configs = []
            
            # 处理payload数据
            payload_str = body_str if body_str else json.dumps(body_json, ensure_ascii=False)
            
            # 创建webhook事件记录
            webhook_data = {
                'event_type': event_type,
                'source': user_agent[:500] if user_agent else 'unknown',
                'webhook_url': str(request.url),
                'headers': headers,
                'payload': payload_str,
                'status': 1,  # 成功状态
                'processed_at': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
                'retry_count': 0,
                'error_message': None,
            }
            
            # 创建webhook记录
            async with async_db_session.begin() as db:
                webhook = await webhook_dao.create(db, CreateWebhookParam(**webhook_data))
            
            # 处理webhook事件
            await self._process_webhook_event(webhook, body_json)
            
            return {
                'success': True,
                'message': 'Webhook事件处理成功',
                'webhook_id': webhook.id,
                'event_type': event_type,
                'processed_at': webhook.processed_at if webhook.processed_at else None
            }
            
        except Exception as e:
            # 记录失败的webhook事件
            error_message = str(e)[:1000]
            
            # 获取基本信息
            try:
                body = await request.body()
                body_str = body.decode('utf-8') if body else '{}'
                headers = dict(request.headers)
                user_agent = headers.get('user-agent', 'unknown')
                event_type = 'unknown'
            except:
                body_str = '{}'
                headers = {}
                user_agent = 'unknown'
                event_type = 'unknown'
            
            webhook_data = {
                'event_type': event_type,
                'source': user_agent[:500] if user_agent else 'unknown',
                'webhook_url': str(request.url),
                'headers': headers,
                'payload': body_str,
                'status': 0,  # 失败状态
                'error_message': error_message,
                'retry_count': 0,
                'processed_at': None,
            }
            
            # 尝试创建失败记录
            try:
                async with async_db_session.begin() as db:
                    await webhook_dao.create(db, CreateWebhookParam(**webhook_data))
            except Exception as db_error:
                log.error(f"无法创建失败的webhook记录: {db_error}")
            
            # 记录错误日志
            log.error(f"Webhook事件处理失败: {error_message}")
            
            return {
                'success': False,
                'message': f'Webhook事件处理失败: {error_message}',
                'error': error_message
            }

    def _infer_event_type(self, body_json: dict, headers: dict, url: str) -> str:
        """
        推断事件类型

        Args:
            body_json: 请求体JSON
            headers: 请求头
            url: 请求URL
            \n
        Returns:
            str: 推断的事件类型
        """
        # 1. 从请求体中查找事件类型
        if isinstance(body_json, dict):
            for key in ['event_type', 'event', 'type', 'action', 'eventType']:
                if key in body_json:
                    return str(body_json[key])
        
        # 2. 从请求头中查找
        for key in ['x-event-type', 'x-github-event', 'x-gitlab-event']:
            if key in headers:
                return headers[key]
        
        # 3. 从User-Agent推断
        user_agent = headers.get('user-agent', '').lower()
        if 'github' in user_agent:
            return 'github.webhook'
        elif 'gitlab' in user_agent:
            return 'gitlab.webhook'
        elif 'stripe' in user_agent:
            return 'stripe.webhook'
        
        # 4. 从URL推断
        if 'github' in url:
            return 'github.webhook'
        elif 'gitlab' in url:
            return 'gitlab.webhook'
        
        # 5. 默认事件类型
        return 'webhook.generic'
    
    async def get_active_webhook_configs(self) -> Sequence[WebhookConfig]:
        """
        获取活跃的webhook配置
        
        Returns:
            Sequence[WebhookConfig]: 活跃的配置列表
        """
        async with async_db_session.begin() as db:
            return await webhook_config_dao.get_active_configs(db)
    
    async def _validate_webhook_request(self, request: Request, headers: dict, configs: Sequence[WebhookConfig]) -> None:
        """
        验证webhook请求
        
        Args:
            request: 请求对象
            headers: 请求头
            configs: webhook配置列表
            
        Raises:
            HTTPException: 验证失败时抛出异常
        """
        # 获取请求来源
        host = request.client.host if request.client else 'unknown'
        user_agent = headers.get('user-agent', '')
        
        # 检查是否是本地测试请求
        if host in ['127.0.0.1', 'localhost', '::1']:
            log.info(f"本地测试请求，跳过配置验证: {host}")
            return
        
        # 验证来源和头部
        for config in configs:
            if self._validate_config_match(request, headers, config):
                log.info(f"请求匹配配置: {config.name}")
                return
        
        # 如果没有匹配的配置，拒绝请求
        raise errors.ForbiddenError(msg="请求不匹配任何活跃的webhook配置")
    
    def _validate_config_match(self, request: Request, headers: dict, config: WebhookConfig) -> bool:
        """
        验证请求是否匹配配置
        
        Args:
            request: 请求对象
            headers: 请求头
            config: webhook配置
            
        Returns:
            bool: 是否匹配
        """
        # 验证必需的请求头
        if config.required_headers:
            for header_name, expected_value in config.required_headers.items():
                actual_value = headers.get(header_name.lower())
                if actual_value != expected_value:
                    return False
        
        return True

    async def receive_standard_webhook(self, request: Request) -> dict[str, Any]:
        """
        接收Standard Webhooks格式的事件

        Args:
            request: FastAPI请求对象
            \n
        Returns:
            dict: 处理结果
        """
        try:
            # 获取请求体和头部
            body = await request.body()
            body_str = body.decode('utf-8') if body else '{}'
            headers = dict(request.headers)
            
            # 验证Standard Webhooks必需头部
            webhook_id = headers.get('webhook-id')
            webhook_timestamp = headers.get('webhook-timestamp')
            webhook_signature = headers.get('webhook-signature')
            
            if not all([webhook_id, webhook_timestamp, webhook_signature]):
                raise errors.RequestError(msg="缺少Standard Webhooks必需头部")
            
            # 验证时间戳（5分钟容忍时间）
            current_time = int(time.time())
            try:
                request_time = int(webhook_timestamp) if webhook_timestamp else 0
            except (ValueError, TypeError):
                raise errors.RequestError(msg="时间戳格式无效")
                
            if abs(current_time - request_time) > 300:  # 5分钟
                raise errors.RequestError(msg="请求时间戳无效")
            
            # 解析JSON数据
            try:
                body_json = json.loads(body_str) if body_str else {}
            except json.JSONDecodeError:
                raise errors.RequestError(msg="请求体必须是有效的JSON")
            
            # 推断事件类型
            event_type = self._infer_event_type(body_json, headers, str(request.url))
            user_agent = headers.get('user-agent', 'standard-webhook')
            
            # 创建webhook事件记录
            webhook_data = {
                'event_type': event_type,
                'source': user_agent[:500],
                'webhook_url': str(request.url),
                'headers': headers,
                'payload': body_str,
                'status': 1,
                'processed_at': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
                'retry_count': 0,
                'error_message': None,
            }
            
            # 创建webhook记录
            async with async_db_session.begin() as db:
                webhook = await webhook_dao.create(db, CreateWebhookParam(**webhook_data))
            
            # 处理webhook事件
            await self._process_webhook_event(webhook, body_json)
            
            return {
                'success': True,
                'message': 'Standard Webhook事件处理成功',
                'webhook_id': webhook.id,
                'event_type': event_type,
                'standard_webhook_id': webhook_id,
                'processed_at': webhook.processed_at
            }
            
        except Exception as e:
            # 记录失败事件
            error_message = str(e)[:1000]
            log.error(f"Standard Webhook事件处理失败: {error_message}")
            
            # 尝试创建失败记录
            try:
                body = await request.body()
                webhook_data = {
                    'event_type': 'standard.webhook.failed',
                    'source': 'standard-webhook',
                    'webhook_url': str(request.url),
                    'headers': dict(request.headers),
                    'payload': body.decode('utf-8') if body else '{}',
                    'status': 0,
                    'error_message': error_message,
                    'retry_count': 0,
                    'processed_at': None,
                }
                
                async with async_db_session.begin() as db:
                    await webhook_dao.create(db, CreateWebhookParam(**webhook_data))
            except Exception as db_error:
                log.error(f"无法创建失败记录: {db_error}")
            
            return {
                'success': False,
                'message': f'Standard Webhook事件处理失败: {error_message}',
                'error': error_message
            }


webhook_service: WebhookService = WebhookService() 