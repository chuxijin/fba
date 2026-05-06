#!/usr/bin/env python3
import json
import logging

from typing import Annotated, Any

from fastapi import APIRouter, File, Form, Query, Request, UploadFile
from fastapi.responses import FileResponse, StreamingResponse

from backend.app.question_bank.schema.parse import OCRMarkdownRecoverParam, ReviewJobUpdateParam
from backend.app.question_bank.service.parse_service import parse_service
from backend.common.exception import errors
from backend.common.response.response_code import CustomResponse
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.core.path_conf import UPLOAD_DIR
from backend.database.db import CurrentSessionTransaction
from backend.utils.path_safety import safe_path_segment

log = logging.getLogger(__name__)

router = APIRouter()


@router.post('/pdf', summary='上传并解析PDF试卷为Markdown', name='qbank_parse_pdf')
async def upload_and_parse_pdf(
    file: Annotated[UploadFile, File()],
) -> Any:
    """上传 PDF 试卷并提取 Markdown 和图片"""
    try:
        data = await parse_service.upload_and_parse_pdf_file(
            file=file,
        )
        return response_base.success(data=data)
    except ValueError as e:
        return response_base.fail(res=CustomResponse(code=400, msg=str(e)))
    except Exception as e:
        log.exception('解析 PDF 失败')
        return response_base.fail(res=CustomResponse(code=400, msg=f'解析失败: {e}'))


@router.post(
    '/pdf-markdown',
    summary='仅将 PDF 转为 Markdown',
    name='qbank_parse_pdf_markdown_only',
    dependencies=[DependsJwtAuth],
)
async def convert_pdf_to_markdown_only(
    db: CurrentSessionTransaction,
    bank_id: Annotated[int, Form(...)],
    file: Annotated[UploadFile, File(...)],
) -> ResponseSchemaModel:
    """仅上传 PDF 并转换 Markdown，不执行后续 AI 解析"""
    try:
        data = await parse_service.convert_pdf_to_markdown_only(
            db=db,
            file=file,
            bank_id=bank_id,
        )
        return response_base.success(data=data)
    except ValueError as e:
        return response_base.fail(res=CustomResponse(code=400, msg=str(e)))
    except Exception as e:
        log.error(f'PDF 转 Markdown 失败: {e}')
        return response_base.fail(res=CustomResponse(code=400, msg=f'PDF 转 Markdown 失败: {e}'))


@router.post(
    '/review-jobs/stream',
    summary='流式创建 AI 解析审核任务',
    name='qbank_parse_review_job_create_stream',
    dependencies=[DependsJwtAuth],
)
async def create_review_job_stream(
    request: Request,
    db: CurrentSessionTransaction,
    bank_id: Annotated[int, Form(...)],
    file: Annotated[UploadFile, File(...)],
    provider_id: Annotated[int, Form()] = 4,
    extract_mode: Annotated[str, Form()] = 'question',
) -> StreamingResponse:
    """流式创建 AI 解析审核任务"""
    try:
        if not hasattr(request, 'user') or not request.user:
            raise errors.RequestError(msg='未获取到用户身份信息，请重新登录')
        user_id = request.user.id

        async def event_generator() -> Any:
            try:
                async for event in parse_service.create_review_job_stream(
                    db=db,
                    file=file,
                    bank_id=bank_id,
                    provider_id=provider_id,
                    user_id=user_id,
                    extract_mode=extract_mode,
                ):
                    yield f'data: {json.dumps(event, ensure_ascii=False)}\n\n'
                yield 'data: [DONE]\n\n'
            except Exception as e:
                log.exception('流式创建审核任务异常中断')
                yield f'data: {json.dumps({"type": "error", "message": str(e)}, ensure_ascii=False)}\n\n'

        return StreamingResponse(event_generator(), media_type='text/event-stream')
    except ValueError as e:
        error_message = str(e)

        async def value_error_generator() -> Any:
            yield f'data: {json.dumps({"type": "error", "message": error_message}, ensure_ascii=False)}\n\n'

        return StreamingResponse(value_error_generator(), media_type='text/event-stream')
    except Exception as e:
        log.exception('流式创建审核任务启动失败')
        error_message = str(e)

        async def error_generator() -> Any:
            yield f'data: {json.dumps({"type": "error", "message": error_message}, ensure_ascii=False)}\n\n'

        return StreamingResponse(error_generator(), media_type='text/event-stream')


@router.post(
    '/pdf-markdown/recover',
    summary='从云端 OCR JobID 恢复 Markdown',
    name='qbank_parse_pdf_markdown_recover',
    dependencies=[DependsJwtAuth],
)
async def recover_pdf_markdown_from_ocr_job(
    db: CurrentSessionTransaction,
    param: OCRMarkdownRecoverParam,
) -> ResponseSchemaModel:
    """从云端 OCR JobID 恢复 Markdown"""
    try:
        data = await parse_service.recover_markdown_from_ocr_job(
            db=db,
            bank_id=param.bank_id,
            job_id=param.job_id,
            download_images=param.download_images,
        )
        return response_base.success(data=data)
    except ValueError as e:
        return response_base.fail(res=CustomResponse(code=400, msg=str(e)))
    except Exception as e:
        log.exception('恢复 OCR Markdown 失败')
        return response_base.fail(res=CustomResponse(code=400, msg=f'恢复 Markdown 失败: {e}'))


@router.get(
    '/review-jobs/{job_id}',
    summary='获取 AI 解析审核任务',
    name='qbank_parse_review_job_detail',
    dependencies=[DependsJwtAuth],
)
async def get_review_job(job_id: str) -> ResponseSchemaModel:
    """获取 AI 解析审核任务"""
    try:
        data = await parse_service.get_review_job(job_id)
        return response_base.success(data=data)
    except ValueError as e:
        return response_base.fail(res=CustomResponse(code=404, msg=str(e)))
    except Exception as e:
        log.exception('获取审核任务失败')
        return response_base.fail(res=CustomResponse(code=400, msg=f'获取审核任务失败: {e}'))


@router.put(
    '/review-jobs/{job_id}',
    summary='保存 AI 解析审核任务',
    name='qbank_parse_review_job_update',
    dependencies=[DependsJwtAuth],
)
async def update_review_job(job_id: str, param: ReviewJobUpdateParam) -> ResponseSchemaModel:
    """保存 AI 解析审核任务"""
    try:
        data = await parse_service.update_review_job(job_id, param)
        return response_base.success(data=data)
    except ValueError as e:
        return response_base.fail(res=CustomResponse(code=404, msg=str(e)))
    except Exception as e:
        log.exception('保存审核任务失败')
        return response_base.fail(res=CustomResponse(code=400, msg=f'保存审核任务失败: {e}'))


@router.post(
    '/review-jobs/{job_id}/commit',
    summary='提交审核任务入库',
    name='qbank_parse_review_job_commit',
    dependencies=[DependsJwtAuth],
)
async def commit_review_job(
    request: Request,
    db: CurrentSessionTransaction,
    job_id: str,
) -> ResponseSchemaModel:
    """提交审核任务入库"""
    try:
        if not hasattr(request, 'user') or not request.user:
            raise errors.RequestError(msg='未获取到用户身份信息，请重新登录')
        user_id = request.user.id
        data = await parse_service.commit_review_job(db=db, job_id=job_id, user_id=user_id)
        return response_base.success(data=data)
    except ValueError as e:
        return response_base.fail(res=CustomResponse(code=404, msg=str(e)))
    except Exception as e:
        log.exception('提交审核任务失败')
        return response_base.fail(res=CustomResponse(code=400, msg=f'提交审核任务失败: {e}'))


@router.post(
    '/review-jobs/{job_id}/excel',
    summary='导出审核任务 Excel',
    name='qbank_parse_review_job_excel',
    dependencies=[DependsJwtAuth],
)
async def export_review_job_excel(job_id: str) -> ResponseSchemaModel:
    """导出审核任务 Excel"""
    try:
        data = await parse_service.export_review_job_excel(job_id)
        return response_base.success(data=data)
    except ValueError as e:
        return response_base.fail(res=CustomResponse(code=404, msg=str(e)))
    except Exception as e:
        log.exception('导出审核任务 Excel 失败')
        return response_base.fail(res=CustomResponse(code=400, msg=f'导出审核任务 Excel 失败: {e}'))


@router.get(
    '/files/download',
    summary='下载解析生成文件',
    name='qbank_parse_file_download',
    dependencies=[DependsJwtAuth],
)
async def download_parse_file(
    filename: Annotated[str, Query(description='文件名（如 parse_review/xxx.xlsx）')],
) -> Any:
    """下载解析生成的文件"""
    parts = filename.replace('\\', '/').split('/')
    safe_parts = [safe_path_segment(part) for part in parts if part and part != '.']
    safe_name = '/'.join(safe_parts)
    if not (safe_name.startswith(('parse_export/', 'parse_review/'))):
        return response_base.fail(res=CustomResponse(code=400, msg='非法文件路径'))

    file_path = UPLOAD_DIR / safe_name
    if not file_path.exists():
        return response_base.fail(res=CustomResponse(code=404, msg='文件不存在'))

    media_type = 'application/octet-stream'
    if file_path.suffix.lower() == '.xlsx':
        media_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    if file_path.suffix.lower() == '.md':
        media_type = 'text/markdown; charset=utf-8'
    if file_path.suffix.lower() == '.txt':
        media_type = 'text/plain; charset=utf-8'

    return FileResponse(path=file_path, filename=file_path.name, media_type=media_type)
