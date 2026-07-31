from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, Path, Query, Request, UploadFile

from backend.app.question_bank_v2.schema.bank import (
    CreateBankParam,
    CreateBankRevisionParam,
    GetAdminBankListItem,
    GetBankCategoryDetail,
    GetBankDetail,
    GetBankListItem,
    GetBankRevisionDetail,
    SetBankCategoriesParam,
    UpdateBankParam,
    UpdateBankRevisionParam,
)
from backend.app.question_bank_v2.schema.import_task import BankImportResult
from backend.app.question_bank_v2.service.bank_service import bank_service
from backend.app.question_bank_v2.service.import_task_service import import_task_service
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

router = APIRouter()

BankKindQuery = Literal['practice', 'paper', 'mock']


@router.get(
    '/admin',
    summary='获取管理端题库列表',
    name='qbank_v2_get_admin_banks',
    dependencies=[
        DependsJwtAuth,
        Depends(RequestPermission('question_bank:bank:update')),
        DependsRBAC,
        DependsPagination,
    ],
)
async def get_admin_banks(
    db: CurrentSession,
    *,
    bank_kind: Annotated[BankKindQuery | None, Query(description='题库用途类型')] = None,
    keyword: Annotated[str | None, Query(max_length=80, description='题库名称、编码或 ID')] = None,
) -> ResponseSchemaModel[PageData[GetAdminBankListItem]]:
    stmt = bank_service.get_admin_select(bank_kind=bank_kind, keyword=keyword)
    return response_base.success(data=await paging_data(db, stmt, GetAdminBankListItem))


@router.get(
    '',
    summary='获取公开题库列表',
    name='qbank_v2_get_banks',
    dependencies=[DependsPagination],
)
async def get_banks(
    db: CurrentSession,
    *,
    category_id: Annotated[int | None, Query(gt=0, description='业务分类 ID')] = None,
    include_descendants: Annotated[bool, Query(description='是否包含子孙分类')] = True,
    bank_kind: Annotated[BankKindQuery | None, Query(description='题库用途类型')] = None,
    keyword: Annotated[str | None, Query(max_length=80, description='题库名称关键字')] = None,
) -> ResponseSchemaModel[PageData[GetBankListItem]]:
    """获取当前已发布的公开题库列表（分页）"""
    stmt = await bank_service.get_select(
        db=db,
        category_id=category_id,
        include_descendants=include_descendants,
        bank_kind=bank_kind,
        keyword=keyword,
    )
    page_data = await paging_data(db, stmt, GetBankListItem)
    return response_base.success(data=page_data)


@router.get('/{pk}', summary='获取公开题库详情', name='qbank_v2_get_bank')
async def get_bank(
    request: Request,
    db: CurrentSession,
    pk: Annotated[int, Path(gt=0, description='题库 ID')],
) -> ResponseSchemaModel[GetBankDetail]:
    """
    获取当前已发布的公开题库详情

    匿名可访问；携带有效凭证时额外返回该账号的刷题准入结果。
    """
    data = await bank_service.get(db=db, pk=pk, user_id=getattr(request.user, 'id', None))
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
    dependencies=[
        DependsJwtAuth,
        Depends(RequestPermission('question_bank:bank:update')),
        DependsRBAC,
    ],
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
    dependencies=[
        DependsJwtAuth,
        Depends(RequestPermission('question_bank:bank:update')),
        DependsRBAC,
    ],
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
    dependencies=[
        DependsJwtAuth,
        Depends(RequestPermission('question_bank:bank:update')),
        DependsRBAC,
        DependsCursorPagination,
    ],
)
async def get_bank_revisions(
    db: CurrentSession,
    pk: Annotated[int, Path(gt=0, description='题库 ID')],
) -> ResponseSchemaModel[CursorPageData[GetBankRevisionDetail]]:
    """按版本号倒序游标分页获取题库版本"""
    stmt = await bank_service.get_revisions_select(db=db, bank_id=pk)
    return response_base.success(data=await cursor_paging_data(db, stmt, GetBankRevisionDetail))


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


@router.get(
    '/import/template',
    summary='下载题库导入模板',
    name='qbank_v2_get_import_template',
)
async def get_import_template() -> ResponseSchemaModel[None]:
    """下载 XLSX 格式的导入模板"""
    content = await import_task_service.build_import_template()
    from fastapi.responses import Response
    return Response(
        content=content,
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={'Content-Disposition': 'attachment; filename="question_import_template.xlsx"'},
    )


@router.post(
    '/import',
    summary='从 XLSX 导入题目并创建题库',
    name='qbank_v2_import_bank',
    dependencies=[DependsJwtAuth, Depends(RequestPermission('question_bank:bank:create')), DependsRBAC],
)
async def import_bank(
    request: Request,
    db: CurrentSessionTransaction,
    file: Annotated[UploadFile, File(description='XLSX 文件')],
    bank_name: Annotated[str, Form(min_length=1, max_length=160, description='题库名称')],
    bank_code: Annotated[str | None, Form(max_length=64, description='题库编码（可选，自动生成）')] = None,
    bank_kind: Annotated[str, Form(description='题库类型')] = 'practice',
    collection_id: Annotated[int | None, Form(gt=0, description='挂载合集 ID')] = None,
    category_ids: Annotated[str | None, Form(description='分类 ID 列表，逗号分隔')] = None,
    primary_category_id: Annotated[int | None, Form(gt=0, description='主分类 ID')] = None,
    description: Annotated[str | None, Form(max_length=500, description='题库描述')] = None,
) -> ResponseSchemaModel[BankImportResult]:
    """上传 XLSX 文件，自动创建题库、导入题目、发布版本、挂载合集并设置分类。"""
    content = await file.read(20 * 1024 * 1024 + 1)
    if len(content) > 20 * 1024 * 1024:
        from backend.common.exception import errors as exc
        raise exc.RequestError(msg='导入文件不能超过 20 MiB')
    if not content:
        from backend.common.exception import errors as exc
        raise exc.RequestError(msg='上传文件为空')

    parsed_category_ids: list[int] = []
    if category_ids:
        parsed_category_ids = [int(c.strip()) for c in category_ids.split(',') if c.strip()]
        if len(set(parsed_category_ids)) > 20:
            from backend.common.exception import errors as exc
            raise exc.RequestError(msg='题库分类最多 20 个')

    data = await import_task_service.import_bank(
        db=db,
        user_id=request.user.id,
        file_content=content,
        bank_name=bank_name,
        bank_code=bank_code,
        bank_kind=bank_kind,
        collection_id=collection_id,
        category_ids=parsed_category_ids or None,
        primary_category_id=primary_category_id,
        description=description,
    )
    return response_base.success(data=data)
