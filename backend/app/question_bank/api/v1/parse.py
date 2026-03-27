#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import logging
from typing import Annotated, Any

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool

from backend.app.question_bank.crud.crud_bank import bank_dao
from backend.app.question_bank.schema.parse import SaveSegmentsParam, SmartCommitParam
from backend.app.question_bank.service.parse_service import parse_service
from backend.common.response.response_code import CustomResponse
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.core.path_conf import UPLOAD_DIR
from backend.database.db import CurrentSessionTransaction
from backend.utils.file_ops import upload_file

log = logging.getLogger(__name__)

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
        log.exception('解析 PDF 失败')
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
        log.exception('智能提取失败')
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
            async for chunk_result in parse_service.extract_questions_stream(db, md_content, provider_id=4):
                yield f"data: {json.dumps(chunk_result, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(event_generator(), media_type='text/event-stream')
    except Exception as e:
        log.exception('智能流式提取失败')
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
) -> ResponseSchemaModel:
    """将前端确认后的智能解析结果批量入库"""
    try:
        user_id = request.user.id if hasattr(request, 'user') else 1
        data = await parse_service.smart_commit(
            db=db,
            bank_id=param.bank_id,
            materials_data=param.materials,
            questions_data=param.questions,
            user_id=user_id,
        )
        return response_base.success(data=data)
    except Exception as e:
        log.exception('解析结果提交入库失败')
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
) -> ResponseSchemaModel:
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
        log.exception('保存分段失败')
        return response_base.fail(res=CustomResponse(code=400, msg=f'保存失败: {e}'))
