from typing import Annotated

from fastapi import APIRouter, Body, Depends, Path, Query, Request

from backend.app.question_bank_v2.schema.material import (
    CreateMaterialAnchorParam,
    CreateMaterialParam,
    CreateMaterialRevisionParam,
    GetMaterialAnchorDetail,
    GetMaterialDetail,
    GetMaterialListItem,
    GetMaterialRevisionDetail,
    MaterialRevisionStatus,
    MaterialStatus,
    UpdateMaterialAnchorParam,
    UpdateMaterialParam,
    UpdateMaterialRevisionParam,
)
from backend.app.question_bank_v2.service.material_service import material_service
from backend.common.pagination import (
    CursorPageData,
    DependsCursorPagination,
    DependsPagination,
    PageData,
    cursor_paging_data,
    paging_data,
)
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.common.security.permission import RequestPermission
from backend.common.security.rbac import DependsRBAC
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter(dependencies=[DependsJwtAuth, Depends(RequestPermission('question_bank:bank:update')), DependsRBAC])


@router.get(
    '',
    summary='获取材料管理列表',
    name='qbank_v2_get_materials',
    dependencies=[DependsPagination],
)
async def get_materials(
    db: CurrentSession,
    *,
    status: Annotated[MaterialStatus | None, Query(description='材料身份状态')] = None,
    revision_status: Annotated[MaterialRevisionStatus | None, Query(description='最近版本状态')] = None,
    keyword: Annotated[str | None, Query(max_length=200, description='编码或标题关键字')] = None,
) -> ResponseSchemaModel[PageData[GetMaterialListItem]]:
    """按每份材料最近版本查询管理列表（分页）"""
    stmt = material_service.get_list_select(
        status=status,
        revision_status=revision_status,
        keyword=keyword,
    )
    page_data = await paging_data(db, stmt, GetMaterialListItem)
    return response_base.success(data=page_data)


@router.get(
    '/{pk}/revisions/{revision_id}/anchors',
    summary='获取材料版本锚点',
    name='qbank_v2_get_material_anchors',
    dependencies=[DependsCursorPagination],
)
async def get_material_anchors(
    db: CurrentSession,
    pk: Annotated[int, Path(gt=0, description='材料 ID')],
    revision_id: Annotated[int, Path(gt=0, description='材料版本 ID')],
) -> ResponseSchemaModel[CursorPageData[GetMaterialAnchorDetail]]:
    stmt = await material_service.get_anchors_select(db=db, material_id=pk, revision_id=revision_id)
    return response_base.success(data=await cursor_paging_data(db, stmt, GetMaterialAnchorDetail))


@router.post(
    '/{pk}/revisions/{revision_id}/anchors',
    summary='创建材料版本锚点（支持批量）',
    name='qbank_v2_create_material_anchor',
)
async def create_material_anchor(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(gt=0, description='材料 ID')],
    revision_id: Annotated[int, Path(gt=0, description='材料版本 ID')],
    items: Annotated[list[CreateMaterialAnchorParam], Body(min_length=1, max_length=500)],
) -> ResponseSchemaModel[list[GetMaterialAnchorDetail]]:
    """请求体为锚点参数数组，单个数组元素表示创建一个锚点。"""
    data = await material_service.create_anchors(
        db=db,
        material_id=pk,
        revision_id=revision_id,
        obj_list=items,
        user_id=request.user.id,
    )
    return response_base.success(data=data)


@router.put(
    '/{pk}/revisions/{revision_id}/anchors/{anchor_id}',
    summary='更新材料版本锚点',
    name='qbank_v2_update_material_anchor',
)
async def update_material_anchor(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(gt=0, description='材料 ID')],
    revision_id: Annotated[int, Path(gt=0, description='材料版本 ID')],
    anchor_id: Annotated[int, Path(gt=0, description='材料锚点 ID')],
    obj: UpdateMaterialAnchorParam,
) -> ResponseSchemaModel[GetMaterialAnchorDetail]:
    data = await material_service.update_anchor(
        db=db,
        material_id=pk,
        revision_id=revision_id,
        anchor_id=anchor_id,
        obj=obj,
        user_id=request.user.id,
    )
    return response_base.success(data=data)


@router.delete(
    '/{pk}/revisions/{revision_id}/anchors/{anchor_id}',
    summary='删除材料版本锚点',
    name='qbank_v2_delete_material_anchor',
)
async def delete_material_anchor(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(gt=0, description='材料 ID')],
    revision_id: Annotated[int, Path(gt=0, description='材料版本 ID')],
    anchor_id: Annotated[int, Path(gt=0, description='材料锚点 ID')],
) -> ResponseSchemaModel[None]:
    await material_service.delete_anchor(
        db=db,
        material_id=pk,
        revision_id=revision_id,
        anchor_id=anchor_id,
    )
    return response_base.success()


@router.get(
    '/{pk}/revisions/{revision_id}/blocks',
    summary='解析材料版本内容分块',
    name='qbank_v2_get_material_blocks',
)
async def get_material_blocks(
    db: CurrentSession,
    pk: Annotated[int, Path(gt=0, description='材料 ID')],
    revision_id: Annotated[int, Path(gt=0, description='材料版本 ID')],
) -> ResponseSchemaModel[dict]:
    """解析材料 HTML 内容为文本块和图片块，用于前端锚点标注交互"""
    data = await material_service.get_blocks(db=db, material_id=pk, revision_id=revision_id)
    return response_base.success(data=data)


@router.get(
    '/{pk}/questions',
    summary='获取材料关联题目',
    name='qbank_v2_get_material_questions',
    dependencies=[DependsCursorPagination],
)
async def get_material_questions(
    db: CurrentSession,
    pk: Annotated[int, Path(gt=0, description='材料 ID')],
) -> ResponseSchemaModel[CursorPageData[dict]]:
    """获取关联指定材料的所有题目（含题干预览）"""
    stmt = await material_service.get_question_previews_select(db=db, material_id=pk)
    return response_base.success(
        data=await cursor_paging_data(db, stmt, item_transform=material_service.build_mapping_page)
    )


@router.get('/{pk}', summary='获取材料管理详情', name='qbank_v2_get_material')
async def get_material(
    db: CurrentSession,
    pk: Annotated[int, Path(gt=0, description='材料 ID')],
    revision_id: Annotated[int | None, Query(gt=0, description='指定材料版本 ID')] = None,
) -> ResponseSchemaModel[GetMaterialDetail]:
    """获取材料最近版本或指定版本详情"""
    data = await material_service.get(db=db, pk=pk, revision_id=revision_id)
    return response_base.success(data=data)


@router.post('', summary='创建材料及首个草稿版本', name='qbank_v2_create_material')
async def create_material(
    request: Request,
    db: CurrentSessionTransaction,
    obj: CreateMaterialParam,
) -> ResponseSchemaModel[GetMaterialDetail]:
    """创建材料稳定身份和首个草稿内容"""
    data = await material_service.create(db=db, obj=obj, created_by=request.user.id)
    return response_base.success(data=data)


@router.put('/{pk}', summary='更新材料稳定身份', name='qbank_v2_update_material')
async def update_material(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(gt=0, description='材料 ID')],
    obj: UpdateMaterialParam,
) -> ResponseSchemaModel[GetMaterialDetail]:
    """仅更新材料编码和身份状态"""
    data = await material_service.update(db=db, pk=pk, obj=obj, updated_by=request.user.id)
    return response_base.success(data=data)


@router.get(
    '/{pk}/revisions',
    summary='获取材料版本列表',
    name='qbank_v2_get_material_revisions',
    dependencies=[DependsCursorPagination],
)
async def get_material_revisions(
    db: CurrentSession,
    pk: Annotated[int, Path(gt=0, description='材料 ID')],
) -> ResponseSchemaModel[CursorPageData[GetMaterialRevisionDetail]]:
    """按版本号倒序游标分页获取材料版本"""
    stmt = await material_service.get_revisions_select(db=db, material_id=pk)
    return response_base.success(data=await cursor_paging_data(db, stmt, GetMaterialRevisionDetail))


@router.post('/{pk}/revisions', summary='创建材料草稿版本', name='qbank_v2_create_material_revision')
async def create_material_revision(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(gt=0, description='材料 ID')],
    obj: CreateMaterialRevisionParam,
) -> ResponseSchemaModel[GetMaterialRevisionDetail]:
    """创建下一个递增版本号的材料草稿"""
    data = await material_service.create_revision(db=db, material_id=pk, obj=obj, created_by=request.user.id)
    return response_base.success(data=data)


@router.put(
    '/{pk}/revisions/{revision_id}',
    summary='更新材料草稿版本',
    name='qbank_v2_update_material_revision',
)
async def update_material_revision(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(gt=0, description='材料 ID')],
    revision_id: Annotated[int, Path(gt=0, description='材料版本 ID')],
    obj: UpdateMaterialRevisionParam,
) -> ResponseSchemaModel[GetMaterialRevisionDetail]:
    """仅允许修改尚未发布的材料版本"""
    data = await material_service.update_revision(
        db=db,
        material_id=pk,
        revision_id=revision_id,
        obj=obj,
        updated_by=request.user.id,
    )
    return response_base.success(data=data)


@router.post(
    '/{pk}/revisions/{revision_id}/publish',
    summary='发布材料版本',
    name='qbank_v2_publish_material_revision',
)
async def publish_material_revision(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(gt=0, description='材料 ID')],
    revision_id: Annotated[int, Path(gt=0, description='材料版本 ID')],
) -> ResponseSchemaModel[GetMaterialRevisionDetail]:
    """固化材料内容哈希并切换当前发布版本"""
    data = await material_service.publish_revision(
        db=db,
        material_id=pk,
        revision_id=revision_id,
        published_by=request.user.id,
    )
    return response_base.success(data=data)
