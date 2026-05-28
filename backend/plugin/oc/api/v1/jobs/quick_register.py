"""快速注册 API"""

from typing import Annotated

from fastapi import APIRouter, Query, Request

from backend.common.response.response_schema import ResponseModel, response_base
from backend.common.exception import errors
from backend.database.db import CurrentSession
from backend.utils.request_parse import get_request_ip
from backend.plugin.oc.service.quick_register_service import quick_register_service
from backend.plugin.oc.schema.quick_register import QuickRegisterParam


router = APIRouter()


# IP 白名单
ALLOWED_IPS = ['212.64.23.13', '127.0.0.1']


@router.get(
    '/quick-register',
    summary='快速注册用户',
    description='通过手机号快速注册用户，用户名和密码默认为手机号。仅限白名单 IP 访问。',
)
async def quick_register(
    request: Request,
    db: CurrentSession,
    phone: Annotated[str, Query(description='手机号（11位）')],
) -> ResponseModel:
    """
    快速注册用户

    - **phone**: 手机号（必填，11位）

    返回:
    - **username**: 用户名（即手机号）
    - **password**: 密码（明文，即手机号）
    """
    # IP 白名单校验
    client_ip = get_request_ip(request)
    if client_ip not in ALLOWED_IPS:
        raise errors.ForbiddenError(msg=f'IP {client_ip} 无权访问此接口')

    # 校验手机号格式（Pydantic validator 会自动校验）
    param = QuickRegisterParam(phone=phone)

    # 执行注册
    result = await quick_register_service.quick_register(db, param)

    return response_base.success(data=result)
