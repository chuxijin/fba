from typing import Annotated, Literal

from fastapi import APIRouter, Path, Query, Request

from backend.app.question_bank_v2.schema.annotation import AnnotationContext, GetAnnotationsDetail, SaveAnnotationsParam
from backend.app.question_bank_v2.service.annotation_service import annotation_service
from backend.common.exception import errors
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter(dependencies=[DependsJwtAuth])


@router.get('/{question_id}/annotations', summary='读取个人文字标注', name='qbank_v2_get_annotations')
async def get_annotations(
    request: Request,
    db: CurrentSession,
    question_id: Annotated[int, Path(gt=0)],
    session_key: Annotated[str | None, Query(min_length=8, max_length=64)] = None,
    session_item_id: Annotated[int | None, Query(gt=0)] = None,
    source: Literal['latest', 'wrong'] = 'latest',
) -> ResponseSchemaModel[GetAnnotationsDetail]:
    if (session_key is None) != (session_item_id is None):
        raise errors.RequestError(msg='练习会话与投递题必须同时提供')
    obj = AnnotationContext(session_key=session_key, session_item_id=session_item_id, source=source)
    return response_base.success(
        data=await annotation_service.get(db=db, user_id=request.user.id, question_id=question_id, obj=obj)
    )


@router.put('/{question_id}/annotations', summary='保存个人高亮与批注', name='qbank_v2_save_annotations')
async def save_annotations(
    request: Request,
    db: CurrentSessionTransaction,
    question_id: Annotated[int, Path(gt=0)],
    obj: SaveAnnotationsParam,
) -> ResponseSchemaModel[GetAnnotationsDetail]:
    return response_base.success(
        data=await annotation_service.save(db=db, user_id=request.user.id, question_id=question_id, obj=obj)
    )
