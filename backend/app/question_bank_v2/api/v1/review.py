from typing import Annotated, Literal

from fastapi import APIRouter, File, Path, Query, Request, UploadFile

from backend.app.question_bank_v2.schema.review import (
    CreateExternalWrongQuestionParam,
    CreateQuestionReviewParam,
    CreateReviewTagParam,
    GetDueWrongQuestionResult,
    GetExternalQuestionAssetUploadResult,
    GetQuestionReviewDetail,
    GetReviewTagDetail,
    GetWrongQuestionDetail,
    GetWrongQuestionListItem,
    GetWrongReviewDashboard,
    MasteryState,
    RecognizeExternalWrongQuestionParam,
    RecognizeExternalWrongQuestionResult,
    SubmitQuestionReviewResult,
    UpdateWrongStateParam,
    WrongEntryScope,
    WrongEntrySource,
    WrongQuestionStatistics,
    WrongStateStatus,
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
    status: Annotated[WrongStateStatus | None, Query(description='错题状态；空表示全部')] = 'active',
    entry_source: Annotated[WrongEntrySource | None, Query(description='首次录入来源')] = None,
    entry_scope: Annotated[WrongEntryScope | None, Query(description='题库错题或自主录入')] = None,
 ) -> ResponseSchemaModel[CursorPageData[GetWrongQuestionListItem]]:
    """系统内答错与外部录入使用同一列表模型"""
    stmt = wrong_review_service.get_list_select(
        user_id=request.user.id,
        status=status,
        entry_source=entry_source,
        entry_scope=entry_scope,
    )
    return response_base.success(data=await cursor_paging_data(db, stmt, GetWrongQuestionListItem))


@router.get('/statistics', summary='获取错题统计', name='qbank_v2_get_wrong_question_statistics')
async def get_wrong_question_statistics(
    request: Request,
    db: CurrentSession,
    group_by: Annotated[Literal['bank', 'knowledge_point'], Query(description='分组方式')] = 'bank',
    knowledge_system_id: Annotated[
        int | None, Query(gt=0, description='知识体系 ID；空则按偏好回落 default，仅知识点分组生效')
    ] = None,
) -> ResponseSchemaModel[WrongQuestionStatistics]:
    """获取错题总数、到期数、复盘数及题库或知识点分组"""
    data = await wrong_review_service.get_statistics(
        db=db,
        user_id=request.user.id,
        group_by=group_by,
        knowledge_system_id=knowledge_system_id,
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
) -> ResponseSchemaModel[CursorPageData[GetWrongQuestionListItem]]:
    """考前回顾入口；不过滤错题本状态，已移出的题仍可查看"""
    stmt = wrong_review_service.get_reviewed_select(
        user_id=request.user.id,
        mastery_state=mastery_state,
        tag_id=tag_id,
        knowledge_point_id=knowledge_point_id,
        keyword=keyword,
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
) -> ResponseSchemaModel[CursorPageData[GetWrongQuestionListItem]]:
    """仍在错题本且从未复盘的题；复盘一次即自动出队"""
    stmt = wrong_review_service.get_pending_review_select(
        user_id=request.user.id,
        entry_scope=entry_scope,
    )
    return response_base.success(data=await cursor_paging_data(db, stmt, GetWrongQuestionListItem))


@router.get('/dashboard', summary='获取错因与知识点看板', name='qbank_v2_get_wrong_review_dashboard')
async def get_wrong_review_dashboard(
    request: Request,
    db: CurrentSession,
    knowledge_system_id: Annotated[
        int | None, Query(gt=0, description='知识体系 ID；空则按偏好回落 default')
    ] = None,
) -> ResponseSchemaModel[GetWrongReviewDashboard]:
    """分布来自用户复盘时主观选择的标签和知识点"""
    data = await wrong_review_service.get_dashboard(
        db=db,
        user_id=request.user.id,
        knowledge_system_id=knowledge_system_id,
    )
    return response_base.success(data=data)


@router.post('/external', summary='录入外部错题', name='qbank_v2_capture_external_wrong_question')
async def capture_external_wrong_question(
    request: Request,
    db: CurrentSessionTransaction,
    obj: CreateExternalWrongQuestionParam,
) -> ResponseSchemaModel[GetWrongQuestionDetail]:
    """将手工、OCR 或导入题统一创建为可重练的用户私有题目"""
    data = await wrong_review_service.capture_external(db=db, user_id=request.user.id, obj=obj)
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
) -> ResponseSchemaModel[CursorPageData[GetQuestionReviewDetail]]:
    """分页返回录入和复盘事件，按发生时间倒序"""
    stmt = await wrong_review_service.get_review_events_select(
        db=db,
        user_id=request.user.id,
        wrong_state_id=wrong_state_id,
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
