#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from backend.database.db import CurrentSessionTransaction
from backend.plugin.links.service import dwz_service

router = APIRouter()


def _get_request_info(request: Request) -> dict:
    """提取请求信息"""
    return {
        'ip': request.client.host if request.client else None,
        'user_agent': request.headers.get('user-agent'),
        'referer': request.headers.get('referer'),
        'country': None,
        'city': None,
    }


@router.get('/{code}', summary='短链重定向')
async def redirect_dwz(db: CurrentSessionTransaction, request: Request, code: str) -> RedirectResponse:
    current_domain = request.headers.get('host', '').split(':')[0]
    request_info = _get_request_info(request)
    target_url = await dwz_service.redirect(
        db=db,
        code=code,
        request_info=request_info,
        current_domain=current_domain,
    )
    return RedirectResponse(url=target_url, status_code=302)
