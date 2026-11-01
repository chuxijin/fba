from fastapi import APIRouter, Request

from backend.app.question_bank_v2.schema.practice import GetPracticeSessionDetail
from backend.app.question_bank_v2.schema.study_goal import CreateGoalExamParam, DomainCode, GetExamTarget
from backend.app.question_bank_v2.service.study_goal_service import study_goal_service
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get(
    '/exam-targets',
    summary='获取有效备考目标及组卷模板',
    name='qbank_v2_get_exam_targets',
    dependencies=[DependsJwtAuth],
)
async def get_exam_targets(
    db: CurrentSession, domain_code: DomainCode | None = None
) -> ResponseSchemaModel[list[GetExamTarget]]:
    return response_base.success(data=await study_goal_service.get_targets(db=db, domain_code=domain_code))


@router.get(
    '/exam-target-catalog',
    summary='获取公开备考目标目录，不含组卷资源',
    name='qbank_v2_get_exam_target_catalog',
)
async def get_exam_target_catalog(
    db: CurrentSession, domain_code: DomainCode | None = None
) -> ResponseSchemaModel[list[GetExamTarget]]:
    targets = await study_goal_service.get_targets(db=db, domain_code=domain_code)
    return response_base.success(
        data=[
            target.model_copy(update={'config': target.config.model_copy(update={'templates': []})})
            for target in targets
        ]
    )


@router.post(
    '/goal-exams',
    summary='按当前备考目标创建考试',
    name='qbank_v2_create_goal_exam',
    dependencies=[DependsJwtAuth],
)
async def create_goal_exam(
    request: Request,
    db: CurrentSessionTransaction,
    obj: CreateGoalExamParam,
) -> ResponseSchemaModel[GetPracticeSessionDetail]:
    return response_base.success(data=await study_goal_service.create_exam(db=db, user_id=request.user.id, obj=obj))
