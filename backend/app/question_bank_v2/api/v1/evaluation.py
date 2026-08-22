from typing import Annotated

from fastapi import APIRouter, File, Path, Request, UploadFile

from backend.app.question_bank_v2.schema.evaluation import (
    EvaluationRunRead,
    SubjectiveAnswerOCRResult,
    TriggerEvaluationParam,
)
from backend.app.question_bank_v2.service.evaluation_service import evaluation_service
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction
from backend.plugin.agent.schema.grading import GradingRunRead, StartShenlunGradingResult
from backend.plugin.ocr.service.ocr_service import ocr_service

router = APIRouter(dependencies=[DependsJwtAuth])


@router.post('/ocr', summary='识别主观题答题图片', name='qbank_v2_subjective_answer_ocr')
async def recognize_subjective_answer(
    files: Annotated[list[UploadFile], File(description='主观题答题图片')],
) -> ResponseSchemaModel[SubjectiveAnswerOCRResult]:
    result = await ocr_service.recognize_upload_files(files=files, scene='subjective_answer')
    return response_base.success(data=SubjectiveAnswerOCRResult(text=result.text))


@router.get(
    '/attempts/{attempt_id}',
    summary='获取作答最新 AI 判分',
    name='qbank_v2_get_attempt_evaluation',
)
async def get_attempt_evaluation(
    request: Request,
    db: CurrentSession,
    attempt_id: Annotated[int, Path(gt=0, description='作答事实 ID')],
) -> ResponseSchemaModel[EvaluationRunRead]:
    data = await evaluation_service.get_latest_attempt(
        db=db,
        attempt_id=attempt_id,
        user_id=request.user.id,
    )
    return response_base.success(data=EvaluationRunRead.model_validate(data))


@router.post(
    '/attempts/{attempt_id}/judge',
    summary='触发作答 AI 判分',
    name='qbank_v2_judge_attempt',
)
async def judge_attempt(
    request: Request,
    db: CurrentSessionTransaction,
    attempt_id: Annotated[int, Path(gt=0, description='作答事实 ID')],
    obj: TriggerEvaluationParam,
) -> ResponseSchemaModel[EvaluationRunRead]:
    data = await evaluation_service.evaluate_attempt(
        db=db,
        attempt_id=attempt_id,
        user_id=request.user.id,
        force_regenerate=obj.force_regenerate,
        model_name=obj.model_name,
    )
    return response_base.success(data=EvaluationRunRead.model_validate(data))


@router.post(
    '/attempts/{attempt_id}/shenlun-agent',
    summary='启动申论 Agent 批改',
    name='qbank_v2_start_shenlun_agent',
)
async def start_shenlun_agent(
    request: Request,
    db: CurrentSessionTransaction,
    attempt_id: Annotated[int, Path(gt=0, description='作答事实 ID')],
) -> ResponseSchemaModel[StartShenlunGradingResult]:
    data = await evaluation_service.start_shenlun_agent(
        db=db,
        attempt_id=attempt_id,
        user_id=request.user.id,
    )
    return response_base.success(data=data)


@router.get(
    '/agents/{task_id}',
    summary='获取申论 Agent 批改详情',
    name='qbank_v2_get_shenlun_agent',
)
async def get_shenlun_agent(
    request: Request,
    db: CurrentSession,
    task_id: Annotated[int, Path(gt=0, description='Agent 任务 ID')],
) -> ResponseSchemaModel[GradingRunRead]:
    data = await evaluation_service.get_shenlun_agent(
        db=db,
        task_id=task_id,
        user_id=request.user.id,
    )
    return response_base.success(data=data)


@router.post(
    '/sessions/{session_key}/judge-subjective',
    summary='批量触发会话主观题 AI 判分',
    name='qbank_v2_judge_session_subjective',
)
async def judge_session_subjective(
    request: Request,
    db: CurrentSessionTransaction,
    session_key: Annotated[str, Path(min_length=8, max_length=64, description='会话标识')],
    obj: TriggerEvaluationParam,
) -> ResponseSchemaModel[list[EvaluationRunRead]]:
    data = await evaluation_service.evaluate_session_attempts(
        db=db,
        session_key=session_key,
        user_id=request.user.id,
        force_regenerate=obj.force_regenerate,
        model_name=obj.model_name,
    )
    return response_base.success(data=[EvaluationRunRead.model_validate(item) for item in data])


@router.get(
    '/sessions/{session_key}/summary',
    summary='获取会话最新 AI 总结',
    name='qbank_v2_get_session_evaluation_summary',
)
async def get_session_summary(
    request: Request,
    db: CurrentSession,
    session_key: Annotated[str, Path(min_length=8, max_length=64, description='会话标识')],
) -> ResponseSchemaModel[EvaluationRunRead]:
    data = await evaluation_service.get_latest_session_summary(
        db=db,
        session_key=session_key,
        user_id=request.user.id,
    )
    return response_base.success(data=EvaluationRunRead.model_validate(data))


@router.post(
    '/sessions/{session_key}/summary',
    summary='生成会话 AI 总结',
    name='qbank_v2_generate_session_evaluation_summary',
)
async def generate_session_summary(
    request: Request,
    db: CurrentSessionTransaction,
    session_key: Annotated[str, Path(min_length=8, max_length=64, description='会话标识')],
    obj: TriggerEvaluationParam,
) -> ResponseSchemaModel[EvaluationRunRead]:
    data = await evaluation_service.generate_session_summary(
        db=db,
        session_key=session_key,
        user_id=request.user.id,
        force_regenerate=obj.force_regenerate,
        model_name=obj.model_name,
    )
    return response_base.success(data=EvaluationRunRead.model_validate(data))
