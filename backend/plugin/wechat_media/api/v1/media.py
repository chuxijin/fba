from typing import Annotated

from fastapi import APIRouter, File, Form, UploadFile

from backend.common.response.response_schema import ResponseModel, response_base
from backend.plugin.wechat_media.service.media_service import media_service

router = APIRouter()


@router.post('/test', summary='测试微信公众号素材中转配置')
async def test_wechat_media_config(
    payload: Annotated[str, Form(description='加密的 AppID/AppSecret 凭证')],
) -> ResponseModel:
    credentials = media_service.decrypt_credentials(payload)
    await media_service.get_access_token(credentials['appid'], credentials['appsecret'])
    return response_base.success(data={'configured': True})


@router.post('/upload', summary='中转上传微信公众号文章图片')
async def upload_wechat_article_image(
    file: Annotated[UploadFile, File(description='待上传的 JPG 或 PNG 图片')],
    payload: Annotated[str, Form(description='加密的 AppID/AppSecret 凭证')],
) -> ResponseModel:
    credentials = media_service.decrypt_credentials(payload)
    url = await media_service.upload_article_image(
        file, credentials['appid'], credentials['appsecret']
    )
    return response_base.success(data={'url': url})
