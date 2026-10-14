from fastapi import APIRouter
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool

from backend.common.response.response_schema import ResponseModel, response_base
from backend.plugin.openauth.service.distribution_service import openauth_distribution_service

router = APIRouter()


@router.get('/skill-config', summary='获取 Skill 最新版本和完整包校验信息')
async def get_openauth_skill_config() -> ResponseModel:
    return response_base.success(data=await run_in_threadpool(openauth_distribution_service.get_release))


@router.get('/skill-package', summary='下载完整 youanshang Skill')
async def download_openauth_skill_package() -> FileResponse:
    filename = await run_in_threadpool(openauth_distribution_service.get_package)
    return FileResponse(
        filename, media_type='application/zip', filename='youanshang-skill.zip', headers={'Cache-Control': 'no-store'}
    )
