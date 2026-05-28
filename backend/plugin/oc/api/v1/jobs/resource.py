from fastapi import APIRouter

from backend.plugin.oc.schema.resource import GetResourceDetail
from backend.plugin.oc.service.resource_service import ResourceService
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.database.db import CurrentSession

router = APIRouter()


@router.get(
    '',
    summary='获取所有资料包',
    description='获取所有笔试面试资料包列表',
)
async def get_all_resources(db: CurrentSession) -> ResponseSchemaModel[list[GetResourceDetail]]:
    """获取所有资料包"""
    resources = await ResourceService.get_all(db)
    data = [GetResourceDetail.model_validate(resource) for resource in resources]
    return response_base.success(data=data)


@router.get(
    '/{pk}',
    summary='获取资料包详情',
    description='根据ID获取单个资料包详情',
)
async def get_resource(pk: int, db: CurrentSession) -> ResponseSchemaModel[GetResourceDetail]:
    """获取资料包详情"""
    resource = await ResourceService.get(db, pk)
    data = GetResourceDetail.model_validate(resource)
    return response_base.success(data=data)
