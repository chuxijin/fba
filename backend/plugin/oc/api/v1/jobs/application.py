from typing import Annotated

from fastapi import APIRouter, Path, Query

from backend.plugin.oc.schema.user_application import (
    CreateUserApplicationParam,
    GetUserApplicationDetail,
    UpdateUserApplicationParam,
)
from backend.plugin.oc.service.user_application_service import user_application_service
from backend.common.pagination import DependsPagination, PageData
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get('/{application_id}', summary='获取用户投递记录详情', dependencies=[DependsJwtAuth])
async def get_user_application(
    db: CurrentSession, application_id: Annotated[int, Path(description='投递记录 ID')]
) -> ResponseSchemaModel[GetUserApplicationDetail]:
    """获取用户投递记录详情"""
    data = await user_application_service.get(db=db, application_id=application_id)
    return response_base.success(data=data)


@router.get('', summary='获取用户投递记录列表', dependencies=[DependsJwtAuth, DependsPagination])
async def get_user_application_list(
    db: CurrentSession,
    user_id: Annotated[int | None, Query(description='用户 ID')] = None,
    job_type: Annotated[str | None, Query(description='岗位类型')] = None,
    application_status: Annotated[str | None, Query(description='投递状态')] = None,
) -> ResponseSchemaModel[PageData[GetUserApplicationDetail]]:
    """获取用户投递记录列表"""
    data = await user_application_service.get_list(
        db=db,
        user_id=user_id,
        job_type=job_type,
        application_status=application_status,
    )
    return response_base.success(data=data)


@router.post('', summary='创建用户投递记录', dependencies=[DependsJwtAuth])
async def create_user_application(db: CurrentSessionTransaction, obj: CreateUserApplicationParam) -> ResponseModel:
    """创建用户投递记录"""
    await user_application_service.create(db=db, obj=obj)
    return response_base.success()


@router.put('/{application_id}', summary='更新用户投递记录', dependencies=[DependsJwtAuth])
async def update_user_application(
    db: CurrentSessionTransaction,
    application_id: Annotated[int, Path(description='投递记录 ID')],
    obj: UpdateUserApplicationParam,
) -> ResponseModel:
    """更新用户投递记录"""
    count = await user_application_service.update(db=db, application_id=application_id, obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete('/{application_id}', summary='删除用户投递记录', dependencies=[DependsJwtAuth])
async def delete_user_application(
    db: CurrentSessionTransaction, application_id: Annotated[int, Path(description='投递记录 ID')]
) -> ResponseModel:
    """删除用户投递记录"""
    count = await user_application_service.delete(db=db, application_ids=[application_id])
    if count > 0:
        return response_base.success()
    return response_base.fail()
