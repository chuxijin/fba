#!/usr/bin/env python3
from collections.abc import Sequence
from time import perf_counter
from typing import Annotated, Any

from fastapi import APIRouter, Body, File, Form, Path, Query, Request, UploadFile
from fastapi.responses import StreamingResponse
from loguru import logger

from backend.app.question_bank.model import QuestionAnalysis, QuestionStatistics
from backend.app.question_bank.schema.note import GetQuestionNoteDetail
from backend.app.question_bank.schema.question import (
    CreateQuestionParam,
    DeleteQuestionParam,
    QuestionCollectParam,
    QuestionCollectResult,
    UpdateQuestionParam,
)
from backend.app.question_bank.schema.question_import import (
    BatchImportParam,
    BatchImportResult,
    ExcelImportResult,
)
from backend.app.question_bank.service.favorite_service import favorite_service
from backend.app.question_bank.service.membership_service import membership_service
from backend.app.question_bank.service.note_service import note_service
from backend.app.question_bank.service.question_import_service import question_import_service
from backend.app.question_bank.service.question_selector_service import question_selector_service
from backend.app.question_bank.service.question_service import question_service
from backend.app.question_bank.service.session_service import session_service
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.exception import errors
from backend.common.security.jwt import DependsJwtAuth
from backend.common.security.rbac import DependsRBAC
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


async def _resolve_session_id(db: CurrentSession, session_key: str, user_id: int) -> int:
    """按 session_key 解析会话 ID 并校验归属"""
    from backend.app.question_bank.crud.crud_practice_session import practice_session_dao
    session = await practice_session_dao.get_by_key(db, session_key)
    if not session:
        raise errors.NotFoundError(msg='会话不存在')
    if session.user_id != user_id:
        raise errors.ForbiddenError(msg='无权访问此会话')
    return session.id


def _should_bypass_membership_checks(request: Request) -> bool:
    """判断是否允许跳过题库会员校验"""
    return bool(getattr(request.user, 'is_superuser', False))


# ============ 批量查询接口（必须在 /{pk} 之前） ===========


@router.get(
    '/favorites',
    summary='批量检查收藏状态',
    name='qbank_batch_check_favorites',
    dependencies=[DependsJwtAuth],
)
async def batch_check_favorites(
    request: Request,
    db: CurrentSession,
    question_ids: Annotated[str, Query(description='题目 ID 列表，逗号分隔')],
) -> ResponseSchemaModel[dict[int, bool]]:
    """批量检查收藏状态"""
    if not _should_bypass_membership_checks(request):
        await membership_service.verify_question_ids_access(
            db=db,
            user_id=request.user.id,
            question_ids=question_service.parse_int_csv(question_ids),
        )

    status_map = await favorite_service.batch_check_favorites_from_string(
        db=db, user_id=request.user.id, question_ids_str=question_ids
    )
    return response_base.success(data=status_map)


@router.get(
    '/notes',
    summary='批量查询笔记',
    name='qbank_batch_get_notes',
    dependencies=[DependsJwtAuth],
)
async def batch_get_notes(
    request: Request,
    db: CurrentSession,
    question_ids: Annotated[str, Query(description='题目 ID 列表，逗号分隔')],
) -> ResponseSchemaModel[dict[int, GetQuestionNoteDetail | None]]:
    """批量查询笔记"""
    if not _should_bypass_membership_checks(request):
        await membership_service.verify_question_ids_access(
            db=db,
            user_id=request.user.id,
            question_ids=question_service.parse_int_csv(question_ids),
        )

    note_map = await note_service.batch_get_notes_from_string(
        db=db, user_id=request.user.id, question_ids_str=question_ids
    )
    return response_base.success(data=note_map)


@router.get(
    '/collections',
    summary='动态获取题目合集',
    name='qbank_get_dynamic_collections',
    dependencies=[DependsJwtAuth],
)
async def get_dynamic_collections(
    request: Request,
    db: CurrentSession,
    cat_id: Annotated[int | None, Query(description='分类 ID')] = None,
    region: Annotated[str | None, Query(description='地区关键字')] = None,
    knowledge_ids: Annotated[str | None, Query(description='知识点 ID，逗号分隔')] = None,
    knowledge_names: Annotated[str | None, Query(description='知识点名称，逗号分隔')] = None,
    stem_keyword: Annotated[str | None, Query(description='题干关键字')] = None,
    option_keyword: Annotated[str | None, Query(description='选项关键字')] = None,
    analysis_keyword: Annotated[str | None, Query(description='解析关键字')] = None,
    year_start: Annotated[int | None, Query(description='起始年份（按题目创建年）')] = None,
    year_end: Annotated[int | None, Query(description='结束年份（按题目创建年）')] = None,
) -> ResponseSchemaModel[list[dict[str, Any]]]:
    """按筛选条件动态返回试卷合集（通过题目挂载关系聚合）"""
    if year_start is not None and year_end is not None and year_start > year_end:
        year_start, year_end = year_end, year_start

    knowledge_id_list = question_service.parse_int_csv(knowledge_ids)
    knowledge_name_list = question_service.parse_text_csv(knowledge_names)

    if not _should_bypass_membership_checks(request):
        await membership_service.verify_filter_access(
            db=db,
            user_id=request.user.id,
            cat_id=cat_id,
            region=region,
            year_start=year_start,
            year_end=year_end,
            stem_keyword=stem_keyword,
            option_keyword=option_keyword,
            analysis_keyword=analysis_keyword,
        )
        await membership_service.verify_knowledge_access(
            db=db,
            user_id=request.user.id,
            knowledge_ids=knowledge_id_list,
            knowledge_names=knowledge_name_list,
        )

    data = await question_service.get_dynamic_collections(
        db=db,
        cat_id=cat_id,
        region=region,
        knowledge_ids=knowledge_id_list,
        knowledge_names=knowledge_name_list,
        stem_keyword=stem_keyword,
        option_keyword=option_keyword,
        analysis_keyword=analysis_keyword,
        year_start=year_start,
        year_end=year_end,
    )
    return response_base.success(data=data)


@router.post(
    '/collect',
    summary='统一筛选题目并返回题目 ID 列表',
    name='qbank_collect_questions',
    dependencies=[DependsJwtAuth],
)
async def collect_questions(
    request: Request,
    db: CurrentSession,
    obj: QuestionCollectParam,
) -> ResponseSchemaModel[QuestionCollectResult]:
    """统一筛题入口，适用于前端选题、会话建题与题本渲染前置筛选。"""
    allow_admin_read = _should_bypass_membership_checks(request)

    if obj.chapter_id is not None:
        obj.bank_id = await membership_service.resolve_bank_context_for_chapter(
            db=db,
            chapter_id=obj.chapter_id,
            bank_id=obj.bank_id,
            user_id=None if allow_admin_read else request.user.id,
        )

    if not allow_admin_read:
        if obj.source_type == 'placement' and obj.question_ids:
            await membership_service.verify_question_ids_access(
                db=db,
                user_id=request.user.id,
                question_ids=obj.question_ids,
            )
        elif obj.source_type == 'placement' and obj.bank_id:
            await membership_service.verify_bank_list_access(
                db=db,
                user_id=request.user.id,
                bank_id=obj.bank_id,
            )

        await membership_service.verify_filter_access(
            db=db,
            user_id=request.user.id,
            cat_id=obj.cat_id,
            region=obj.region,
            year_start=obj.year_start,
            year_end=obj.year_end,
            stem_keyword=obj.stem_keyword,
            option_keyword=obj.option_keyword,
            analysis_keyword=obj.analysis_keyword,
        )
        await membership_service.verify_knowledge_access(
            db=db,
            user_id=request.user.id,
            knowledge_point=obj.knowledge_point,
        )

        if obj.source_type == 'placement' and obj.content_status is None:
            obj.content_status = 10
        if obj.source_type == 'placement' and obj.is_active is None:
            obj.is_active = True

    # 个人来源（错题/收藏/笔记）：展开父题库为包含所有后代题库的 ID 列表
    if obj.source_type != 'placement' and obj.bank_id and not obj.bank_ids:
        from backend.app.question_bank.service.group_tree import get_descendant_bank_ids

        descendant_ids = await get_descendant_bank_ids(db, obj.bank_id)
        if len(descendant_ids) > 1:
            obj.bank_ids = descendant_ids
            obj.bank_id = None

    data = await question_selector_service.collect_question_ids(
        db=db,
        params=obj,
        user_id=request.user.id,
    )
    return response_base.success(data=data)


@router.get(
    '/sessions/{session_key}/favorites',
    summary='按会话批量检查收藏状态',
    name='qbank_get_session_favorites',
    dependencies=[DependsJwtAuth],
)
async def get_session_favorites(
    request: Request,
    db: CurrentSession,
    session_key: Annotated[str, Path(description='会话 Key')],
) -> ResponseSchemaModel[dict[int, bool]]:
    """按会话批量检查收藏状态"""
    sid = await _resolve_session_id(db, session_key, request.user.id)
    status_map = await favorite_service.batch_check_favorites_by_session(
        db=db,
        user_id=request.user.id,
        session_id=sid,
    )
    return response_base.success(data=status_map)


@router.get(
    '/sessions/{session_key}/notes',
    summary='按会话批量查询笔记',
    name='qbank_get_session_notes',
    dependencies=[DependsJwtAuth],
)
async def get_session_notes(
    request: Request,
    db: CurrentSession,
    session_key: Annotated[str, Path(description='会话 Key')],
) -> ResponseSchemaModel[dict[int, GetQuestionNoteDetail]]:
    """按会话批量查询笔记"""
    sid = await _resolve_session_id(db, session_key, request.user.id)
    note_map = await note_service.batch_get_notes_by_session(
        db=db,
        user_id=request.user.id,
        session_id=sid,
    )
    return response_base.success(data=note_map)


@router.get(
    '/import-template',
    summary='下载题目导入 Excel 模板',
    name='qbank_import_template',
    dependencies=[DependsJwtAuth],
)
async def download_import_template() -> StreamingResponse:
    """下载空白 Excel 导入模板"""
    import io

    content = await question_import_service.build_import_template()
    return StreamingResponse(
        io.BytesIO(content),
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={'Content-Disposition': 'attachment; filename=question_import_template.xlsx'},
    )


# ============ 题目相关接口 ============


@router.get('/{pk}', summary='获取题目详情（不含答案）', name='qbank_get_question', dependencies=[DependsJwtAuth])
async def get_question(
    request: Request,
    db: CurrentSession,
    pk: Annotated[int, Path(description='题目 ID')],
) -> ResponseSchemaModel[dict[str, Any]]:
    """
    获取题目详情（不含答案和解析）

    - 客户：需要会员权限验证
    - 管理员：直接查看，无需会员验证
    """
    if not _should_bypass_membership_checks(request):
        await membership_service.verify_question_access(db=db, user_id=request.user.id, question_id=pk)

    data = await question_service.get(db=db, pk=pk)
    return response_base.success(data=data)


@router.get(
    '',
    summary='获取题目列表',
    name='qbank_get_question_list',
    dependencies=[DependsJwtAuth],
)
async def get_question_list(
    request: Request,
    db: CurrentSession,
    ids: Annotated[str | None, Query(description='题目 ID 列表，逗号分隔')] = None,
    bank_id: Annotated[int | None, Query(description='题库 ID')] = None,
    chapter_id: Annotated[int | None, Query(description='章节 ID')] = None,
    type: Annotated[str | None, Query(description='题型')] = None,
    difficulty: Annotated[str | None, Query(description='难度')] = None,
    content_status: Annotated[int | None, Query(description='内容状态')] = None,
    is_active: Annotated[bool | None, Query(description='是否启用（挂载级别）')] = None,
    review_status: Annotated[int | None, Query(description='审核状态（挂载级别）')] = None,
    keyword: Annotated[str | None, Query(description='关键字搜索')] = None,
    page: Annotated[int | None, Query(description='页码', ge=1)] = None,
    size: Annotated[int | None, Query(description='每页数量', ge=1, le=100)] = None,
    include_answer: Annotated[bool, Query(description='是否包含答案（用于查看历史记录）')] = False,
) -> ResponseSchemaModel[Sequence[dict[str, Any]] | dict[str, Any]]:
    """
    获取题目列表

    - 客户：需要会员权限验证，不支持分页
    - 管理员：无需会员验证，支持分页
    - 支持通过 ids 参数批量获取指定题目
    - include_answer=True 时返回答案和解析
    """
    allow_admin_read = _should_bypass_membership_checks(request)

    # 解析 ids 参数
    question_ids = None
    if ids:
        question_ids = [int(id.strip()) for id in ids.split(',') if id.strip()]

    if chapter_id is not None:
        bank_id = await membership_service.resolve_bank_context_for_chapter(
            db=db,
            chapter_id=chapter_id,
            bank_id=bank_id,
            user_id=None if allow_admin_read else request.user.id,
        )

    if not allow_admin_read:
        if question_ids:
            await membership_service.verify_question_ids_access(
                db=db,
                user_id=request.user.id,
                question_ids=question_ids,
            )
        elif bank_id:
            await membership_service.verify_bank_list_access(db=db, user_id=request.user.id, bank_id=bank_id)

    data = await question_service.get_list(
        db=db,
        ids=question_ids,
        bank_id=bank_id,
        chapter_id=chapter_id,
        type=type,
        difficulty=difficulty,
        content_status=content_status,
        is_active=is_active,
        review_status=review_status,
        keyword=keyword,
        page=page if allow_admin_read else None,
        size=size if allow_admin_read else None,
        include_analysis=include_answer,
    )

    return response_base.success(data=data)


@router.post(
    '',
    summary='创建题目',
    name='qbank_create_question',
    dependencies=[DependsRBAC],
)
async def create_question(request: Request, db: CurrentSessionTransaction, obj: CreateQuestionParam) -> ResponseModel:
    """管理员接口 - 创建题目"""
    await question_service.create(db=db, obj=obj, user_id=request.user.id)
    return response_base.success()


@router.put(
    '/{pk}',
    summary='更新题目',
    name='qbank_update_question',
    dependencies=[DependsRBAC],
)
async def update_question(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='题目 ID')],
    obj: UpdateQuestionParam,
) -> ResponseModel:
    """管理员接口 - 更新题目"""
    count = await question_service.update(db=db, pk=pk, obj=obj, user_id=request.user.id)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete(
    '',
    summary='删除题目',
    name='qbank_delete_question',
    dependencies=[DependsRBAC],
)
async def delete_question(db: CurrentSessionTransaction, obj: DeleteQuestionParam) -> ResponseModel:
    """管理员接口 - 删除题目（级联删除解析和统计）"""
    count = await question_service.delete(db=db, obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()


# ============ 题目解析相关接口 ============


@router.get(
    '/{pk}/analysis',
    summary='获取题目解析（含答案）',
    name='qbank_get_question_analysis',
    dependencies=[DependsJwtAuth],
)
async def get_question_analysis(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='题目 ID')],
) -> ResponseSchemaModel[QuestionAnalysis]:
    """
    获取题目解析（含答案）

    - 客户：需要会员权限验证，自动增加查看次数（需要写入，因此使用 Transaction）
    - 管理员：直接查看，不增加查看次数
    """
    if not _should_bypass_membership_checks(request):
        await membership_service.verify_question_access(db=db, user_id=request.user.id, question_id=pk)
        increment_view = True
    else:
        increment_view = False

    data = await question_service.get_analysis(db=db, question_id=pk, increment_view=increment_view)
    return response_base.success(data=data)


@router.get(
    '/{pk}/solution',
    summary='获取题目答案和解析（练题模式专用）',
    name='qbank_get_question_solution',
    dependencies=[DependsJwtAuth],
)
async def get_question_solution(
    request: Request,
    db: CurrentSession,
    pk: Annotated[int, Path(description='题目 ID')],
    user_answer: Annotated[str | None, Query(description='用户答案（用于判题）')] = None,
) -> ResponseSchemaModel[dict[str, Any]]:
    """获取题目答案和解析（练题模式专用）"""
    data = await question_service.get_solution(db=db, question_id=pk, user_answer=user_answer)
    return response_base.success(data=data)


@router.post(
    '/{pk}/analysis/helpful',
    summary='标记解析是否有帮助',
    name='qbank_mark_analysis_helpful',
    dependencies=[DependsJwtAuth],
)
async def mark_analysis_helpful(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='题目 ID')],
    is_helpful: Annotated[bool, Body(embed=True, description='是否有帮助')],
) -> ResponseModel:
    """标记解析是否有帮助"""
    await question_service.mark_analysis_helpful(db=db, question_id=pk, is_helpful=is_helpful)
    return response_base.success()


# ============ 题目统计相关接口 ============


@router.get(
    '/{pk}/statistics',
    summary='获取题目统计',
    name='qbank_get_question_statistics',
    dependencies=[DependsJwtAuth],
)
async def get_question_statistics(
    request: Request,
    db: CurrentSession,
    pk: Annotated[int, Path(description='题目 ID')],
) -> ResponseSchemaModel[QuestionStatistics]:
    """获取题目统计"""
    if not _should_bypass_membership_checks(request):
        await membership_service.verify_question_access(db=db, user_id=request.user.id, question_id=pk)

    data = await question_service.get_statistics(db=db, question_id=pk)
    return response_base.success(data=data)


# ============ 批量导入相关接口 ============


@router.post('/import', summary='批量导入题目', name='qbank_batch_import_questions', dependencies=[DependsRBAC])
async def batch_import_questions(
    request: Request,
    db: CurrentSessionTransaction,
    obj: BatchImportParam,
) -> ResponseSchemaModel[BatchImportResult]:
    """
    管理员接口 - 批量导入题目（从 CSV）

    - 支持中文题型和难度
    - 自动创建章节（一级/二级目录）
    - 同时创建题目和解析记录
    - 返回详细的导入结果
    """
    data = await question_import_service.batch_import(db=db, obj=obj, user_id=request.user.id)
    return response_base.success(data=data)


@router.post(
    '/import-excel',
    summary='从 Excel 文件导入题目',
    name='qbank_import_from_excel',
    dependencies=[DependsRBAC],
)
async def import_from_excel(
    request: Request,
    db: CurrentSessionTransaction,
    bank_id: Annotated[int, Form(description='目标题库 ID')],
    file: Annotated[UploadFile, File(description='Excel 文件（.xlsx）')],
) -> ResponseSchemaModel[ExcelImportResult]:
    """
    从 Excel 导入题目

    - Sheet1「题目」：必填，包含题目数据
    - Sheet2「材料」：可选，包含公共材料
    - 支持题干去重：已存在的题目仅新增挂载
    """
    content = await file.read()
    question_rows, material_rows = await question_import_service.parse_excel_file(
        content=content, filename=file.filename,
    )
    data = await question_import_service.import_from_excel(
        db=db,
        bank_id=bank_id,
        question_rows=question_rows,
        material_rows=material_rows,
        user_id=request.user.id,
    )
    return response_base.success(data=data)


# ============ 会话题目批量获取接口 ============
# TODO: 此接口语义上属于 session 模块，但移动会变更 API 路径，暂保留在此


@router.get(
    '/sessions/{session_key}',
    summary='获取会话题目静态内容和材料',
    name='qbank_get_session_questions',
    dependencies=[DependsJwtAuth],
)
async def get_session_questions(
    request: Request,
    db: CurrentSession,
    session_key: Annotated[str, Path(description='会话 Key')],
) -> ResponseSchemaModel[dict[str, Any]]:
    """
    获取会话题目静态内容和去重材料

    - 题目静态内容一次性返回（不含材料全文，仅含 material_ids）
    - 材料独立返回并去重
    - 前端不再逐题拉取题干/选项/材料
    """
    timings: list[tuple[str, float]] = []
    total_start = perf_counter()

    # Cut #1：service 内部一条 SQL 完成 key→id 解析 + 归属校验，省掉路由层 _resolve_session_id
    t0 = perf_counter()
    data = await session_service.get_session_questions_with_materials(
        db=db, session_key=session_key, user_id=request.user.id
    )
    timings.append(('get_session_questions_with_materials', perf_counter() - t0))

    logger.debug(
        'get_session_questions_route_timing | user_id={} session_key={} total={:.1f}ms detail={}',
        request.user.id,
        session_key,
        (perf_counter() - total_start) * 1000,
        ', '.join(f'{name}={cost * 1000:.1f}ms' for name, cost in timings),
    )
    return response_base.success(data=data)
