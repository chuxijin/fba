#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""开放平台客户端管理服务（管理台用）"""

import secrets

from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.exception import errors
from backend.common.pagination import paging_data
from backend.plugin.openauth.crud.crud_openauth import client_enabled, openauth_client_dao
from backend.plugin.openauth.enums import OpenAuthClientStatus
from backend.plugin.openauth.model import OpenAuthClient
from backend.plugin.openauth.schema.client import (
    CreateOpenAuthClientDetail,
    CreateOpenAuthClientParam,
    GetOpenAuthClientDetail,
    ResetOpenAuthSecretDetail,
    UpdateOpenAuthClientParam,
)
from backend.plugin.openauth.service.constants import hash_client_secret


def _generate_client_id() -> str:
    """client_id：可读前缀 + 随机串"""
    return f'oac_{secrets.token_hex(8)}'


class OpenAuthClientService:
    @staticmethod
    async def get_page(db: AsyncSession, *, name: str | None, status: int | None) -> dict:
        stmt = await openauth_client_dao.get_select(name__like=name, status=status, deleted=0)
        return await paging_data(db, stmt, schema_cls=GetOpenAuthClientDetail)

    @staticmethod
    async def get(db: AsyncSession, *, pk: int) -> OpenAuthClient:
        client = await openauth_client_dao.get(db, pk=pk)
        if not client or client.deleted:
            raise errors.NotFoundError(msg='客户端不存在')
        return client

    @staticmethod
    async def get_by_client_id(db: AsyncSession, *, client_id: str) -> OpenAuthClient:
        client = await openauth_client_dao.get_by_client_id(db, client_id=client_id)
        if not client or client.deleted:
            raise errors.NotFoundError(msg=f'客户端不存在: {client_id}')
        return client

    @staticmethod
    async def get_enabled_by_client_id(db: AsyncSession, *, client_id: str) -> OpenAuthClient:
        """OAuth 流程使用：必须存在且启用"""
        client = await openauth_client_dao.get_by_client_id(db, client_id=client_id)
        if not client or client.deleted:
            raise errors.NotFoundError(msg=f'客户端不存在: {client_id}')
        if not client_enabled(client):
            raise errors.ForbiddenError(msg='该应用已停用，暂无法授权')
        return client

    @staticmethod
    async def create(db: AsyncSession, *, obj: CreateOpenAuthClientParam) -> CreateOpenAuthClientDetail:
        client_id = _generate_client_id()
        secret = (obj.client_secret or secrets.token_urlsafe(48)) if obj.client_type == 'confidential' else None
        client = OpenAuthClient(
            client_id=client_id,
            client_secret_hash=hash_client_secret(secret) if secret else '',
            client_type=obj.client_type,
            name=obj.name,
            description=obj.description,
            icon=obj.icon,
            scopes=obj.scopes,
            redirect_uris=obj.redirect_uris,
            status=OpenAuthClientStatus.ENABLED.value,
        )
        db.add(client)
        await db.flush()
        return CreateOpenAuthClientDetail(
            id=client.id,
            client_id=client.client_id,
            client_type=client.client_type,
            name=client.name,
            description=client.description,
            icon=client.icon,
            scopes=client.scopes,
            redirect_uris=client.redirect_uris,
            status=client.status,
            created_time=client.created_time,
            updated_time=client.updated_time,
            client_secret=secret,
        )

    @staticmethod
    async def update(db: AsyncSession, *, pk: int, obj: UpdateOpenAuthClientParam) -> int:
        client = await OpenAuthClientService.get(db, pk=pk)
        if obj.reset_secret:
            if client.client_type == 'public':
                raise errors.RequestError(msg='公开客户端不使用共享密钥')
            if not obj.new_client_secret:
                raise errors.RequestError(msg='重置密钥必须提供 new_client_secret')
        data = obj.model_dump(exclude_unset=True, exclude={'reset_secret', 'new_client_secret'})
        count = await openauth_client_dao.update_model(db, pk, data)
        if obj.reset_secret and obj.new_client_secret:
            client = await OpenAuthClientService.get(db, pk=pk)
            client.client_secret_hash = hash_client_secret(obj.new_client_secret)
            await db.flush()
        return count

    @staticmethod
    async def delete(db: AsyncSession, *, pk: int) -> int:
        await OpenAuthClientService.get(db, pk=pk)
        return await openauth_client_dao.delete_model(db, pk)

    @staticmethod
    async def reset_secret(db: AsyncSession, *, pk: int, new_secret: str | None = None) -> ResetOpenAuthSecretDetail:
        client = await OpenAuthClientService.get(db, pk=pk)
        if client.client_type == 'public':
            raise errors.RequestError(msg='公开客户端不使用共享密钥')
        new_secret = new_secret or secrets.token_urlsafe(48)
        client.client_secret_hash = hash_client_secret(new_secret)
        await db.flush()
        return ResetOpenAuthSecretDetail(client_id=client.client_id, client_secret=new_secret)


openauth_client_service = OpenAuthClientService()
