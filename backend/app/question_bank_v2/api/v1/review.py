from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Path, Query, Request, UploadFile
from pydantic import AwareDatetime

from backend.app.question_bank_v2.schema.review import (
    BatchImportResult,
    BatchUndoResult,
    CreateExternalWrongQuestionParam,
    CreateQuestionReviewParam,
    CreateReviewTagParam,
    GetDueWrongQuestionResult,
    GetExternalQuestionAssetUploadResult,
    GetQuestionReviewDetail,
    GetReviewTagDetail,
    GetWrongQuestionDetail,
    GetWrongQuestionListItem,
    GetWrongQuestionOutlineItem,
    GetWrongQuestionSummaryItem,
    GetWrongReviewDashboard,
    GetWrongSectionFacetsResult,
    ImportBatchPage,
    ImportSinglePage,
    MasteryState,
    RecognizeExternalWrongQuestionParam,
    RecognizeExternalWrongQuestionResult,
    SubmitQuestionReviewResult,
    UpdateWrongStateParam,
    WrongBrowseMode,
    WrongCollectionPage,
    WrongEntryScope,
    WrongQuestionFilters,
    WrongQuestionListQuery,
    WrongQuestionStatistics,
)
from backend.app.question_bank_v2.service.external_asset_service import external_asset_service
from backend.app.question_bank_v2.service.wrong_review_service import wrong_review_service
from backend.common.pagination import CursorPageData, DependsCursorPagination, cursor_paging_data
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter(dependencies=[DependsJwtAuth])

# 注意：以下字面量路由必须全部注册在 /{wrong_state_id} 之前，否则会被当成路径参数解析成 422


@router.post('/assets', summary='上传用户错题图片资产', name='qbank_v2_upload_external_wrong_asset')
async def upload_external_wrong_asset(
    request: Request,
    db: CurrentSessionTransaction,
    file: Annotated[UploadFile, File(description='错题图片')],
) -> ResponseSchemaModel[GetExternalQuestionAssetUploadResult]:
    """上传图片并同时登记 V2 资产元数据和物理位置"""
    data = await external_asset_service.upload_image(db=db, user_id=request.user.id, file=file)
    return response_base.success(data=data)


@router.post('/recognize', summary='识别用户错题图片', name='qbank_v2_recognize_external_wrong_question')
async def recognize_external_wrong_question(
    db: CurrentSession,
    obj: RecognizeExternalWrongQuestionParam,
) -> ResponseSchemaModel[RecognizeExternalWrongQuestionResult]:
    """复用视觉识别能力生成可编辑草稿，不在识别阶段写题目数据"""
    data = await external_asset_service.recognize(db=db, obj=obj)
    return response_base.success(data=data)


@router.get('/tags', summary='获取复盘标签', name='qbank_v2_get_review_tags')
async def get_review_tags(
    request: Request,
    db: CurrentSession,
) -> ResponseSchemaModel[list[GetReviewTagDetail]]:
    """返回系统标签和当前用户自定义标签"""
    data = await wrong_review_service.get_tags(db=db, user_id=request.user.id)
    return response_base.success(data=data)


@router.post('/tags', summary='创建复盘标签', name='qbank_v2_create_review_tag')
async def create_review_tag(
    request: Request,
    db: CurrentSessionTransaction,
    obj: CreateReviewTagParam,
) -> ResponseSchemaModel[GetReviewTagDetail]:
    """创建仅当前用户可见的错因、方法或其他标签"""
    data = await wrong_review_service.create_tag(db=db, user_id=request.user.id, obj=obj)
    return response_base.success(data=data)


@router.get(
    '',
    summary='获取我的错题列表',
    name='qbank_v2_get_wrong_questions',
    dependencies=[DependsCursorPagination],
)
async def get_wrong_questions(
    request: Request,
    db: CurrentSession,
    query: Annotated[WrongQuestionListQuery, Depends()],
) -> ResponseSchemaModel[
    CursorPageData[GetWrongQuestionListItem | GetWrongQuestionSummaryItem | GetWrongQuestionOutlineItem]
]:
    """默认兼容原列表；摘要和答题卡共用筛选及游标，但只返回各自需要的字段。"""
    data = await wrong_review_service.get_list_page(db=db, user_id=request.user.id, query=query)
    return response_base.success(data=data)


@router.get('/statistics', summary='获取错题统计', name='qbank_v2_get_wrong_question_statistics')
async def get_wrong_question_statistics(
    request: Request,
    db: CurrentSession,
    group_by: Annotated[Literal['bank', 'knowledge_point'], Query(description='分组方式')] = 'bank',
    knowledge_system_id: Annotated[
        int | None, Query(gt=0, description='知识体系 ID；空则按偏好回落 default，仅知识点分组生效')
    ] = None,
    domain_category_id: Annotated[int | None, Query(gt=0, description='领域分类 ID；不传取用户当前领域')] = None,
) -> ResponseSchemaModel[WrongQuestionStatistics]:
    """获取错题总数、到期数、复盘数及题库或知识点分组"""
    data = await wrong_review_service.get_statistics(
        db=db,
        user_id=request.user.id,
        group_by=group_by,
        knowledge_system_id=knowledge_system_id,
        domain_category_id=domain_category_id,
    )
    return response_base.success(data=data)


@router.get('/due', summary='获取到期重练错题', name='qbank_v2_get_due_wrong_questions')
async def get_due_wrong_questions(
    request: Request,
    db: CurrentSession,
    limit: Annotated[int | None, Query(ge=1, le=200, description='本次返回题数；空表示取用户偏好上限')] = None,
) -> ResponseSchemaModel[GetDueWrongQuestionResult]:
    """按重练阶梯的下次时间返回当前用户已到期的活跃错题"""
    data = await wrong_review_service.get_due(db=db, user_id=request.user.id, limit=limit)
    return response_base.success(data=data)


@router.get(
    '/reviewed',
    summary='获取复盘档案',
    name='qbank_v2_get_reviewed_wrong_questions',
    dependencies=[DependsCursorPagination],
)
async def get_reviewed_wrong_questions(
    request: Request,
    db: CurrentSession,
    mastery_state: Annotated[MasteryState | None, Query(description='掌握状态筛选')] = None,
    tag_id: Annotated[int | None, Query(gt=0, description='错因标签筛选')] = None,
    knowledge_point_id: Annotated[int | None, Query(gt=0, description='知识点筛选')] = None,
    keyword: Annotated[str | None, Query(max_length=100, description='题干关键词搜索')] = None,
    domain_category_id: Annotated[int | None, Query(gt=0, description='领域分类 ID；不传取用户当前领域')] = None,
) -> ResponseSchemaModel[CursorPageData[GetWrongQuestionListItem]]:
    """考前回顾入口；不过滤错题本状态，已移出的题仍可查看"""
    domain_category_ids = await wrong_review_service.resolve_domain_scope(
        db=db,
        user_id=request.user.id,
        domain_category_id=domain_category_id,
    )
    stmt = wrong_review_service.get_reviewed_select(
        user_id=request.user.id,
        mastery_state=mastery_state,
        tag_id=tag_id,
        knowledge_point_id=knowledge_point_id,
        keyword=keyword,
        domain_category_ids=domain_category_ids,
    )
    return response_base.success(data=await cursor_paging_data(db, stmt, GetWrongQuestionListItem))


@router.get(
    '/pending-review',
    summary='获取待复盘队列',
    name='qbank_v2_get_pending_review_wrong_questions',
    dependencies=[DependsCursorPagination],
)
async def get_pending_review_wrong_questions(
    request: Request,
    db: CurrentSession,
    entry_scope: Annotated[WrongEntryScope | None, Query(description='题库错题或自主录入')] = None,
    domain_category_id: Annotated[int | None, Query(gt=0, description='领域分类 ID；不传取用户当前领域')] = None,
    since: Annotated[AwareDatetime | None, Query(description='最近答错或录入时间下界（含），需带时区')] = None,
) -> ResponseSchemaModel[CursorPageData[GetWrongQuestionListItem]]:
    """仍在错题本且从未复盘，或上次复盘后又答错的题；完成本次复盘即出队"""
    domain_category_ids = await wrong_review_service.resolve_domain_scope(
        db=db,
        user_id=request.user.id,
        domain_category_id=domain_category_id,
    )
    stmt = wrong_review_service.get_pending_review_select(
        user_id=request.user.id,
        entry_scope=entry_scope,
        domain_category_ids=domain_category_ids,
        since=since,
    )
    return response_base.success(data=await cursor_paging_data(db, stmt, GetWrongQuestionListItem))


@router.get('/dashboard', summary='获取错因与知识点看板', name='qbank_v2_get_wrong_review_dashboard')
async def get_wrong_review_dashboard(
    request: Request,
    db: CurrentSession,
    knowledge_system_id: Annotated[int | None, Query(gt=0, description='知识体系 ID；空则按偏好回落 default')] = None,
    domain_category_id: Annotated[int | None, Query(gt=0, description='领域分类 ID；不传取用户当前领域')] = None,
) -> ResponseSchemaModel[GetWrongReviewDashboard]:
    """分布来自用户复盘时主观选择的标签和知识点"""
    data = await wrong_review_service.get_dashboard(
        db=db,
        user_id=request.user.id,
        knowledge_system_id=knowledge_system_id,
        domain_category_id=domain_category_id,
    )
    return response_base.success(data=data)


@router.post('/external', summary='录入外部错题（单条或批量数组）', name='qbank_v2_capture_external_wrong_question')
async def capture_external_wrong_question(
    request: Request,
    db: CurrentSessionTransaction,
    obj: CreateExternalWrongQuestionParam | list[CreateExternalWrongQuestionParam],
) -> ResponseSchemaModel[GetWrongQuestionDetail] | ResponseSchemaModel[BatchImportResult]:
    """将手工、OCR 或导入题统一创建为可重练的用户私有题目

    请求体既可以是单个对象（兼容小程序现有调用），也可以是对象数组：
    数组形态下逐条独立成败，单条失败不影响其余题目入库，并回传批次 ID 便于整批撤销。
    """
    if isinstance(obj, list):
        # 分片提交时客户端用请求头带上同一个批次 ID，保证多片共享同一批次便于整批撤销
        header_batch = (request.headers.get('x-import-batch-id') or '').strip()
        batch_id = header_batch if 8 <= len(header_batch) <= 64 else None
        data = await wrong_review_service.capture_external_batch(
            db=db,
            user_id=request.user.id,
            items=obj,
            import_batch_id=batch_id,
        )
    else:
        data = await wrong_review_service.capture_external(db=db, user_id=request.user.id, obj=obj)
    return response_base.success(data=data)


@router.get(
    '/collections',
    summary='错题集合列表（题库/导入批次/散题）',
    name='qbank_v2_get_wrong_collections',
)
async def get_wrong_collections(
    request: Request,
    db: CurrentSession,
    mode: Annotated[WrongBrowseMode, Query(description='浏览状态：待复盘、已复盘或已掌握')] = 'pending',
    domain_category_id: Annotated[int | None, Query(gt=0, description='领域分类 ID；不传取用户当前领域')] = None,
    since: Annotated[AwareDatetime | None, Query(description='最近答错或录入时间下界（含），需带时区')] = None,
    cursor: Annotated[str | None, Query(description='上一页返回的 next_cursor')] = None,
    size: Annotated[int, Query(ge=1, le=100, description='每页数量')] = 20,
) -> ResponseSchemaModel[WrongCollectionPage]:
    """把错题按「集合」聚合：题库来源按题库、自己导入的按批次、无批次的归散题"""
    data = await wrong_review_service.get_collections_page(
        db=db,
        user_id=request.user.id,
        mode=mode,
        domain_category_id=domain_category_id,
        since=since,
        cursor=cursor,
        size=size,
    )
    return response_base.success(data=data)


@router.get(
    '/sections',
    summary='获取错题章节及题量（支持跨集合）',
    name='qbank_v2_get_wrong_question_sections',
)
async def get_wrong_question_sections(
    request: Request,
    db: CurrentSession,
    filters: Annotated[WrongQuestionFilters, Depends()],
) -> ResponseSchemaModel[GetWrongSectionFacetsResult]:
    """返回当前状态和领域的章节题量；不传集合参数时跨集合汇总同名章节"""
    data = await wrong_review_service.get_sections(
        db=db,
        user_id=request.user.id,
        filters=filters,
    )
    return response_base.success(data=data)


@router.get(
    '/import-history/batches',
    summary='导入记录：批量导入批次（游标分页）',
    name='qbank_v2_get_wrong_import_batches',
)
async def get_wrong_import_batches(
    request: Request,
    db: CurrentSession,
    cursor: Annotated[str | None, Query(description='上一页返回的 next_cursor')] = None,
    size: Annotated[int, Query(ge=1, le=100, description='每页数量')] = 20,
) -> ResponseSchemaModel[ImportBatchPage]:
    """按批次聚合的导入记录，游标为批次内最大状态 ID"""
    data = await wrong_review_service.get_import_batches_page(
        db=db,
        user_id=request.user.id,
        cursor=cursor,
        size=size,
    )
    return response_base.success(data=data)


@router.get(
    '/import-history/singles',
    summary='导入记录：散题（游标分页）',
    name='qbank_v2_get_wrong_import_singles',
)
async def get_wrong_import_singles(
    request: Request,
    db: CurrentSession,
    cursor: Annotated[str | None, Query(description='上一页返回的 next_cursor')] = None,
    size: Annotated[int, Query(ge=1, le=100, description='每页数量')] = 20,
) -> ResponseSchemaModel[ImportSinglePage]:
    """无批次的外部录入错题，游标为错题状态 ID"""
    data = await wrong_review_service.get_import_singles_page(
        db=db,
        user_id=request.user.id,
        cursor=cursor,
        size=size,
    )
    return response_base.success(data=data)


@router.delete(
    '/import-batches/{import_batch_id}',
    summary='撤销一次错题导入批次',
    name='qbank_v2_undo_import_batch',
)
async def undo_import_wrong_question_batch(
    request: Request,
    db: CurrentSessionTransaction,
    import_batch_id: Annotated[str, Path(min_length=8, max_length=64, description='导入批次 ID')],
) -> ResponseSchemaModel[BatchUndoResult]:
    """按批次撤销扩展导入的错题：软删该批次的错题状态、私有题目与复盘事件"""
    data = await wrong_review_service.undo_import_batch(
        db=db,
        user_id=request.user.id,
        import_batch_id=import_batch_id,
    )
    return response_base.success(data=data)


@router.get(
    '/reviews/{review_id}',
    summary='获取错题复盘详情',
    name='qbank_v2_get_wrong_question_review',
)
async def get_wrong_question_review(
    request: Request,
    db: CurrentSession,
    review_id: Annotated[int, Path(gt=0, description='复盘事件 ID')],
) -> ResponseSchemaModel[GetQuestionReviewDetail]:
    """读取复盘快照、标签和知识点"""
    data = await wrong_review_service.get_review(
        db=db,
        user_id=request.user.id,
        review_id=review_id,
    )
    return response_base.success(data=data)


@router.get('/{wrong_state_id}', summary='获取错题详情', name='qbank_v2_get_wrong_question')
async def get_wrong_question(
    request: Request,
    db: CurrentSession,
    wrong_state_id: Annotated[int, Path(gt=0, description='错题状态 ID')],
) -> ResponseSchemaModel[GetWrongQuestionDetail]:
    """含答案解析、掌握状态和还需连对几次"""
    data = await wrong_review_service.get_detail(
        db=db,
        user_id=request.user.id,
        wrong_state_id=wrong_state_id,
    )
    return response_base.success(data=data)


@router.patch('/{wrong_state_id}', summary='调整错题本状态', name='qbank_v2_update_wrong_question_state')
async def update_wrong_question_state(
    request: Request,
    db: CurrentSessionTransaction,
    wrong_state_id: Annotated[int, Path(gt=0, description='错题状态 ID')],
    obj: UpdateWrongStateParam,
) -> ResponseSchemaModel[GetWrongQuestionListItem]:
    """手动移出、恢复、暂停或置顶；系统维护的计数与排期不接受客户端改写"""
    data = await wrong_review_service.update_state(
        db=db,
        user_id=request.user.id,
        wrong_state_id=wrong_state_id,
        obj=obj,
    )
    return response_base.success(data=data)


@router.delete('/{wrong_state_id}', summary='删除单条错题', name='qbank_v2_delete_wrong_question')
async def delete_wrong_question(
    request: Request,
    db: CurrentSessionTransaction,
    wrong_state_id: Annotated[int, Path(gt=0, description='错题状态 ID')],
) -> ResponseSchemaModel[BatchUndoResult]:
    """删除单条错题（散题撤销）：软删错题状态、私有题目与复盘事件"""
    data = await wrong_review_service.delete_external_wrong_question(
        db=db,
        user_id=request.user.id,
        wrong_state_id=wrong_state_id,
    )
    return response_base.success(data=data)


@router.get(
    '/{wrong_state_id}/events',
    summary='获取错题复盘时间线',
    name='qbank_v2_get_wrong_question_review_events',
    dependencies=[DependsCursorPagination],
)
async def get_wrong_question_review_events(
    request: Request,
    db: CurrentSession,
    wrong_state_id: Annotated[int, Path(gt=0, description='错题状态 ID')],
    event_type: Annotated[
        Literal['capture', 'review'] | None, Query(description='事件类型；不传返回完整时间线，review 只返回复盘笔记')
    ] = None,
) -> ResponseSchemaModel[CursorPageData[GetQuestionReviewDetail]]:
    """分页返回录入和复盘事件，按发生时间倒序"""
    stmt = await wrong_review_service.get_review_events_select(
        db=db,
        user_id=request.user.id,
        wrong_state_id=wrong_state_id,
        event_type=event_type,
    )
    page_data = await cursor_paging_data(
        db,
        stmt,
        item_transform=lambda reviews: wrong_review_service.build_review_page(db=db, reviews=reviews),
    )
    return response_base.success(data=page_data)


@router.post(
    '/{wrong_state_id}/reviews',
    summary='提交错题复盘',
    name='qbank_v2_submit_wrong_question_review',
)
async def submit_wrong_question_review(
    request: Request,
    db: CurrentSessionTransaction,
    wrong_state_id: Annotated[int, Path(gt=0, description='错题状态 ID')],
    obj: CreateQuestionReviewParam,
) -> ResponseSchemaModel[SubmitQuestionReviewResult]:
    """追加复盘事件；不打分、不改错题本状态，也不影响重练排期"""
    data = await wrong_review_service.submit_review(
        db=db,
        user_id=request.user.id,
        wrong_state_id=wrong_state_id,
        obj=obj,
    )
    return response_base.success(data=data)
