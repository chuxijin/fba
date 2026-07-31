from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request

from backend.app.question_bank_v2.schema.catalog import (
    CreateCollectionBankMountParam,
    CreateCollectionParam,
    GetCollectionBankMountDetail,
    GetCollectionCatalogItem,
    GetCollectionDetail,
    UpdateCollectionBankMountParam,
    UpdateCollectionParam,
)
from backend.app.question_bank_v2.service.catalog_service import catalog_service
from backend.common.pagination import (
    CursorPageData,
    DependsCursorPagination,
    DependsPagination,
    PageData,
    cursor_paging_data,
    paging_data,
)
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.common.security.permission import RequestPermission
from backend.common.security.rbac import DependsRBAC
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get('/catalog', summary='获取公开题库合集目录', name='qbank_v2_get_collection_catalog')
async def get_collection_catalog(
    db: CurrentSession,
    cat_id: Annotated[int | None, Query(gt=0, description='按题库主分类过滤')] = None,
) -> ResponseSchemaModel[list[GetCollectionCatalogItem]]:
    """以两次数据库查询获取公开合集树及其题库"""
    data = await catalog_service.get_public_catalog(db=db, cat_id=cat_id)
    return response_base.success(data=data)


@router.get(
    '',
    summary='获取全部题库合集',
    name='qbank_v2_get_collections',
    dependencies=[
        DependsJwtAuth,
        Depends(RequestPermission('question_bank:bank:update')),
        DependsRBAC,
        DependsPagination,
    ],
)
async def get_collections(db: CurrentSession) -> ResponseSchemaModel[PageData[GetCollectionDetail]]:
    """获取管理端题库合集列表（分页）"""
    stmt = catalog_service.get_select()
    page_data = await paging_data(db, stmt, GetCollectionDetail)
    return response_base.success(data=page_data)


@router.get(
    '/{pk}',
    summary='获取题库合集详情',
    name='qbank_v2_get_collection',
    dependencies=[
        DependsJwtAuth,
        Depends(RequestPermission('question_bank:bank:update')),
        DependsRBAC,
    ],
)
async def get_collection(
    db: CurrentSession,
    pk: Annotated[int, Path(gt=0, description='合集 ID')],
) -> ResponseSchemaModel[GetCollectionDetail]:
    """获取管理端题库合集详情"""
    data = await catalog_service.get(db=db, pk=pk)
    return response_base.success(data=data)


@router.post(
    '',
    summary='创建题库合集',
    name='qbank_v2_create_collection',
    dependencies=[DependsJwtAuth, Depends(RequestPermission('question_bank:bank:create')), DependsRBAC],
)
async def create_collection(
    request: Request,
    db: CurrentSessionTransaction,
    obj: CreateCollectionParam,
) -> ResponseSchemaModel[GetCollectionDetail]:
    """创建与题库内容解耦的导航合集"""
    data = await catalog_service.create(db=db, obj=obj, created_by=request.user.id)
    return response_base.success(data=data)


@router.put(
    '/{pk}',
    summary='更新题库合集',
    name='qbank_v2_update_collection',
    dependencies=[DependsJwtAuth, Depends(RequestPermission('question_bank:bank:update')), DependsRBAC],
)
async def update_collection(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(gt=0, description='合集 ID')],
    obj: UpdateCollectionParam,
) -> ResponseSchemaModel[GetCollectionDetail]:
    """更新题库合集并校验树结构不成环"""
    data = await catalog_service.update(db=db, pk=pk, obj=obj, updated_by=request.user.id)
    return response_base.success(data=data)


@router.get(
    '/{pk}/banks',
    summary='获取合集题库挂载',
    name='qbank_v2_get_collection_banks',
    dependencies=[
        DependsJwtAuth,
        Depends(RequestPermission('question_bank:bank:update')),
        DependsRBAC,
        DependsCursorPagination,
    ],
)
async def get_collection_banks(
    db: CurrentSession,
    pk: Annotated[int, Path(gt=0, description='合集 ID')],
) -> ResponseSchemaModel[CursorPageData[GetCollectionBankMountDetail]]:
    """游标分页获取管理端合集题库挂载列表"""
    stmt = await catalog_service.get_mounts_select(db=db, collection_id=pk)
    return response_base.success(data=await cursor_paging_data(db, stmt, GetCollectionBankMountDetail))


@router.post(
    '/{pk}/banks',
    summary='创建合集题库挂载',
    name='qbank_v2_create_collection_bank',
    dependencies=[DependsJwtAuth, Depends(RequestPermission('question_bank:bank:update')), DependsRBAC],
)
async def create_collection_bank(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(gt=0, description='合集 ID')],
    obj: CreateCollectionBankMountParam,
) -> ResponseSchemaModel[GetCollectionBankMountDetail]:
    """将一个可复用题库挂载到合集"""
    data = await catalog_service.create_mount(db=db, collection_id=pk, obj=obj, created_by=request.user.id)
    return response_base.success(data=data)


@router.put(
    '/{pk}/banks/{mount_id}',
    summary='更新合集题库挂载',
    name='qbank_v2_update_collection_bank',
    dependencies=[DependsJwtAuth, Depends(RequestPermission('question_bank:bank:update')), DependsRBAC],
)
async def update_collection_bank(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(gt=0, description='合集 ID')],
    mount_id: Annotated[int, Path(gt=0, description='挂载 ID')],
    obj: UpdateCollectionBankMountParam,
) -> ResponseSchemaModel[GetCollectionBankMountDetail]:
    """切换跟随最新版或固定已发布版本"""
    data = await catalog_service.update_mount(
        db=db,
        collection_id=pk,
        mount_id=mount_id,
        obj=obj,
        updated_by=request.user.id,
    )
    return response_base.success(data=data)


@router.delete(
    '/{pk}/banks/{mount_id}',
    summary='删除合集题库挂载',
    name='qbank_v2_delete_collection_bank',
    dependencies=[DependsJwtAuth, Depends(RequestPermission('question_bank:bank:update')), DependsRBAC],
)
async def delete_collection_bank(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(gt=0, description='合集 ID')],
    mount_id: Annotated[int, Path(gt=0, description='挂载 ID')],
) -> ResponseModel:
    """逻辑删除合集题库挂载"""
    await catalog_service.delete_mount(db=db, collection_id=pk, mount_id=mount_id)
    return response_base.success()
