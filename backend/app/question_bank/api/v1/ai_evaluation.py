#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, File, Path, Request, UploadFile

from backend.app.question_bank.schema.ai_evaluation import (
    PracticeAIEvaluationRead,
    SubjectiveAnswerOCRResult,
    TriggerPracticeAIEvaluationParam,
)
from backend.app.question_bank.crud.crud_practice_session import practice_session_dao
from backend.app.question_bank.service.ai_evaluation_service import practice_ai_evaluation_service
from backend.common.exception import errors
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction
from backend.plugin.agents.schema import GradingDetail, GradingStartResult
from backend.plugin.ocr.service.ocr_service import ocr_service

router = APIRouter()


async def _resolve_session_id(db: CurrentSession, session_key: str, user_id: int) -> int:
    """按 session_key 解析会话 ID 并校验归属"""
    session = await practice_session_dao.get_by_key(db, session_key)
    if not session:
        raise errors.NotFoundError(msg='会话不存在')
    if session.user_id != user_id:
        raise errors.ForbiddenError(msg='无权访问此会话')
    return session.id


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
    '/records/{record_id}/shenlun-agent',
    summary='启动申论 Agent 批改',
    name='qbank_ai_evaluation_start_shenlun_agent',
    dependencies=[DependsJwtAuth],
)
async def start_shenlun_agent_grading(
    request: Request,
    db: CurrentSession,
    record_id: Annotated[int, Path(description='答题记录 ID')],
) -> ResponseSchemaModel[GradingStartResult]:
    """启动申论 Agent 批改"""
    result = await practice_ai_evaluation_service.start_shenlun_agent_grading(
        db=db,
        record_id=record_id,
        user_id=request.user.id,
    )
    return response_base.success(data=result)


@router.get(
    '/agents/{task_id}',
    summary='获取申论 Agent 批改详情',
    name='qbank_ai_evaluation_get_shenlun_agent',
    dependencies=[DependsJwtAuth],
)
async def get_shenlun_agent_grading_detail(
    request: Request,
    db: CurrentSession,
    task_id: Annotated[int, Path(description='批改任务 ID')],
) -> ResponseSchemaModel[GradingDetail]:
    """获取申论 Agent 批改详情"""
    detail = await practice_ai_evaluation_service.get_shenlun_agent_grading_detail(
        db=db,
        task_id=task_id,
        user_id=request.user.id,
    )
    return response_base.success(data=detail)


@router.post(
    '/sessions/{session_key}/judge-subjective',
    summary='手动触发会话主观题 AI 判分',
    name='qbank_ai_evaluation_judge_session_subjective',
    dependencies=[DependsJwtAuth],
)
async def judge_session_subjective(
    request: Request,
    db: CurrentSessionTransaction,
    session_key: Annotated[str, Path(description='会话 Key')],
    obj: TriggerPracticeAIEvaluationParam,
) -> ResponseSchemaModel[list[PracticeAIEvaluationRead]]:
    """手动触发会话主观题 AI 判分"""
    sid = await _resolve_session_id(db, session_key, request.user.id)
    evaluations = await practice_ai_evaluation_service.judge_session_subjective_records(
        db=db,
        session_id=sid,
        user_id=request.user.id,
        force_regenerate=obj.force_regenerate,
    )
    return response_base.success(data=[PracticeAIEvaluationRead.model_validate(item) for item in evaluations])


@router.get(
    '/sessions/{session_key}/summary',
    summary='获取会话最新 AI 总结',
    name='qbank_ai_evaluation_get_session_summary',
    dependencies=[DependsJwtAuth],
)
async def get_session_summary(
    request: Request,
    db: CurrentSession,
    session_key: Annotated[str, Path(description='会话 Key')],
) -> ResponseSchemaModel[PracticeAIEvaluationRead]:
    """获取会话最新 AI 总结"""
    sid = await _resolve_session_id(db, session_key, request.user.id)
    evaluation = await practice_ai_evaluation_service.get_latest_session_summary(
        db=db,
        session_id=sid,
        user_id=request.user.id,
    )
    return response_base.success(data=PracticeAIEvaluationRead.model_validate(evaluation))


@router.post(
    '/sessions/{session_key}/summary',
    summary='生成会话 AI 总结',
    name='qbank_ai_evaluation_generate_session_summary',
    dependencies=[DependsJwtAuth],
)
async def generate_session_summary(
    request: Request,
    db: CurrentSessionTransaction,
    session_key: Annotated[str, Path(description='会话 Key')],
    obj: TriggerPracticeAIEvaluationParam,
) -> ResponseSchemaModel[PracticeAIEvaluationRead]:
    """生成会话 AI 总结"""
    sid = await _resolve_session_id(db, session_key, request.user.id)
    evaluation = await practice_ai_evaluation_service.generate_session_summary(
        db=db,
        session_id=sid,
        user_id=request.user.id,
        force_regenerate=obj.force_regenerate,
    )
    return response_base.success(data=PracticeAIEvaluationRead.model_validate(evaluation))
