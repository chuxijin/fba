from functools import wraps
from typing import Any, Optional
import inspect

ERRORS = {
    200: "success",
    500: "服务器内部错误",
    401: "未授权",
    403: "禁止访问",
    404: "资源不存在"
}

UNKNOWN_ERROR = "未知错误"


class AlistApiError(Exception):
    def __init__(self, message: str, error_code: Optional[int] = None, cause=None):
        self.__cause__ = cause
        self.error_code = error_code
        super().__init__(message)


def parse_errno(error_code: int, info: Any = None) -> Optional[AlistApiError]:
    if error_code != 200:
        mean = ERRORS.get(error_code, info or UNKNOWN_ERROR)
        msg = f"error_code: {error_code}, message: {mean}"
        return AlistApiError(msg, error_code=error_code)
    return None


def assert_ok(func):
    """Assert the code of response is 200
    支持同步和异步函数
    """

    @wraps(func)
    async def async_check(*args, **kwargs):
        info = await func(*args, **kwargs)
        code = info.get("code")  # 获取 code 字段
        if code is None:
            code = 500  # 如果没有code字段，视为服务器错误

        if code != 200:  # 判断 code 是否为 200
            err = AlistApiError(f"Error code: {code}, message: {info.get('message', 'Unknown error')}")
            raise err
        return info.get("data", info)  # 如果成功，返回data字段，如果没有data字段则返回整个响应

    @wraps(func)
    def sync_check(*args, **kwargs):
        info = func(*args, **kwargs)
        code = info.get("code")  # 获取 code 字段
        if code is None:
            code = 500  # 如果没有code字段，视为服务器错误

        if code != 200:  # 判断 code 是否为 200
            err = AlistApiError(f"Error code: {code}, message: {info.get('message', 'Unknown error')}")
            raise err
        return info.get("data", info)  # 如果成功，返回data字段，如果没有data字段则返回整个响应

    # 根据被装饰函数是否为协程函数来选择返回异步或同步包装器
    if inspect.iscoroutinefunction(func):
        return async_check
    else:
        return sync_check
