#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import html
import re

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from backend.common.exception import errors
from backend.database.db import CurrentSessionTransaction
from backend.plugin.links.service import page_service

router = APIRouter()

_FULL_DOC_PATTERN = re.compile(r'^\s*<(!doctype|html)\b', re.IGNORECASE)
_SECURITY_HEADERS = {'X-Content-Type-Options': 'nosniff'}

_NOT_FOUND_HTML = """<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>页面不存在</title>
</head>
<body style="margin:0;display:flex;align-items:center;justify-content:center;min-height:100vh;font-family:system-ui,sans-serif;color:#666;background:#fafafa">
<div style="text-align:center">
<p style="font-size:18px">页面不存在或已下线</p>
</div>
</body>
</html>"""


def _render(title: str, html_content: str | None) -> str:
    """
    渲染页面 HTML，完整文档原样返回，片段套用最小骨架

    :param title: 页面标题
    :param html_content: HTML 内容
    :return:
    """
    body = html_content or ''
    if _FULL_DOC_PATTERN.match(body):
        return body
    return (
        '<!DOCTYPE html>\n'
        '<html lang="zh">\n'
        '<head>\n'
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f'<title>{html.escape(title)}</title>\n'
        '</head>\n'
        f'<body>\n{body}\n</body>\n'
        '</html>'
    )


def _get_request_info(request: Request) -> dict:
    """提取请求信息"""
    return {
        'ip': request.client.host if request.client else None,
        'user_agent': request.headers.get('user-agent'),
        'referer': request.headers.get('referer'),
        'country': None,
        'city': None,
    }


@router.get('/{code}', summary='渲染页面', response_class=HTMLResponse)
async def render_page(db: CurrentSessionTransaction, request: Request, code: str):
    try:
        request_info = _get_request_info(request)
        page = await page_service.render(db=db, code=code, request_info=request_info)
    except (errors.NotFoundError, errors.RequestError):
        return HTMLResponse(content=_NOT_FOUND_HTML, status_code=404, headers=_SECURITY_HEADERS)

    return HTMLResponse(content=_render(page.title, page.html_content), headers=_SECURITY_HEADERS)
