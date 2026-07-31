from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request

from backend.app.question_bank_v2.schema.composition import (
    CreateBankItemParam,
    CreateBankSectionParam,
    GetBankCompositionDetail,
    GetBankItemDetail,
    GetBankSectionDetail,
    UpdateBankItemParam,
    UpdateBankSectionParam,
)
from backend.app.question_bank_v2.service.composition_service import composition_service
from backend.common.pagination import CursorPageData, DependsCursorPagination, cursor_paging_data
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.common.security.permission import RequestPermission
from backend.common.security.rbac import DependsRBAC
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter(dependencies=[DependsJwtAuth])


@router.get(
    '/{bank_id}/revisions/{revision_id}/composition',
    summary='获取题库版本编排',
    name='qbank_v2_get_bank_composition',
    dependencies=[Depends(RequestPermission('question_bank:bank:update')), DependsRBAC],
)
async def get_bank_composition(
    db: CurrentSession,
    bank_id: Annotated[int, Path(gt=0, description='题库 ID')],
    revision_id: Annotated[int, Path(gt=0, description='题库版本 ID')],
) -> ResponseSchemaModel[GetBankCompositionDetail]:
    """获取轻量章节树；题目编排通过同版本的 items 接口游标分页读取"""
    data = await composition_service.get(db=db, bank_id=bank_id, revision_id=revision_id)
    return response_base.success(data=data)


@router.get(
    '/{bank_id}/revisions/{revision_id}/items',
    summary='分页获取题库版本题目编排',
    name='qbank_v2_get_bank_composition_items',
    dependencies=[
        DependsCursorPagination,
        Depends(RequestPermission('question_bank:bank:update')),
        DependsRBAC,
    ],
)
async def get_bank_composition_items(
    db: CurrentSession,
    bank_id: Annotated[int, Path(gt=0, description='题库 ID')],
    revision_id: Annotated[int, Path(gt=0, description='题库版本 ID')],
    section_id: Annotated[int | None, Query(gt=0, description='章节 ID')] = None,
) -> ResponseSchemaModel[CursorPageData[GetBankItemDetail]]:
    """按章节和题目顺序游标分页，避免一次传输完整大题库"""
    stmt = await composition_service.get_items_select(
        db=db,
        bank_id=bank_id,
        revision_id=revision_id,
        section_id=section_id,
    )
    return response_base.success(data=await cursor_paging_data(db, stmt, GetBankItemDetail))


@router.post(
    '/{bank_id}/revisions/{revision_id}/sections',
    summary='创建题库版本章节',
    name='qbank_v2_create_bank_section',
    dependencies=[Depends(RequestPermission('question_bank:bank:update')), DependsRBAC],
)
async def create_bank_section(
    request: Request,
    db: CurrentSessionTransaction,
    bank_id: Annotated[int, Path(gt=0, description='题库 ID')],
    revision_id: Annotated[int, Path(gt=0, description='题库版本 ID')],
    obj: CreateBankSectionParam,
) -> ResponseSchemaModel[GetBankSectionDetail]:
    """仅允许在题库草稿版本中创建章节"""
    data = await composition_service.create_section(
        db=db,
        bank_id=bank_id,
        revision_id=revision_id,
        obj=obj,
        created_by=request.user.id,
    )
    return response_base.success(data=data)


@router.put(
    '/{bank_id}/revisions/{revision_id}/sections/{section_id}',
    summary='更新题库版本章节',
    name='qbank_v2_update_bank_section',
    dependencies=[Depends(RequestPermission('question_bank:bank:update')), DependsRBAC],
)
async def update_bank_section(
    request: Request,
    db: CurrentSessionTransaction,
    bank_id: Annotated[int, Path(gt=0, description='题库 ID')],
    revision_id: Annotated[int, Path(gt=0, description='题库版本 ID')],
    section_id: Annotated[int, Path(gt=0, description='章节 ID')],
    obj: UpdateBankSectionParam,
) -> ResponseSchemaModel[GetBankSectionDetail]:
    """仅允许更新草稿版本章节并阻止树结构成环"""
    data = await composition_service.update_section(
        db=db,
        bank_id=bank_id,
        revision_id=revision_id,
        section_id=section_id,
        obj=obj,
        updated_by=request.user.id,
    )
    return response_base.success(data=data)


@router.post(
    '/{bank_id}/revisions/{revision_id}/items',
    summary='创建题库版本题目编排',
    name='qbank_v2_create_bank_item',
    dependencies=[Depends(RequestPermission('question_bank:bank:update')), DependsRBAC],
)
async def create_bank_item(
    request: Request,
    db: CurrentSessionTransaction,
    bank_id: Annotated[int, Path(gt=0, description='题库 ID')],
    revision_id: Annotated[int, Path(gt=0, description='题库版本 ID')],
    obj: CreateBankItemParam,
) -> ResponseSchemaModel[GetBankItemDetail]:
    """在题库草稿版本中固定一个已发布题目版本"""
    data = await composition_service.create_item(
        db=db,
        bank_id=bank_id,
        revision_id=revision_id,
        obj=obj,
        created_by=request.user.id,
    )
    return response_base.success(data=data)


@router.put(
    '/{bank_id}/revisions/{revision_id}/items/{item_id}',
    summary='更新题库版本题目编排',
    name='qbank_v2_update_bank_item',
    dependencies=[Depends(RequestPermission('question_bank:bank:update')), DependsRBAC],
)
async def update_bank_item(
    request: Request,
    db: CurrentSessionTransaction,
    bank_id: Annotated[int, Path(gt=0, description='题库 ID')],
    revision_id: Annotated[int, Path(gt=0, description='题库版本 ID')],
    item_id: Annotated[int, Path(gt=0, description='题目编排 ID')],
    obj: UpdateBankItemParam,
) -> ResponseSchemaModel[GetBankItemDetail]:
    """更新草稿题库中的题号、章节、分值和固定题目版本"""
    data = await composition_service.update_item(
        db=db,
        bank_id=bank_id,
        revision_id=revision_id,
        item_id=item_id,
        obj=obj,
        updated_by=request.user.id,
    )
    return response_base.success(data=data)


@router.delete(
    '/{bank_id}/revisions/{revision_id}/items/{item_id}',
    summary='删除题库版本题目编排',
    name='qbank_v2_delete_bank_item',
    dependencies=[Depends(RequestPermission('question_bank:bank:update')), DependsRBAC],
)
async def delete_bank_item(
    db: CurrentSessionTransaction,
    bank_id: Annotated[int, Path(gt=0, description='题库 ID')],
    revision_id: Annotated[int, Path(gt=0, description='题库版本 ID')],
    item_id: Annotated[int, Path(gt=0, description='题目编排 ID')],
) -> ResponseModel:
    """逻辑删除草稿题库版本中的题目编排"""
    await composition_service.delete_item(
        db=db,
        bank_id=bank_id,
        revision_id=revision_id,
        item_id=item_id,
    )
    return response_base.success()
