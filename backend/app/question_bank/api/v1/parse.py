#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import logging
from typing import Annotated, Any

from fastapi import APIRouter, File, Form, Query, Request, UploadFile
from fastapi.responses import FileResponse, StreamingResponse

from backend.app.question_bank.schema.parse import SaveSegmentsParam, SmartCommitParam
from backend.app.question_bank.service.parse_service import parse_service
from backend.common.response.response_code import CustomResponse
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.core.path_conf import UPLOAD_DIR
from backend.database.db import CurrentSessionTransaction

log = logging.getLogger(__name__)

router = APIRouter()


@router.post('/pdf', summary='上传并解析PDF试卷为Markdown', name='qbank_parse_pdf')
async def upload_and_parse_pdf(
    request: Request,
    file: Annotated[UploadFile, File()],
) -> Any:
    """上传 PDF 试卷，用 LlamaParse 智能提取 Markdown 和图片"""
    try:
        data = await parse_service.upload_and_parse_pdf_file(
            file=file,
            request_base_url=str(request.base_url),
        )
        return response_base.success(data=data)
    except ValueError as e:
        return response_base.fail(res=CustomResponse(code=400, msg=str(e)))
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
    try:
        data = await parse_service.smart_extract_file(
            db=db,
            file=file,
            bank_id=bank_id,
            request_base_url=str(request.base_url),
        )
        return response_base.success(data=data)
    except ValueError as e:
        return response_base.fail(res=CustomResponse(code=400, msg=str(e)))
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
    try:
        async def event_generator():
            async for chunk_result in parse_service.smart_extract_file_stream(
                db=db,
                file=file,
                bank_id=bank_id,
                request_base_url=str(request.base_url),
            ):
                yield f"data: {json.dumps(chunk_result, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(event_generator(), media_type='text/event-stream')
    except ValueError as e:
        return response_base.fail(res=CustomResponse(code=400, msg=str(e)))
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
        data = await parse_service.save_segments_to_disk(
            db=db,
            bank_id=param.bank_id,
            segments=param.segments,
        )
        return response_base.success(data=data)
    except ValueError as e:
        return response_base.fail(res=CustomResponse(code=400, msg=str(e)))
    except Exception as e:
        log.exception('保存分段失败')
        return response_base.fail(res=CustomResponse(code=400, msg=f'保存失败: {e}'))


# ============ 智能导入流水线 ============


@router.post(
    '/pipeline',
    summary='智能导入流水线（PDF/MD → Excel）',
    name='qbank_pipeline',
    dependencies=[DependsJwtAuth],
)
async def run_pipeline(
    request: Request,
    db: CurrentSessionTransaction,
    bank_id: Annotated[int, Form(...)],
    file: Annotated[UploadFile, File(...)],
    provider_id: Annotated[int, Form()] = 4,
) -> Any:
    """主流水线接口：上传 PDF/MD → SSE 流式推送进度 → 最终返回 Excel 下载链接"""
    try:
        async def event_generator():
            try:
                async for event in parse_service.run_pipeline_with_file(
                    db=db,
                    file=file,
                    bank_id=bank_id,
                    request_base_url=str(request.base_url),
                    provider_id=provider_id,
                ):
                    yield f'data: {json.dumps(event, ensure_ascii=False)}\n\n'
                yield 'data: [DONE]\n\n'
            except Exception as e:
                log.exception('流水线执行异常中断')
                yield f'data: {json.dumps({"type": "error", "message": f"系统发生崩溃: {str(e)}"}, ensure_ascii=False)}\n\n'

        return StreamingResponse(event_generator(), media_type='text/event-stream')
    except ValueError as e:
        return response_base.fail(res=CustomResponse(code=400, msg=str(e)))
    except Exception as e:
        log.exception('流水线启动失败')
        return response_base.fail(res=CustomResponse(code=400, msg=f'流水线启动失败: {e}'))


@router.get(
    '/pipeline/download',
    summary='下载流水线生成的 Excel',
    name='qbank_pipeline_download',
    dependencies=[DependsJwtAuth],
)
async def download_pipeline_excel(
    filename: Annotated[str, Query(description='Excel 文件名（如 pipeline_export/xxx.xlsx）')],
) -> Any:
    """下载流水线生成的 Excel 文件"""
    safe_name = filename.replace('\\', '/').replace('..', '')
    if not safe_name.startswith('pipeline_export/'):
        return response_base.fail(res=CustomResponse(code=400, msg='非法文件路径'))

    file_path = UPLOAD_DIR / safe_name
    if not file_path.exists():
        return response_base.fail(res=CustomResponse(code=404, msg='文件不存在'))

    return FileResponse(
        path=file_path,
        filename=file_path.name,
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )


@router.post(
    '/preview-segments',
    summary='预览 Markdown 分段结果（兜底）',
    name='qbank_preview_segments',
    dependencies=[DependsJwtAuth],
)
async def preview_segments(
    file: Annotated[UploadFile, File(...)],
) -> Any:
    """仅预览分段结果，不调用 AI。用于校验正则分段质量。支持上传 .md 文件，返回按题号切割的分段列表。"""
    try:
        data = await parse_service.preview_segments_from_file(file=file)
        return response_base.success(data=data)
    except ValueError as e:
        return response_base.fail(res=CustomResponse(code=400, msg=str(e)))
    except Exception as e:
        log.exception('预览分段失败')
        return response_base.fail(res=CustomResponse(code=400, msg=f'预览分段失败: {e}'))
