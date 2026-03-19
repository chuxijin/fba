#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool

from backend.app.question_bank.crud.crud_bank import bank_dao
from backend.app.question_bank.crud.crud_material import material_dao
from backend.app.question_bank.schema.material import CreateMaterialParam
from backend.app.question_bank.schema.parse import SaveSegmentsParam, SmartCommitParam
from backend.app.question_bank.schema.question import (
    CreateQuestionParam,
    QuestionCoreBase,
    UpsertQuestionAnalysisItem,
    UpsertQuestionOptionItem,
    UpsertQuestionPlacementItem,
)
from backend.app.question_bank.service.parse_service import parse_service
from backend.app.question_bank.service.question_service import QuestionService, question_service
from backend.common.response.response_code import CustomResponse
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.core.path_conf import UPLOAD_DIR
from backend.database.db import CurrentSessionTransaction
from backend.utils.file_ops import upload_file

router = APIRouter()


@router.post('/pdf', summary='上传并解析PDF试卷为Markdown', name='qbank_parse_pdf')
async def upload_and_parse_pdf(
    request: Request,
    file: Annotated[UploadFile, File()],
) -> Any:
    """上传 PDF 试卷，用 LlamaParse 智能提取 Markdown 和图片"""
    if not file.filename.lower().endswith('.pdf'):
        return response_base.fail(res=CustomResponse(code=400, msg='请上传 .pdf 格式文件'))

    temp_folder = 'temp_pdf'
    filename = await upload_file(file, folder=temp_folder)
    file_path = UPLOAD_DIR / filename

    try:
        folder_name = file.filename.rsplit('.', 1)[0]
        md_content = await parse_service.parse_pdf_to_markdown(
            file_path=file_path,
            images_dir_name=folder_name,
            request_base_url=str(request.base_url),
        )
        return response_base.success(data={'markdown': md_content})
    except Exception as e:
        return response_base.fail(res=CustomResponse(code=400, msg=f'解析失败: {e}'))


@router.post(
    '/smart-extract',
    summary='仅智能识别提取(不入库)',
    name='qbank_smart_extract_pdf',
    dependencies=[DependsJwtAuth],
)
async def smart_extract_pdf(
    request: Request,
    db: CurrentSessionTransaction,
    bank_id: Annotated[int, Form(...)],
    file: Annotated[UploadFile, File(...)],
) -> Any:
    """智能提取 PDF/Markdown 文件中的题目结构（不入库）"""
    is_pdf = file.filename.lower().endswith('.pdf')
    is_md = file.filename.lower().endswith('.md')
    if not (is_pdf or is_md):
        return response_base.fail(res=CustomResponse(code=400, msg='请上传 .pdf 或 .md 格式文件'))

    temp_folder = 'temp_pdf'
    filename = await upload_file(file, folder=temp_folder)
    file_path = UPLOAD_DIR / filename

    bank = await bank_dao.get(db, bank_id)
    if not bank:
        return response_base.fail(res=CustomResponse(code=400, msg='题库不存在'))
    folder_name = bank.name

    try:
        if is_pdf:
            md_content = await parse_service.parse_pdf_to_markdown(
                file_path=file_path,
                images_dir_name=folder_name,
                request_base_url=str(request.base_url),
            )
        else:
            md_content = await run_in_threadpool(file_path.read_text, encoding='utf-8')

        extract_result = await parse_service.extract_questions_from_md(
            db=db, md_content=md_content, provider_id=4,
        )

        materials_data = extract_result.get('materials', [])
        questions_data = extract_result.get('questions', [])
        return response_base.success(data={
            'materials': materials_data,
            'questions': questions_data,
            'raw_md_length': len(md_content),
            'materials_count': len(materials_data),
            'questions_count': len(questions_data),
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return response_base.fail(res=CustomResponse(code=400, msg=f'智能提取失败: {e}'))


@router.post(
    '/smart-extract-stream',
    summary='智能提取(支持流式)',
    name='qbank_smart_extract_stream',
    dependencies=[DependsJwtAuth],
)
async def smart_extract_pdf_stream(
    request: Request,
    db: CurrentSessionTransaction,
    bank_id: Annotated[int, Form(...)],
    file: Annotated[UploadFile, File(...)],
) -> Any:
    """智能流式提取 PDF/Markdown 中的题目结构"""
    is_pdf = file.filename.lower().endswith('.pdf')
    is_md = file.filename.lower().endswith('.md')
    if not (is_pdf or is_md):
        return response_base.fail(res=CustomResponse(code=400, msg='请上传 .pdf 或 .md 格式文件'))

    temp_folder = 'temp_pdf'
    filename = await upload_file(file, folder=temp_folder)
    file_path = UPLOAD_DIR / filename

    bank = await bank_dao.get(db, bank_id)
    if not bank:
        return response_base.fail(res=CustomResponse(code=400, msg='题库不存在'))
    folder_name = bank.name

    try:
        if is_pdf:
            md_content = await parse_service.parse_pdf_to_markdown(
                file_path=file_path,
                images_dir_name=folder_name,
                request_base_url=str(request.base_url),
            )
        else:
            md_content = await run_in_threadpool(file_path.read_text, encoding='utf-8')

        async def event_generator():
            import json

            async for chunk_result in parse_service.extract_questions_stream(db, md_content, provider_id=4):
                yield f"data: {json.dumps(chunk_result, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(event_generator(), media_type='text/event-stream')
    except Exception as e:
        import traceback
        traceback.print_exc()
        return response_base.fail(res=CustomResponse(code=400, msg=f'智能流式提取失败: {e}'))


@router.post(
    '/smart-commit',
    summary='提交智能解析结果入库',
    name='qbank_smart_commit',
    dependencies=[DependsJwtAuth],
)
async def smart_commit_docs(
    request: Request,
    db: CurrentSessionTransaction,
    param: SmartCommitParam,
) -> Any:
    """
    将前端确认后的智能解析结果批量入库

    通过 question_service.create() 走标准嵌套 schema 流程，
    保证选项归一化、挂载写入、解析写入、材料关联等所有副作用完整执行。
    """
    try:
        bank_id = param.bank_id
        materials_data = param.materials
        questions_data = param.questions
        user_id = request.user.id if hasattr(request, 'user') else 1

        bank = await bank_dao.get(db, bank_id)
        if not bank:
            return response_base.fail(res=CustomResponse(code=400, msg='题库不存在'))

        # -------- 1. 保存公共材料 --------
        # 前端可能传入临时 material_id 与 question 的 material_id 对应
        material_id_map: dict[str | int, int] = {}
        for m_data in materials_data:
            create_material = CreateMaterialParam(
                bank_id=bank_id,
                title=m_data.get('title', '资料分析材料'),
                content=m_data.get('content', ''),
                is_active=True,
            )
            material = await material_dao.create(db, create_material, created_by=user_id)
            await db.flush()

            temp_id = m_data.get('material_id')
            if temp_id is not None:
                material_id_map[temp_id] = material.id

        # -------- 2. 逐题构建 CreateQuestionParam 并调用 service --------
        chapter_cache: dict[str, int] = {}
        success_count = 0

        for q_data in questions_data:
            # 2a. 章节处理
            chapter_id = None
            c_name = q_data.get('chapter_name')
            if c_name:
                chapter_id = await QuestionService._get_or_create_chapter(
                    db=db, bank_id=bank_id, level1_name=c_name, level2_name=None, chapter_cache=chapter_cache,
                )

            # 2b. 基本字段
            q_type = q_data.get('type') or 'single'
            q_diff = q_data.get('difficulty') or 'medium'
            q_default_score = Decimal(str(q_data.get('score') or '1.0'))

            sort_order = q_data.get('sort_order')
            if sort_order is None:
                sort_order = success_count + 1
            elif isinstance(sort_order, str) and sort_order.isdigit():
                sort_order = int(sort_order)
            elif not isinstance(sort_order, int):
                sort_order = success_count + 1

            knowledge_point = q_data.get('knowledge_point')
            if isinstance(knowledge_point, str):
                knowledge_point = [knowledge_point] if knowledge_point else None

            # 2c. 构建 core
            core = QuestionCoreBase(
                type=q_type,
                stem=q_data.get('stem') or '',
                difficulty=q_diff,
                default_score=q_default_score,
                knowledge_point=knowledge_point,
            )

            # 2d. 构建选项
            options: list[UpsertQuestionOptionItem] = []
            raw_options = q_data.get('options_data')
            if isinstance(raw_options, dict):
                for code, opt in raw_options.items():
                    content = opt.get('content', '') if isinstance(opt, dict) else str(opt)
                    options.append(UpsertQuestionOptionItem(
                        option_code=code.upper(),
                        content=content,
                        sort_order=ord(code.upper()) - ord('A'),
                    ))

            # 2e. 构建挂载（一题一挂载，挂到 bank + chapter）
            placements = [UpsertQuestionPlacementItem(
                bank_id=bank_id,
                chapter_id=chapter_id,
                sort_order=sort_order,
                is_active=True,
                score=q_default_score,
                review_status=10,
            )]

            # 2f. 构建解析
            answer_data = q_data.get('answer_data') or {}
            analysis_content = q_data.get('analysis_content') or ''
            analyses = [UpsertQuestionAnalysisItem(
                type='official',
                is_default=True,
                answer_data=answer_data,
                content=analysis_content or '暂无解析',
            )]

            # 2g. 材料关联
            material_ids: list[int] | None = None
            temp_mid = q_data.get('material_id')
            if temp_mid is not None and temp_mid in material_id_map:
                material_ids = [material_id_map[temp_mid]]

            # 2h. 组装并调用 service.create
            create_param = CreateQuestionParam(
                core=core,
                options=options,
                placements=placements,
                analyses=analyses,
                material_ids=material_ids,
            )
            await question_service.create(db=db, obj=create_param, user_id=user_id)
            success_count += 1

        # -------- 3. 更新题库 q_count_cache --------
        if success_count > 0:
            await QuestionService._update_bank_q_count_cache_recursive(
                db=db, bank_id=bank_id, delta=success_count,
            )
            await db.flush()

        return response_base.success(data={
            'materials_count': len(materials_data),
            'questions_count': success_count,
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return response_base.fail(res=CustomResponse(code=400, msg=f'解析结果提交入库失败: {e}'))


@router.post(
    '/save-segments',
    summary='保存分段 Markdown 到服务器',
    name='qbank_save_segments',
    dependencies=[DependsJwtAuth],
)
async def save_segments(
    db: CurrentSessionTransaction,
    param: SaveSegmentsParam,
) -> Any:
    """将前端编辑后的分段 Markdown 保存到服务器文件系统"""
    try:
        bank = await bank_dao.get(db, param.bank_id)
        if not bank:
            return response_base.fail(res=CustomResponse(code=400, msg='题库不存在'))

        base_dir = UPLOAD_DIR / 'parsed_md' / bank.name
        base_dir.mkdir(parents=True, exist_ok=True)

        saved_files = []
        for seg in param.segments:
            name = seg.get('name', '未命名分片')
            content = seg.get('content', '')

            safe_name = ''.join([c for c in name if c.isalnum() or c in (' ', '_', '-')]).rstrip()
            file_path = base_dir / f'{safe_name}.md'

            await run_in_threadpool(file_path.write_text, content, encoding='utf-8')
            saved_files.append(str(file_path))

        return response_base.success(data={'count': len(saved_files), 'path': str(base_dir)})
    except Exception as e:
        return response_base.fail(res=CustomResponse(code=400, msg=f'保存失败: {e}'))

