#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from backend.common.exception import errors
from backend.database.db import CurrentSessionTransaction
from backend.plugin.links.service import kf_service
from backend.plugin.links.service.online_utils import is_dark_theme, parse_online_status

router = APIRouter()

# 模板目录
TEMPLATES_DIR = Path(__file__).parent.parent.parent / 'templates'
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def _get_request_info(request: Request) -> dict:
    """提取请求信息"""
    return {
        'ip': request.client.host if request.client else None,
        'user_agent': request.headers.get('user-agent'),
        'referer': request.headers.get('referer'),
        'country': None,
        'city': None,
    }


@router.get('/{code}', summary='客服码页面', response_class=HTMLResponse)
async def render_kf_page(db: CurrentSessionTransaction, request: Request, code: str):
    try:
        request_info = _get_request_info(request)
        item = await kf_service.redirect(db=db, code=code, request_info=request_info)
        kf = await kf_service.get_by_code(db=db, code=code)

        # 解析在线状态
        online_status = parse_online_status(kf.online if kf else None)

        return templates.TemplateResponse(
            'kf.html',
            {
                'request': request,
                'title': kf.title if kf else '联系客服',
                'qrcode': item.qrcode,
                'leader': item.leader,
                'remark': kf.remark if kf else None,
                'item_id': item.id,
                'longpress_url': f'/k/{code}/longpress',
                'is_online': online_status['is_online'],
                'status_text': online_status['status_text'],
                'offline_msg': online_status['offline_msg'],
                'dark_theme': is_dark_theme(),
            },
        )
    except errors.NotFoundError:
        return templates.TemplateResponse(
            'error.html',
            {
                'request': request,
                'title': '页面不存在',
                'message': '客服码不存在或已失效',
                'dark_theme': is_dark_theme(),
            },
            status_code=404,
        )
    except errors.RequestError as e:
        return templates.TemplateResponse(
            'error.html',
            {'request': request, 'title': '暂不可用', 'message': str(e.msg), 'dark_theme': is_dark_theme()},
            status_code=400,
        )


@router.post('/{code}/longpress', summary='客服码长按记录')
async def record_kf_longpress(db: CurrentSessionTransaction, code: str, item_id: int):
    await kf_service.record_longpress(db=db, item_id=item_id)
    return {'code': 200, 'msg': 'ok'}
