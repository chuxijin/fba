#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Query

from backend.common.response.response_schema import ResponseModel, response_base
from backend.plugin.baidupan.schema.oauth import (
    OAuthAuthorizeRequest,
    OAuthCallbackRequest,
    OAuthRefreshRequest,
)
from backend.plugin.baidupan.service.oauth_service import baidupan_oauth_service

router = APIRouter()


@router.post('/authorize', summary='获取授权 URL')
async def baidupan_get_authorize_url(request: OAuthAuthorizeRequest) -> ResponseModel:
    """
    生成百度网盘 OAuth 授权跳转 URL

    :param request: 授权请求参数
    :return:
    """
    result = await baidupan_oauth_service.generate_authorize_url(request)
    return response_base.success(data=result)


@router.get('/callback', summary='OAuth 回调')
async def baidupan_oauth_callback(
    code: Annotated[str, Query(description='授权码')],
    state: Annotated[str | None, Query(description='状态参数')] = None,
) -> ResponseModel:
    """
    处理百度网盘 OAuth 回调，用授权码换取 access_token

    :param code: 授权码
    :param state: 状态参数
    :return:
    """
    result = await baidupan_oauth_service.handle_callback(code=code, state=state)
    return response_base.success(data=result)


@router.post('/callback', summary='OAuth 回调（POST）')
async def baidupan_oauth_callback_post(request: OAuthCallbackRequest) -> ResponseModel:
    """
    处理百度网盘 OAuth 回调（POST 方式）

    :param request: 回调请求参数
    :return:
    """
    result = await baidupan_oauth_service.handle_callback(code=request.code, state=request.state)
    return response_base.success(data=result)


@router.post('/refresh', summary='刷新 Token')
async def baidupan_refresh_token(request: OAuthRefreshRequest) -> ResponseModel:
    """
    使用 refresh_token 刷新 access_token

    :param request: 刷新请求参数
    :return:
    """
    result = await baidupan_oauth_service.refresh_token(request)
    return response_base.success(data=result)
