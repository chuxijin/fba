from functools import wraps
from typing import Any, Optional
import inspect

ERRORS = {
    0: 0,
    -1: "由于您分享了违反相关法律法规的文件，分享功能已被禁用，之前分享出去的文件不受影响。",
}

UNKNOWN_ERROR = "未知错误"


class QuarkApiError(Exception):
    def __init__(self, message: str, error_code: Optional[int] = None, cause=None):
        self.__cause__ = cause
        self.error_code = error_code
        super().__init__(message)


def parse_errno(error_code: int, info: Any = None) -> Optional[QuarkApiError]:
    if error_code != 0:
        mean = ERRORS.get(error_code, info or UNKNOWN_ERROR)
        msg = f"error_code: {error_code}, message: {mean}"
        return QuarkApiError(msg, error_code=error_code)
    return None


def assert_ok(func):
    """Assert the code of response is 0
    支持同步和异步函数
    """

    @wraps(func)
    async def async_check(*args, **kwargs):
        info = await func(*args, **kwargs)
        code = info.get("code")  # 获取 code 字段
        if code is None:
            code = 0  # 默认值

        if code != 0:  # 判断 code 是否为 0
            err = QuarkApiError(f"Error code: {code}, message: {info.get('message', 'Unknown error')}")
            raise err
        return info

    @wraps(func)
    def sync_check(*args, **kwargs):
        info = func(*args, **kwargs)
        code = info.get("code")  # 获取 code 字段
        if code is None:
            code = 0  # 默认值

        if code != 0:  # 判断 code 是否为 0
            err = QuarkApiError(f"Error code: {code}, message: {info.get('message', 'Unknown error')}")
            raise err
        return info

    # 根据被装饰函数是否为协程函数来选择返回异步或同步包装器
    if inspect.iscoroutinefunction(func):
        return async_check
    else:
        return sync_check
