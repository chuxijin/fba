from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Path, Query, Request
from sqlalchemy import func, select

from backend.app.admin.crud.crud_category import category_dao
from backend.app.question_bank_v2.crud.crud_preference import practice_preference_dao
from backend.app.question_bank_v2.schema.practice import (
    PRACTICE_SESSION_RANGE_DAYS,
    CreatePracticeSessionParam,
    GetPracticeResponseDetail,
    GetPracticeSessionDetail,
    GetPracticeSessionListItem,
    GetPracticeSessionListPage,
    GetPracticeSessionReport,
    GetPracticeSessionSolutionItem,
    GetPracticeSolutionDetail,
    PracticeSessionRange,
    SavePracticeResponseParam,
    SubmitPracticeItemParam,
    SubmitPracticeItemResult,
    SubmitPracticeSessionResult,
)
from backend.app.question_bank_v2.service.practice_service import practice_service
from backend.common.pagination import (
    DependsCursorPagination,
    _CustomCursorParams,
    cursor_paging_data,
)
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction
from backend.utils.timezone import timezone

router = APIRouter(dependencies=[DependsJwtAuth])


@router.post('', summary='创建练习会话', name='qbank_v2_create_practice_session')
async def create_practice_session(
    request: Request,
    db: CurrentSessionTransaction,
    obj: CreatePracticeSessionParam,
) -> ResponseSchemaModel[GetPracticeSessionDetail]:
    """按稳定题库 ID 校验刷题权限并固定当前发布版本"""
    data = await practice_service.create(db=db, user_id=request.user.id, obj=obj)
    return response_base.success(data=data)


@router.get(
    '',
    summary='分页获取练习会话历史',
    name='qbank_v2_get_practice_sessions',
    dependencies=[DependsCursorPagination],
)
async def get_practice_sessions(
    request: Request,
    db: CurrentSession,
    page_params: Annotated[_CustomCursorParams, DependsCursorPagination],
    status: Annotated[str | None, Query(description='会话状态，多个用逗号分隔，如 graded,submitted')] = None,
    mode: Annotated[str | None, Query(description='练习模式，多个用逗号分隔，如 exam,mock')] = None,
    source_type: Annotated[str | None, Query(max_length=24, description='组题来源类型')] = None,
    bank_id: Annotated[int | None, Query(gt=0, description='题库稳定身份 ID')] = None,
    time_range: Annotated[PracticeSessionRange, Query(description='时间范围：all / 7d / 30d / 90d')] = 'all',
) -> ResponseSchemaModel[GetPracticeSessionListPage]:
    category_ids: list[int] | None = None
    preference = await practice_preference_dao.get_by_user_id(db, request.user.id)
    root_category_id = getattr(preference, 'current_category_id', None)
    if root_category_id:
        category_ids = await category_dao.get_subtree_ids_by_path(db, root_category_id)
        if not category_ids:
            category_ids = None

    range_days = PRACTICE_SESSION_RANGE_DAYS.get(time_range)
    created_after = timezone.now() - timedelta(days=range_days) if range_days else None

    stmt = practice_service.get_list_select(
        user_id=request.user.id,
        status=status,
        mode=mode,
        source_type=source_type,
        bank_id=bank_id,
        created_after=created_after,
        category_ids=category_ids,
    )
    # 仅首页统计总数：翻页时没必要为了列表头再 count 一次
    total: int | None = None
    if not page_params.cursor:
        total = int(await db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0)

    page_data = await cursor_paging_data(db, stmt, GetPracticeSessionListItem, unique=False)
    return response_base.success(data=GetPracticeSessionListPage(total=total, **page_data))


@router.get('/{session_key}', summary='获取练习会话', name='qbank_v2_get_practice_session')
async def get_practice_session(
    request: Request,
    db: CurrentSessionTransaction,
    session_key: Annotated[str, Path(min_length=8, max_length=64, description='会话标识')],
) -> ResponseSchemaModel[GetPracticeSessionDetail]:
    """仅会话所有者可以读取投递题目，响应不包含标准答案与解析"""
    data = await practice_service.get(db=db, session_key=session_key, user_id=request.user.id)
    return response_base.success(data=data)


@router.delete('/{session_key}', summary='隐藏练习会话', name='qbank_v2_delete_practice_session')
async def delete_practice_session(
    request: Request,
    db: CurrentSessionTransaction,
    session_key: Annotated[str, Path(min_length=8, max_length=64, description='会话标识')],
) -> ResponseSchemaModel[None]:
    """仅隐藏用户历史入口，保留作答事实、错题和学习统计"""
    await practice_service.hide(db=db, session_key=session_key, user_id=request.user.id)
    return response_base.success()


@router.get(
    '/{session_key}/report',
    summary='获取整场练习报告',
    name='qbank_v2_get_practice_session_report',
)
async def get_practice_session_report(
    request: Request,
    db: CurrentSessionTransaction,
    session_key: Annotated[str, Path(min_length=8, max_length=64, description='会话标识')],
) -> ResponseSchemaModel[GetPracticeSessionReport]:
    data = await practice_service.get_report(db=db, session_key=session_key, user_id=request.user.id)
    return response_base.success(data=data)


@router.get(
    '/{session_key}/solutions',
    summary='获取整场答案解析',
    name='qbank_v2_get_practice_session_solutions',
)
async def get_practice_session_solutions(
    request: Request,
    db: CurrentSessionTransaction,
    session_key: Annotated[str, Path(min_length=8, max_length=64, description='会话标识')],
) -> ResponseSchemaModel[list[GetPracticeSessionSolutionItem]]:
    data = await practice_service.get_session_solutions(
        db=db,
        session_key=session_key,
        user_id=request.user.id,
    )
    return response_base.success(data=data)


@router.put(
    '/{session_key}/items/{session_item_id}/response',
    summary='自动保存题目答案',
    name='qbank_v2_save_practice_response',
)
async def save_practice_response(
    request: Request,
    db: CurrentSessionTransaction,
    session_key: Annotated[str, Path(min_length=8, max_length=64, description='会话标识')],
    session_item_id: Annotated[int, Path(gt=0, description='会话题目 ID')],
    obj: SavePracticeResponseParam,
) -> ResponseSchemaModel[GetPracticeResponseDetail]:
    """按客户端 save_version 乐观锁保存答案草稿"""
    data = await practice_service.save_response(
        db=db,
        session_key=session_key,
        user_id=request.user.id,
        session_item_id=session_item_id,
        obj=obj,
    )
    return response_base.success(data=data)


@router.post(
    '/{session_key}/items/{session_item_id}/submit',
    summary='提交单题答案',
    name='qbank_v2_submit_practice_item',
)
async def submit_practice_item(
    request: Request,
    db: CurrentSessionTransaction,
    session_key: Annotated[str, Path(min_length=8, max_length=64, description='会话标识')],
    session_item_id: Annotated[int, Path(gt=0, description='会话题目 ID')],
    obj: SubmitPracticeItemParam,
) -> ResponseSchemaModel[SubmitPracticeItemResult]:
    """追加不可变作答事实并同步当前判分缓存"""
    data = await practice_service.submit_item(
        db=db,
        session_key=session_key,
        user_id=request.user.id,
        session_item_id=session_item_id,
        obj=obj,
    )
    return response_base.success(data=data)


@router.get(
    '/{session_key}/items/{session_item_id}/solution',
    summary='获取单题答案解析',
    name='qbank_v2_get_practice_solution',
)
async def get_practice_solution(
    request: Request,
    db: CurrentSession,
    session_key: Annotated[str, Path(min_length=8, max_length=64, description='会话标识')],
    session_item_id: Annotated[int, Path(gt=0, description='会话题目 ID')],
) -> ResponseSchemaModel[GetPracticeSolutionDetail]:
    """普通练习或背题模式可查看；考试和模考必须整卷交卷后查看"""
    data = await practice_service.get_solution(
        db=db,
        session_key=session_key,
        user_id=request.user.id,
        session_item_id=session_item_id,
    )
    return response_base.success(data=data)


@router.post(
    '/{session_key}/submit',
    summary='提交练习会话',
    name='qbank_v2_submit_practice_session',
)
async def submit_practice_session(
    request: Request,
    db: CurrentSessionTransaction,
    session_key: Annotated[str, Path(min_length=8, max_length=64, description='会话标识')],
) -> ResponseSchemaModel[SubmitPracticeSessionResult]:
    """交卷后冻结继续作答入口，并保留已有客观题判分结果"""
    data = await practice_service.submit_session(
        db=db,
        session_key=session_key,
        user_id=request.user.id,
    )
    return response_base.success(data=data)
