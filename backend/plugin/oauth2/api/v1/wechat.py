from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Body, Response
from pyrate_limiter import Duration, Rate

from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.core.conf import settings
from backend.database.db import CurrentSessionTransaction
from backend.plugin.oauth2.enums import UserSocialType
from backend.plugin.oauth2.service.oauth2_service import oauth2_service

router = APIRouter()


@router.post(
    '/miniapp/login',
    summary='微信小程序登录',
    description='通过小程序的 code 换取 openid 进行登录或自动注册',
)
async def wechat_miniapp_login(
    db: CurrentSessionTransaction,
    response: Response,
    background_tasks: BackgroundTasks,
    code: Annotated[str, Body(description='微信 wx.login 返回的 code')],
    nickname: Annotated[str | None, Body(description='用户授权的昵称')] = None,
    avatar: Annotated[str | None, Body(description='用户授权的头像')] = None,
) -> ResponseSchemaModel:
    
    data = await oauth2_service.wechat_miniapp_login(
        db=db,
        response=response,
        background_tasks=background_tasks,
        code=code,
        nickname=nickname,
        avatar=avatar
    )
    
    return response_base.success(data=data)
