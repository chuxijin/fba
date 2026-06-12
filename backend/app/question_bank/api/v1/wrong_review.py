#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Body, Depends, Path, Request

from backend.app.question_bank.crud.crud_wrong_review import custom_question_dao, review_dao
from backend.app.question_bank.schema.wrong_review import (
    CreateCustomQuestionParam,
    CreateReasonTagParam,
    CreateReviewParam,
    CustomQuestionQueryParam,
    GetCustomQuestionDetail,
    GetCustomQuestionListItem,
    GetReasonTagItem,
    GetReviewDetail,
    GetReviewListItem,
    ReviewQueryParam,
    UpdateCustomQuestionParam,
    GetReviewDashboard,
    TodayPendingItem,
)
from backend.app.question_bank.service.wrong_review_service import wrong_review_service
from backend.common.pagination import DependsPagination, PageData, paging_data
from backend.common.response.response_code import CustomResponse
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


# ───────────────── 看板统计 ─────────────────


@router.get(
    '/dashboard',
    summary='获取复盘看板数据',
    name='qbank_wrong_review_dashboard',
    dependencies=[DependsJwtAuth],
)
async def get_dashboard(
    request: Request,
    db: CurrentSession,
    cat_id: int | None = None,
    kp_cat_id: int | None = None,
) -> ResponseSchemaModel[GetReviewDashboard]:
    data = await wrong_review_service.get_dashboard(
        db=db,
        user_id=request.user.id,
        cat_id=cat_id,
        kp_cat_id=kp_cat_id,
    )
    return response_base.success(data=data)


@router.get(
    '/today-pending',
    summary='获取今日待复盘错题列表',
    name='qbank_wrong_review_today_pending',
    dependencies=[DependsJwtAuth],
)
async def get_today_pending(
    request: Request,
    db: CurrentSession,
) -> ResponseSchemaModel[list[TodayPendingItem]]:
    data = await wrong_review_service.get_today_pending_list(
        db=db,
        user_id=request.user.id,
    )
    return response_base.success(data=data)


# ───────────────── 错因标签 ─────────────────


@router.get(
    '/tags',
    summary='获取错因标签列表',
    name='qbank_wrong_review_tags_list',
    dependencies=[DependsJwtAuth],
)
async def list_tags(
    request: Request,
    db: CurrentSession,
) -> ResponseSchemaModel[list[GetReasonTagItem]]:
    tags = await wrong_review_service.list_tags(db=db, user_id=request.user.id)
    return response_base.success(data=[GetReasonTagItem.model_validate(t) for t in tags])


@router.post(
    '/tags',
    summary='创建自定义错因标签',
    name='qbank_wrong_review_tags_create',
    dependencies=[DependsJwtAuth],
)
async def create_tag(
    request: Request,
    db: CurrentSessionTransaction,
    obj: CreateReasonTagParam,
) -> ResponseSchemaModel[GetReasonTagItem]:
    tag = await wrong_review_service.create_tag(
        db=db,
        user_id=request.user.id,
        name=obj.name,
        color=obj.color,
    )
    return response_base.success(data=GetReasonTagItem.model_validate(tag))


@router.delete(
    '/tags/{pk}',
    summary='删除自定义错因标签',
    name='qbank_wrong_review_tags_delete',
    dependencies=[DependsJwtAuth],
)
async def delete_tag(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='标签 ID')],
) -> ResponseModel:
    count = await wrong_review_service.delete_tag(db=db, tag_id=pk, user_id=request.user.id)
    if count > 0:
        return response_base.success(res=CustomResponse(code=200, msg='删除成功'))
    return response_base.fail(res=CustomResponse(code=400, msg='删除失败'))


# ───────────────── 自定义错题 ─────────────────


@router.get(
    '/custom',
    summary='获取自定义错题列表',
    name='qbank_wrong_review_custom_list',
    dependencies=[DependsJwtAuth, DependsPagination],
)
async def list_custom_questions(
    request: Request,
    db: CurrentSession,
    query: Annotated[CustomQuestionQueryParam, Depends()],
) -> ResponseSchemaModel[PageData[GetCustomQuestionListItem]]:
    stmt = await wrong_review_service.list_custom_questions(
        db=db,
        user_id=request.user.id,
        category_id=query.category_id,
        source=query.source,
        keyword=query.keyword,
    )
    page_data = await paging_data(db, stmt, GetCustomQuestionListItem)
    return response_base.success(data=page_data)


@router.get(
    '/custom/{pk}',
    summary='获取自定义错题详情',
    name='qbank_wrong_review_custom_get',
    dependencies=[DependsJwtAuth],
)
async def get_custom_question(
    request: Request,
    db: CurrentSession,
    pk: Annotated[int, Path(description='错题 ID')],
) -> ResponseSchemaModel[GetCustomQuestionDetail]:
    question = await wrong_review_service.get_custom_question(
        db=db, custom_id=pk, user_id=request.user.id,
    )
    return response_base.success(data=GetCustomQuestionDetail.model_validate(question))


@router.post(
    '/custom',
    summary='创建自定义错题',
    name='qbank_wrong_review_custom_create',
    dependencies=[DependsJwtAuth],
)
async def create_custom_question(
    request: Request,
    db: CurrentSessionTransaction,
    obj: CreateCustomQuestionParam,
) -> ResponseSchemaModel[GetCustomQuestionDetail]:
    question = await wrong_review_service.create_custom_question(
        db=db,
        user_id=request.user.id,
        **obj.model_dump(exclude_unset=True),
    )
    return response_base.success(data=GetCustomQuestionDetail.model_validate(question))


@router.put(
    '/custom/{pk}',
    summary='更新自定义错题',
    name='qbank_wrong_review_custom_update',
    dependencies=[DependsJwtAuth],
)
async def update_custom_question(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='错题 ID')],
    obj: UpdateCustomQuestionParam,
) -> ResponseModel:
    count = await wrong_review_service.update_custom_question(
        db=db,
        custom_id=pk,
        user_id=request.user.id,
        data=obj.model_dump(exclude_unset=True),
    )
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete(
    '/custom',
    summary='批量删除自定义错题',
    name='qbank_wrong_review_custom_delete',
    dependencies=[DependsJwtAuth],
)
async def delete_custom_questions(
    request: Request,
    db: CurrentSessionTransaction,
    ids: Annotated[list[int], Body(description='错题 ID 列表')],
) -> ResponseModel:
    count = await wrong_review_service.delete_custom_questions(
        db=db, ids=ids, user_id=request.user.id,
    )
    if count > 0:
        return response_base.success(res=CustomResponse(code=200, msg=f'成功删除 {count} 条自定义错题'))
    return response_base.fail(res=CustomResponse(code=400, msg='删除失败'))


# ───────────────── 复盘记录 ─────────────────


@router.get(
    '/reviews',
    summary='获取复盘记录列表',
    name='qbank_wrong_review_list',
    dependencies=[DependsJwtAuth, DependsPagination],
)
async def list_reviews(
    request: Request,
    db: CurrentSession,
    query: Annotated[ReviewQueryParam, Depends()],
) -> ResponseSchemaModel[PageData[GetReviewListItem]]:
    stmt = await wrong_review_service.list_reviews(
        db=db,
        user_id=request.user.id,
        review_type=query.review_type,
        start_date=query.start_date,
        end_date=query.end_date,
    )
    page_data = await paging_data(db, stmt, GetReviewListItem)
    return response_base.success(data=page_data)


@router.post(
    '/reviews',
    summary='创建复盘记录',
    name='qbank_wrong_review_create',
    dependencies=[DependsJwtAuth],
)
async def create_review(
    request: Request,
    db: CurrentSessionTransaction,
    obj: CreateReviewParam,
) -> ResponseSchemaModel[GetReviewDetail]:
    review = await wrong_review_service.create_review(
        db=db,
        user_id=request.user.id,
        **obj.model_dump(exclude_unset=True),
    )
    return response_base.success(data=GetReviewDetail.model_validate(review))


@router.delete(
    '/reviews/{pk}',
    summary='删除复盘记录',
    name='qbank_wrong_review_delete',
    dependencies=[DependsJwtAuth],
)
async def delete_review(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='复盘 ID')],
) -> ResponseModel:
    count = await wrong_review_service.delete_review(
        db=db, review_id=pk, user_id=request.user.id,
    )
    if count > 0:
        return response_base.success(res=CustomResponse(code=200, msg='删除成功'))
    return response_base.fail(res=CustomResponse(code=400, msg='删除失败'))
