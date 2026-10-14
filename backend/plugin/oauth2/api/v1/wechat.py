from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Body, Query, Response

from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.database.db import CurrentSessionTransaction
from backend.plugin.oauth2.service.oauth2_service import oauth2_service
from backend.plugin.oauth2.service.wechat_scan_service import wechat_scan_service

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
        db=db, response=response, background_tasks=background_tasks, code=code, nickname=nickname, avatar=avatar
    )

    return response_base.success(data=data)


@router.get(
    '/scan/qrcode',
    summary='生成微信小程序扫码登录码',
    description='用于浏览器插件或 PC 端展示带 scene_id 的动态微信官方小程序码',
)
async def get_scan_qrcode(
    page: Annotated[str, Query(description='小程序接收扫码的页面路径')] = 'pages/index/index',
) -> ResponseSchemaModel:
    data = await wechat_scan_service.generate_scan_qrcode(page=page)
    return response_base.success(data=data)


@router.get(
    '/scan/status',
    summary='轮询微信扫码登录状态',
    description='浏览器插件端轻量轮询检测扫码确认状态，已确认时返回登录 Token',
)
async def check_scan_status(
    scene_id: Annotated[str, Query(description='场景唯一识别码')],
) -> ResponseSchemaModel:
    data = await wechat_scan_service.get_scan_status(scene_id=scene_id)
    return response_base.success(data=data)


@router.post(
    '/scan/confirm',
    summary='微信小程序端扫码授权确认',
    description='手机端扫码后，携带 scene_id 与 wx.login 的 code 提交确认，完成登录并绑定',
)
async def confirm_scan_login(
    db: CurrentSessionTransaction,
    response: Response,
    background_tasks: BackgroundTasks,
    scene_id: Annotated[str, Body(description='场景唯一识别码')],
    code: Annotated[str, Body(description='微信临时登录 code')],
    nickname: Annotated[str | None, Body(description='用户昵称')] = None,
    avatar: Annotated[str | None, Body(description='用户头像')] = None,
) -> ResponseSchemaModel:
    await wechat_scan_service.confirm_scan(
        db=db,
        response=response,
        background_tasks=background_tasks,
        scene_id=scene_id,
        code=code,
        nickname=nickname,
        avatar=avatar,
    )
    return response_base.success(data={'success': True})


@router.post(
    '/scan/mock_confirm',
    summary='模拟手机扫码授权（开发与测试环境专用）',
    description='无真机环境时一键模拟手机扫码确认，直接下发测试用户凭证',
)
async def mock_confirm_scan_login(
    scene_id: Annotated[str, Body(description='场景唯一识别码')],
    username: Annotated[str | None, Body(description='指定登录的测试用户名')] = None,
) -> ResponseSchemaModel:
    data = await wechat_scan_service.mock_confirm_scan(
        scene_id=scene_id,
        username=username,
    )
    return response_base.success(data=data)

