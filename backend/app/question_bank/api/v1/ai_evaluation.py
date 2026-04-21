#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, File, Path, Request, UploadFile

from backend.app.question_bank.schema.ai_evaluation import (
    PracticeAIEvaluationRead,
    SubjectiveAnswerOCRResult,
    TriggerPracticeAIEvaluationParam,
)
from backend.app.question_bank.service.ai_evaluation_service import practice_ai_evaluation_service
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction
from backend.plugin.ocr.service.ocr_service import ocr_service

router = APIRouter()


@router.post(
    '/ocr',
    summary='主观题拍照识别',
    name='qbank_ai_evaluation_subjective_ocr',
    dependencies=[DependsJwtAuth],
)
async def recognize_subjective_answer_images(
    files: Annotated[list[UploadFile], File(description='主观题答题图片')],  # type: ignore[valid-type]
) -> ResponseSchemaModel[SubjectiveAnswerOCRResult]:
    """主观题拍照识别"""
    result = await ocr_service.recognize_upload_files(
        files=files,
        scene='subjective_answer',
    )
    return response_base.success(data=SubjectiveAnswerOCRResult(text=result.text))


@router.get(
    '/records/{record_id}',
    summary='获取单题最新 AI 判分',
    name='qbank_ai_evaluation_get_record_latest',
    dependencies=[DependsJwtAuth],
)
async def get_record_evaluation(
    request: Request,
    db: CurrentSession,
    record_id: Annotated[int, Path(description='答题记录 ID')],
) -> ResponseSchemaModel[PracticeAIEvaluationRead]:
    """获取单题最新 AI 判分"""
    evaluation = await practice_ai_evaluation_service.get_latest_record_evaluation(
        db=db,
        record_id=record_id,
        user_id=request.user.id,
    )
    return response_base.success(data=PracticeAIEvaluationRead.model_validate(evaluation))


@router.post(
    '/records/{record_id}/judge',
    summary='手动触发单题 AI 判分',
    name='qbank_ai_evaluation_judge_record',
    dependencies=[DependsJwtAuth],
)
async def judge_record(
    request: Request,
    db: CurrentSessionTransaction,
    record_id: Annotated[int, Path(description='答题记录 ID')],
    obj: TriggerPracticeAIEvaluationParam,
) -> ResponseSchemaModel[PracticeAIEvaluationRead]:
    """手动触发单题 AI 判分"""
    evaluation = await practice_ai_evaluation_service.judge_record(
        db=db,
        record_id=record_id,
        user_id=request.user.id,
        force_regenerate=obj.force_regenerate,
    )
    return response_base.success(data=PracticeAIEvaluationRead.model_validate(evaluation))


@router.post(
    '/sessions/{session_id}/judge-subjective',
    summary='手动触发会话主观题 AI 判分',
    name='qbank_ai_evaluation_judge_session_subjective',
    dependencies=[DependsJwtAuth],
)
async def judge_session_subjective(
    request: Request,
    db: CurrentSessionTransaction,
    session_id: Annotated[int, Path(description='会话 ID')],
    obj: TriggerPracticeAIEvaluationParam,
) -> ResponseSchemaModel[list[PracticeAIEvaluationRead]]:
    """手动触发会话主观题 AI 判分"""
    evaluations = await practice_ai_evaluation_service.judge_session_subjective_records(
        db=db,
        session_id=session_id,
        user_id=request.user.id,
        force_regenerate=obj.force_regenerate,
    )
    return response_base.success(data=[PracticeAIEvaluationRead.model_validate(item) for item in evaluations])


@router.get(
    '/sessions/{session_id}/summary',
    summary='获取会话最新 AI 总结',
    name='qbank_ai_evaluation_get_session_summary',
    dependencies=[DependsJwtAuth],
)
async def get_session_summary(
    request: Request,
    db: CurrentSession,
    session_id: Annotated[int, Path(description='会话 ID')],
) -> ResponseSchemaModel[PracticeAIEvaluationRead]:
    """获取会话最新 AI 总结"""
    evaluation = await practice_ai_evaluation_service.get_latest_session_summary(
        db=db,
        session_id=session_id,
        user_id=request.user.id,
    )
    return response_base.success(data=PracticeAIEvaluationRead.model_validate(evaluation))


@router.post(
    '/sessions/{session_id}/summary',
    summary='生成会话 AI 总结',
    name='qbank_ai_evaluation_generate_session_summary',
    dependencies=[DependsJwtAuth],
)
async def generate_session_summary(
    request: Request,
    db: CurrentSessionTransaction,
    session_id: Annotated[int, Path(description='会话 ID')],
    obj: TriggerPracticeAIEvaluationParam,
) -> ResponseSchemaModel[PracticeAIEvaluationRead]:
    """生成会话 AI 总结"""
    evaluation = await practice_ai_evaluation_service.generate_session_summary(
        db=db,
        session_id=session_id,
        user_id=request.user.id,
        force_regenerate=obj.force_regenerate,
    )
    return response_base.success(data=PracticeAIEvaluationRead.model_validate(evaluation))
