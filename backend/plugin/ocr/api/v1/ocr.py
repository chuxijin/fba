#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, File, Form, UploadFile

from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.plugin.ocr.schema.ocr import (
    OCRDocumentOutputFormat,
    OCRDocumentParseResult,
    OCRDocumentRecoverParam,
    OCRRecognizeResult,
    OCRRecognizeScene,
)
from backend.plugin.ocr.service.ocr_service import ocr_service

router = APIRouter()


@router.post('/recognize', summary='图片文字识别', dependencies=[DependsJwtAuth])
async def recognize_images(
    files: Annotated[list[UploadFile], File(description='待识别图片')],  # type: ignore[valid-type]
    scene: Annotated[OCRRecognizeScene, Form(description='识别场景')] = 'general',
    provider: Annotated[str | None, Form(description='OCR provider')] = None,
) -> ResponseSchemaModel[OCRRecognizeResult]:
    """
    识别图片中的文字

    :param files: 图片文件列表
    :param scene: 识别场景
    :param provider: OCR provider
    :return:
    """
    result = await ocr_service.recognize_upload_files(files=files, scene=scene, provider=provider)
    return response_base.success(
        data=OCRRecognizeResult(
            provider=result.provider,
            text=result.text,
            lines=result.lines,
            elapsed_ms=result.elapsed_ms,
        )
    )


@router.post('/documents/parse', summary='文档 OCR 解析', dependencies=[DependsJwtAuth])
async def parse_document(
    file: Annotated[UploadFile, File(description='待解析文档')],
    provider: Annotated[str | None, Form(description='OCR provider')] = None,
    output_format: Annotated[OCRDocumentOutputFormat, Form(description='输出格式')] = 'markdown',
    wait: Annotated[bool, Form(description='是否等待云端完成')] = True,
    images_dir_name: Annotated[str | None, Form(description='图片保存目录名')] = None,
) -> ResponseSchemaModel[OCRDocumentParseResult]:
    """
    解析文档为 Markdown 或纯文本

    :param file: 待解析文档
    :param provider: OCR provider
    :param output_format: 输出格式
    :param wait: 是否等待云端完成
    :param images_dir_name: 图片保存目录名
    :return:
    """
    result = await ocr_service.parse_upload_document(
        file=file,
        provider=provider,
        output_format=output_format,
        wait=wait,
        images_dir_name=images_dir_name,
    )
    return response_base.success(
        data=OCRDocumentParseResult(
            provider=result.provider,
            job_id=result.job_id,
            status=result.status,
            output_format=result.output_format,
            content=result.content,
            elapsed_ms=result.elapsed_ms,
        )
    )


@router.post('/documents/recover', summary='恢复云端文档 OCR 结果', dependencies=[DependsJwtAuth])
async def recover_document(
    param: OCRDocumentRecoverParam,
) -> ResponseSchemaModel[OCRDocumentParseResult]:
    """
    恢复云端文档解析结果

    :param param: 恢复参数
    :return:
    """
    result = await ocr_service.recover_document(
        job_id=param.job_id,
        provider=param.provider,
        output_format=param.output_format,
        images_dir_name=param.images_dir_name,
        download_images=param.download_images,
    )
    return response_base.success(
        data=OCRDocumentParseResult(
            provider=result.provider,
            job_id=result.job_id,
            status=result.status,
            output_format=result.output_format,
            content=result.content,
            elapsed_ms=result.elapsed_ms,
        )
    )
