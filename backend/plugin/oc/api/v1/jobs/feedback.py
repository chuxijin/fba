"""用户反馈 API"""

from fastapi import APIRouter, Request

from backend.common.response.response_schema import ResponseModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession
from backend.utils.request_parse import get_request_ip
from backend.plugin.oc.schema.feedback import FeedbackCreate
from backend.plugin.oc.service.feedback_service import feedback_service

router = APIRouter()


@router.post('', summary='提交反馈', dependencies=[DependsJwtAuth])
async def create_oc_feedback(
    request: Request,
    db: CurrentSession,
    obj: FeedbackCreate,
) -> ResponseModel:
    """提交用户反馈"""
    await feedback_service.create(
        db=db,
        obj=obj,
        user_id=request.user.id,
        ip=get_request_ip(request),
        user_agent=request.headers.get('User-Agent', '')[:500],
    )
    return response_base.success()
