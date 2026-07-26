import time

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.routing import Match

from backend.common.context import ctx
from backend.common.log import log
from backend.common.observability.prometheus.fastapi import (
    dec_fastapi_request_in_progress,
    inc_fastapi_exception,
    inc_fastapi_request,
    inc_fastapi_request_in_progress,
    inc_fastapi_response,
    observe_fastapi_request_cost_time,
)
from backend.common.response.response_code import StandardResponseCode
from backend.core.conf import settings
from backend.utils.timezone import timezone
from backend.utils.trace_id import get_request_trace_id


def resolve_request_path_template(request: Request) -> str:
    """将实际请求路径解析为低基数路由模板"""
    route = request.scope.get('route')
    route_path = getattr(route, 'path', None)
    if route_path:
        return str(route_path)

    for app_route in request.app.routes:
        match, _ = app_route.matches(request.scope)
        if match is Match.FULL:
            matched_path = getattr(app_route, 'path', None)
            if matched_path:
                return str(matched_path)
    return '__unmatched__'


class AccessMiddleware(BaseHTTPMiddleware):
    """访问日志中间件"""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:  # ruff:ignore[complex-structure]
        """
        处理请求并记录访问日志

        :param request: FastAPI 请求对象
        :param call_next: 下一个中间件或路由处理函数
        :return:
        """
        perf_time = time.perf_counter()
        ctx.perf_time = perf_time

        start_time = timezone.now()
        ctx.start_time = start_time

        path = request.url.path
        method = request.method

        if method != 'OPTIONS':
            log.debug(f'--> 请求开始[{path if not request.url.query else request.url.path + "?" + request.url.query}]')

        should_record_metrics = settings.GRAFANA_METRICS_ENABLE and path.startswith(settings.FASTAPI_API_V1_PATH)
        metrics_path = resolve_request_path_template(request) if should_record_metrics else path
        if should_record_metrics:
            inc_fastapi_request_in_progress(method=method, path=metrics_path)
            inc_fastapi_request(method=method, path=metrics_path)

        try:
            response = await call_next(request)
        except Exception as e:
            elapsed = round((time.perf_counter() - perf_time) * 1000, 3)
            if should_record_metrics:
                inc_fastapi_exception(method=method, path=metrics_path, exception_type=type(e).__name__)
                error_status_code = getattr(e, 'code', StandardResponseCode.HTTP_500)
                observe_fastapi_request_cost_time(
                    method=method,
                    path=metrics_path,
                    elapsed=elapsed,
                    trace_id=get_request_trace_id(),
                    status_code=error_status_code,
                )
                inc_fastapi_response(
                    method=method,
                    path=metrics_path,
                    status_code=error_status_code,
                )
            raise
        else:
            elapsed = round((time.perf_counter() - perf_time) * 1000, 3)
            if should_record_metrics:
                exception_type = None
                exception_code = None
                for exception_key, current_exception_type in {
                    '__request_authentication_exception__': 'AuthenticationError',
                    '__request_http_exception__': 'HTTPException',
                    '__request_validation_exception__': 'RequestValidationError',
                    '__request_assertion_error__': 'AssertionError',
                    '__request_custom_exception__': 'BaseExceptionError',
                    '__request_unknown_exception__': 'Exception',
                }.items():
                    exception = ctx.get(exception_key)
                    if exception:
                        exception_type = current_exception_type
                        exception_code = exception.get('code')
                        break
                if exception_type is not None:
                    inc_fastapi_exception(method=method, path=metrics_path, exception_type=exception_type)
                observe_fastapi_request_cost_time(
                    method=method,
                    path=metrics_path,
                    elapsed=elapsed,
                    trace_id=get_request_trace_id(),
                    status_code=exception_code or response.status_code,
                )
                inc_fastapi_response(
                    method=method,
                    path=metrics_path,
                    status_code=exception_code or response.status_code,
                )
        finally:
            if should_record_metrics:
                dec_fastapi_request_in_progress(method=method, path=metrics_path)

        return response
