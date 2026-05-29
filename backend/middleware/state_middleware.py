#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import time

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from backend.common.context import ctx
from backend.common.log import log
from backend.utils.request_parse import parse_ip_info, parse_user_agent_info


_ACCESS_MY_PERF_PATHS = {
    '/api/v1/access/my/summary',
    '/api/v1/access/my/subscriptions',
    '/api/v1/access/my/entitlements',
}


class StateMiddleware(BaseHTTPMiddleware):
    """请求状态中间件"""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """
        处理请求并设置请求状态信息

        :param request: FastAPI 请求对象
        :param call_next: 下一个中间件或路由处理函数
        :return:
        """
        path = request.url.path
        should_log_perf = path in _ACCESS_MY_PERF_PATHS
        total_start = time.perf_counter()

        ip_start = time.perf_counter()
        ip_info = await parse_ip_info(request)
        if should_log_perf:
            log.info(
                f'access-my-perf | {path} | state.parse_ip='
                f'{(time.perf_counter() - ip_start) * 1000:.3f}ms ip={ip_info.ip}'
            )

        ctx.ip = ip_info.ip
        ctx.country = ip_info.country
        ctx.region = ip_info.region
        ctx.city = ip_info.city

        ua_start = time.perf_counter()
        ua_info = parse_user_agent_info(request)
        if should_log_perf:
            log.info(
                f'access-my-perf | {path} | state.parse_user_agent='
                f'{(time.perf_counter() - ua_start) * 1000:.3f}ms'
            )

        ctx.user_agent = ua_info.user_agent
        ctx.os = ua_info.os
        ctx.browser = ua_info.browser
        ctx.device = ua_info.device

        response = await call_next(request)
        if should_log_perf:
            log.info(
                f'access-my-perf | {path} | state.total='
                f'{(time.perf_counter() - total_start) * 1000:.3f}ms'
            )

        return response
