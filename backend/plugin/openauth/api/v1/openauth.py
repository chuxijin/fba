#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""开放平台授权中心 API

三类调用方：
- 前端授权页（用户 JWT）：preview / authorize / 解绑
- 第三方程序 CLI（client 凭证 / 客户端 token）：token / refresh / check
- 管理台（RBAC）：client CRUD
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request, Response

from backend.common.pagination import DependsPagination, PageData
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.common.security.permission import RequestPermission
from backend.common.security.rbac import DependsRBAC
from backend.database.db import CurrentSession, CurrentSessionTransaction
from backend.plugin.openauth.dependencies import OpenAuthBearerToken, RequireOpenAuth
from backend.plugin.openauth.schema.authorization import (
    CreateOpenAuthAuthorizationParam,
    CreateOpenAuthRefreshParam,
    CreateOpenAuthRevokeParam,
    CreateOpenAuthTokenParam,
    GetOpenAuthAuthorizationPreview,
    GetOpenAuthAuthorizationResult,
    GetOpenAuthCheckResult,
    GetOpenAuthTokenResult,
    GetOpenAuthUserAuthorizationDetail,
)
from backend.plugin.openauth.schema.client import (
    CreateOpenAuthClientDetail,
    CreateOpenAuthClientParam,
    GetOpenAuthClientDetail,
    ResetOpenAuthSecretDetail,
    ResetOpenAuthSecretParam,
    UpdateOpenAuthClientParam,
)
from backend.plugin.openauth.schema.profile import GetOpenAuthProfile
from backend.plugin.openauth.service.authorization_service import openauth_authorization_service
from backend.plugin.openauth.service.client_service import openauth_client_service
from backend.plugin.openauth.service.profile_service import openauth_profile_service


def no_store(response: Response) -> None:
    response.headers['Cache-Control'] = 'no-store'
    response.headers['Pragma'] = 'no-cache'


router = APIRouter(dependencies=[Depends(no_store)])
client_router = APIRouter(dependencies=[Depends(no_store)])


# ============================================================================
# 前端授权页（用户 JWT）
# ============================================================================


@router.post('/authorize/preview', summary='授权确认页预览', dependencies=[DependsJwtAuth])
async def get_openauth_authorize_preview(
    request: Request,
    db: CurrentSession,
    obj: CreateOpenAuthAuthorizationParam,
) -> ResponseSchemaModel[GetOpenAuthAuthorizationPreview]:
    """授权页渲染数据：应用信息 + 申请权限 + 是否已授权过（免二次确认提示）"""
    client = await openauth_client_service.get_enabled_by_client_id(db, client_id=obj.client_id)
    data = await openauth_authorization_service.get_authorize_preview(
        db, user_id=int(request.user.id), client=client, obj=obj
    )
    return response_base.success(data=data)


@router.post('/authorize', summary='同意授权', dependencies=[DependsJwtAuth])
async def create_openauth_authorization(
    request: Request,
    db: CurrentSessionTransaction,
    obj: CreateOpenAuthAuthorizationParam,
) -> ResponseSchemaModel[GetOpenAuthAuthorizationResult]:
    """用户同意授权：写入/激活授权关系，签发一次性 code（前端带 code 重定向回调用方）"""
    client = await openauth_client_service.get_enabled_by_client_id(db, client_id=obj.client_id)
    data = await openauth_authorization_service.authorize(db, user_id=int(request.user.id), client=client, obj=obj)
    return response_base.success(data=data)


@router.post('/revoke', summary='解绑应用授权', dependencies=[DependsJwtAuth])
async def revoke_openauth_authorization(
    request: Request,
    db: CurrentSessionTransaction,
    obj: CreateOpenAuthRevokeParam,
) -> ResponseModel:
    """用户解绑：吊销该应用全部 token 并将授权关系置为 revoked"""
    client = await openauth_client_service.get_by_client_id(db, client_id=obj.client_id)
    await openauth_authorization_service.revoke(db, user_id=int(request.user.id), client=client, obj=obj)
    return response_base.success()


@router.get('/authorizations', summary='我的应用授权', dependencies=[DependsJwtAuth])
async def get_openauth_authorizations(
    request: Request,
    db: CurrentSession,
) -> ResponseSchemaModel[list[GetOpenAuthUserAuthorizationDetail]]:
    data = await openauth_authorization_service.list_authorizations(db, user_id=int(request.user.id))
    return response_base.success(data=data)


# ============================================================================
# 第三方程序 CLI（client 凭证 / 客户端 token）
# ============================================================================


@router.post('/token', summary='授权码换取 token')
async def create_openauth_token(
    db: CurrentSession,
    obj: CreateOpenAuthTokenParam,
) -> ResponseSchemaModel[GetOpenAuthTokenResult]:
    """一次性 code + PKCE → access/refresh token；机密客户端额外验证密钥"""
    data = await openauth_authorization_service.create_token(db, obj=obj)
    return response_base.success(data=data)


@router.post('/refresh', summary='刷新 access token')
async def refresh_openauth_token(
    db: CurrentSession,
    obj: CreateOpenAuthRefreshParam,
) -> ResponseSchemaModel[GetOpenAuthTokenResult]:
    """refresh_token 换新 access_token（旋转：旧 refresh 立即作废）"""
    data = await openauth_authorization_service.refresh(db, obj=obj)
    return response_base.success(data=data)


@router.post('/check', summary='客户端 token 自检')
async def check_openauth_token(
    db: CurrentSessionTransaction,
    token: OpenAuthBearerToken,
) -> ResponseSchemaModel[GetOpenAuthCheckResult]:
    """当前凭据的身份与权限自检，不替代业务接口自身的 RequireOpenAuth"""
    data = await openauth_authorization_service.check(db, token=token)
    return response_base.success(data=data)


@router.post('/logout', summary='退出当前设备授权会话')
async def logout_openauth(db: CurrentSessionTransaction, token: OpenAuthBearerToken) -> ResponseModel:
    await openauth_authorization_service.logout(db, token=token)
    return response_base.success()


@router.get('/profile', summary='读取当前授权账号资料')
async def get_openauth_profile(
    db: CurrentSessionTransaction,
    identity: Annotated[GetOpenAuthCheckResult, Depends(RequireOpenAuth('profile:read'))],
) -> ResponseSchemaModel[GetOpenAuthProfile]:
    data = await openauth_profile_service.get_profile(db, user_id=identity.user_id)
    return response_base.success(data=data)


# ============================================================================
# 管理台（RBAC）
# ============================================================================


@client_router.post(
    '', summary='创建客户端', dependencies=[Depends(RequestPermission('openauth:client:add')), DependsRBAC]
)
async def create_openauth_client(
    db: CurrentSessionTransaction,
    obj: CreateOpenAuthClientParam,
) -> ResponseSchemaModel[CreateOpenAuthClientDetail]:
    """创建客户端；明文密钥仅此响应返回一次"""
    data = await openauth_client_service.create(db, obj=obj)
    return response_base.success(data=data)


@client_router.delete(
    '/{pk}', summary='删除客户端', dependencies=[Depends(RequestPermission('openauth:client:delete')), DependsRBAC]
)
async def delete_openauth_client(
    db: CurrentSessionTransaction, pk: Annotated[int, Path(description='客户端 ID')]
) -> ResponseModel:
    count = await openauth_client_service.delete(db, pk=pk)
    return response_base.success(count=count)


@client_router.put(
    '/{pk}', summary='更新客户端', dependencies=[Depends(RequestPermission('openauth:client:edit')), DependsRBAC]
)
async def update_openauth_client(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='客户端 ID')],
    obj: UpdateOpenAuthClientParam,
) -> ResponseModel:
    count = await openauth_client_service.update(db, pk=pk, obj=obj)
    return response_base.success(count=count)


@client_router.put(
    '/{pk}/secret',
    summary='重置客户端密钥',
    dependencies=[Depends(RequestPermission('openauth:client:secret')), DependsRBAC],
)
async def reset_openauth_client_secret(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='客户端 ID')],
    obj: ResetOpenAuthSecretParam,
) -> ResponseSchemaModel[ResetOpenAuthSecretDetail]:
    data = await openauth_client_service.reset_secret(db, pk=pk, new_secret=obj.new_secret)
    return response_base.success(data=data)


@client_router.get(
    '/{pk}', summary='获取客户端详情', dependencies=[Depends(RequestPermission('openauth:client:view')), DependsRBAC]
)
async def get_openauth_client(
    db: CurrentSession,
    pk: Annotated[int, Path(description='客户端 ID')],
) -> ResponseSchemaModel[GetOpenAuthClientDetail]:
    client = await openauth_client_service.get(db, pk=pk)
    return response_base.success(data=GetOpenAuthClientDetail.model_validate(client))


@client_router.get(
    '',
    summary='分页获取客户端列表',
    dependencies=[Depends(RequestPermission('openauth:client:list')), DependsRBAC, DependsPagination],
)
async def get_pagination_openauth_clients(
    db: CurrentSession,
    name: Annotated[str | None, Query(description='名称关键字')] = None,
    status: Annotated[int | None, Query(description='状态(0停用 1启用)')] = None,
) -> ResponseSchemaModel[PageData[GetOpenAuthClientDetail]]:
    page_data = await openauth_client_service.get_page(db, name=name, status=status)
    return response_base.success(data=page_data)
