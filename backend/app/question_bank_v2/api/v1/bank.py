from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Path, Query, Request

from backend.app.question_bank_v2.schema.bank import (
    CreateBankParam,
    CreateBankRevisionParam,
    GetBankCategoryDetail,
    GetBankDetail,
    GetBankListItem,
    GetBankRevisionDetail,
    SetBankCategoriesParam,
    UpdateBankParam,
    UpdateBankRevisionParam,
)
from backend.app.question_bank_v2.service.bank_service import bank_service
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.common.security.permission import RequestPermission
from backend.common.security.rbac import DependsRBAC
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()

BankKindQuery = Literal['practice', 'paper', 'mock']


@router.get('', summary='获取公开题库列表', name='qbank_v2_get_banks')
async def get_banks(
    db: CurrentSession,
    *,
    category_id: Annotated[int | None, Query(gt=0, description='业务分类 ID')] = None,
    include_descendants: Annotated[bool, Query(description='是否包含子孙分类')] = True,
    bank_kind: Annotated[BankKindQuery | None, Query(description='题库用途类型')] = None,
    keyword: Annotated[str | None, Query(max_length=80, description='题库名称关键字')] = None,
    offset: Annotated[int, Query(ge=0, description='偏移量')] = 0,
    limit: Annotated[int, Query(ge=1, le=200, description='返回数量')] = 100,
) -> ResponseSchemaModel[list[GetBankListItem]]:
    """获取当前已发布的公开题库列表"""
    data = await bank_service.get_list(
        db=db,
        category_id=category_id,
        include_descendants=include_descendants,
        bank_kind=bank_kind,
        keyword=keyword,
        offset=offset,
        limit=limit,
    )
    return response_base.success(data=data)


@router.get('/{pk}', summary='获取公开题库详情', name='qbank_v2_get_bank')
async def get_bank(
    db: CurrentSession,
    pk: Annotated[int, Path(gt=0, description='题库 ID')],
) -> ResponseSchemaModel[GetBankDetail]:
    """获取当前已发布的公开题库详情"""
    data = await bank_service.get(db=db, pk=pk)
    return response_base.success(data=data)


@router.post(
    '',
    summary='创建题库及首个草稿版本',
    name='qbank_v2_create_bank',
    dependencies=[DependsJwtAuth, Depends(RequestPermission('question_bank:bank:create')), DependsRBAC],
)
async def create_bank(
    request: Request,
    db: CurrentSessionTransaction,
    obj: CreateBankParam,
) -> ResponseSchemaModel[GetBankDetail]:
    """创建题库稳定身份和首个草稿版本"""
    data = await bank_service.create(db=db, obj=obj, created_by=request.user.id)
    return response_base.success(data=data)


@router.put(
    '/{pk}',
    summary='更新题库稳定身份',
    name='qbank_v2_update_bank',
    dependencies=[DependsJwtAuth, Depends(RequestPermission('question_bank:bank:update')), DependsRBAC],
)
async def update_bank(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(gt=0, description='题库 ID')],
    obj: UpdateBankParam,
) -> ResponseSchemaModel[GetBankDetail]:
    """仅更新题库编码、可见性和身份状态"""
    data = await bank_service.update(db=db, pk=pk, obj=obj, updated_by=request.user.id)
    return response_base.success(data=data)


@router.put(
    '/{pk}/categories',
    summary='设置题库业务分类',
    name='qbank_v2_set_bank_categories',
    dependencies=[DependsJwtAuth, Depends(RequestPermission('question_bank:bank:update')), DependsRBAC],
)
async def set_bank_categories(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(gt=0, description='题库 ID')],
    obj: SetBankCategoriesParam,
) -> ResponseSchemaModel[list[GetBankCategoryDetail]]:
    """原子替换题库的多分类关联和主分类"""
    data = await bank_service.set_categories(db=db, bank_id=pk, obj=obj, updated_by=request.user.id)
    return response_base.success(data=data)


@router.get(
    '/{pk}/revisions',
    summary='获取题库版本列表',
    name='qbank_v2_get_bank_revisions',
    dependencies=[DependsJwtAuth, Depends(RequestPermission('question_bank:bank:update')), DependsRBAC],
)
async def get_bank_revisions(
    db: CurrentSession,
    pk: Annotated[int, Path(gt=0, description='题库 ID')],
) -> ResponseSchemaModel[list[GetBankRevisionDetail]]:
    """按版本号倒序获取题库全部版本"""
    data = await bank_service.get_revisions(db=db, bank_id=pk)
    return response_base.success(data=data)


@router.post(
    '/{pk}/revisions',
    summary='创建题库草稿版本',
    name='qbank_v2_create_bank_revision',
    dependencies=[DependsJwtAuth, Depends(RequestPermission('question_bank:bank:update')), DependsRBAC],
)
async def create_bank_revision(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(gt=0, description='题库 ID')],
    obj: CreateBankRevisionParam,
) -> ResponseSchemaModel[GetBankRevisionDetail]:
    """为题库创建下一个递增版本号的草稿"""
    data = await bank_service.create_revision(db=db, bank_id=pk, obj=obj, created_by=request.user.id)
    return response_base.success(data=data)


@router.put(
    '/{pk}/revisions/{revision_id}',
    summary='更新题库草稿版本',
    name='qbank_v2_update_bank_revision',
    dependencies=[DependsJwtAuth, Depends(RequestPermission('question_bank:bank:update')), DependsRBAC],
)
async def update_bank_revision(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(gt=0, description='题库 ID')],
    revision_id: Annotated[int, Path(gt=0, description='题库版本 ID')],
    obj: UpdateBankRevisionParam,
) -> ResponseSchemaModel[GetBankRevisionDetail]:
    """仅草稿版本允许更新"""
    data = await bank_service.update_revision(
        db=db,
        bank_id=pk,
        revision_id=revision_id,
        obj=obj,
        updated_by=request.user.id,
    )
    return response_base.success(data=data)


@router.post(
    '/{pk}/revisions/{revision_id}/publish',
    summary='发布题库版本',
    name='qbank_v2_publish_bank_revision',
    dependencies=[DependsJwtAuth, Depends(RequestPermission('question_bank:bank:update')), DependsRBAC],
)
async def publish_bank_revision(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(gt=0, description='题库 ID')],
    revision_id: Annotated[int, Path(gt=0, description='题库版本 ID')],
) -> ResponseSchemaModel[GetBankRevisionDetail]:
    """固化题量、总分和内容哈希后原子切换当前发布版本"""
    data = await bank_service.publish_revision(
        db=db,
        bank_id=pk,
        revision_id=revision_id,
        published_by=request.user.id,
    )
    return response_base.success(data=data)
