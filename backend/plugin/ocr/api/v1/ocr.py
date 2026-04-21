#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, File, Form, UploadFile

from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.plugin.ocr.schema.ocr import OCRRecognizeResult, OCRRecognizeScene
from backend.plugin.ocr.service.ocr_service import ocr_service

router = APIRouter()


@router.post('/recognize', summary='图片文字识别', dependencies=[DependsJwtAuth])
async def recognize_images(
    files: Annotated[list[UploadFile], File(description='待识别图片')],  # type: ignore[valid-type]
    scene: Annotated[OCRRecognizeScene, Form(description='识别场景')] = 'general',
) -> ResponseSchemaModel[OCRRecognizeResult]:
    """
    识别图片中的文字

    :param files: 图片文件列表
    :param scene: 识别场景
    :return:
    """
    result = await ocr_service.recognize_upload_files(files=files, scene=scene)
    return response_base.success(
        data=OCRRecognizeResult(
            provider=result.provider,
            text=result.text,
            lines=result.lines,
            elapsed_ms=result.elapsed_ms,
        )
    )
