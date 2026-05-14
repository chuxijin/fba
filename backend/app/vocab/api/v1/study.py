#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Path, Query, Request

from backend.app.vocab.schema.review import (
    GetStudySession,
    GetStudyStats,
    ReviewForecast,
    ReviewResult,
    SubmitReviewParam,
)
from backend.app.vocab.schema.user_book import CreateUserBookParam, GetUserBookDetail, StartBookParam
from backend.app.vocab.schema.user_word import ToggleStarParam
from backend.app.vocab.service.review_service import review_service
from backend.app.vocab.service.study_service import study_service
from backend.app.vocab.crud.crud_user_book import user_book_dao
from backend.app.vocab.crud.crud_user_word import user_word_dao
from backend.app.vocab.schema.book import GetBookListItem
from backend.app.vocab.service.book_service import book_service
from backend.common.pagination import DependsPagination
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession
from backend.utils.timezone import timezone

router = APIRouter(prefix='/vocab', tags=['单词本学习'], dependencies=[DependsJwtAuth])


# ============ 词书浏览 ============
@router.get('/books', summary='浏览可选词书列表', dependencies=[DependsPagination])
async def browse_books(
    db: CurrentSession,
    category: Annotated[str | None, Query(description='分类过滤')] = None,
) -> ResponseModel:
    """浏览可选词书列表（上架状态）"""
    data = await book_service.get_book_list(db=db, category=category, status=1)
    return response_base.success(data=data)


# ============ 用户词书 ============
@router.post('/books/{pk}/start', summary='开始学习词书')
async def start_book(
    request: Request,
    db: CurrentSession,
    pk: Annotated[int, Path(description='词书 ID')],
    obj: StartBookParam | None = None,
) -> ResponseSchemaModel[GetUserBookDetail]:
    """开始学习某词书（设为当前活跃）"""
    user_id = request.user.id

    # 先取消其他活跃词书
    await user_book_dao.deactivate_all(db, user_id)

    # 查看是否已有记录
    ub = await user_book_dao.get_by_user_and_book(db, user_id, pk)
    if ub:
        await user_book_dao.update_model(db, ub.id, {'is_active': True, 'finished_at': None})
        await db.refresh(ub)
    else:
        ub = await user_book_dao.create_model(
            db,
            CreateUserBookParam(
                user_id=user_id,
                book_id=pk,
                is_active=True,
                started_at=timezone.now(),
            ),
            commit=False,
        )
        await db.commit()
        await db.refresh(ub)

    return response_base.success(data=GetUserBookDetail.model_validate(ub))


@router.post('/books/{pk}/finish', summary='完成/放弃词书')
async def finish_book(
    request: Request,
    db: CurrentSession,
    pk: Annotated[int, Path(description='词书 ID')],
) -> ResponseModel:
    """完成或放弃学习某词书"""
    ub = await user_book_dao.get_by_user_and_book(db, request.user.id, pk)
    if ub:
        await user_book_dao.update_model(db, ub.id, {'is_active': False, 'finished_at': timezone.now()})
    return response_base.success()


@router.get('/books/mine', summary='我的词书列表', dependencies=[DependsPagination])
async def get_my_books(request: Request, db: CurrentSession) -> ResponseModel:
    """获取我的词书列表"""
    from backend.common.pagination import paging_data
    stmt = await user_book_dao.get_select_by_user(request.user.id)
    data = await paging_data(db, stmt)
    return response_base.success(data=data)


# ============ 学习核心 ============
@router.get('/study/session', summary='获取今日学习会话')
async def get_study_session(request: Request, db: CurrentSession) -> ResponseSchemaModel[GetStudySession]:
    """获取今日学习会话（待复习 + 新词）"""
    data = await study_service.get_study_session(db=db, user_id=request.user.id)
    return response_base.success(data=data)


@router.get('/study/stats', summary='获取学习统计')
async def get_study_stats(request: Request, db: CurrentSession) -> ResponseSchemaModel[GetStudyStats]:
    """获取学习统计数据"""
    data = await study_service.get_study_stats(db=db, user_id=request.user.id)
    return response_base.success(data=data)


@router.post('/study/review', summary='提交复习结果')
async def submit_review(
    request: Request,
    db: CurrentSession,
    obj: SubmitReviewParam,
) -> ResponseSchemaModel[ReviewResult]:
    """提交一次复习结果（FSRS 调度）"""
    data = await review_service.submit_review(db=db, user_id=request.user.id, obj=obj)
    return response_base.success(data=data)


@router.get('/study/review-forecast/{word_id}', summary='复习预测')
async def get_review_forecast(
    request: Request,
    db: CurrentSession,
    word_id: Annotated[int, Path(description='单词 ID')],
) -> ResponseSchemaModel[ReviewForecast]:
    """预览各评分对应的下次复习时间"""
    data = await review_service.get_review_forecast(db=db, user_id=request.user.id, word_id=word_id)
    return response_base.success(data=data)


# ============ 收藏 ============
@router.post('/star', summary='切换收藏')
async def toggle_star(request: Request, db: CurrentSession, obj: ToggleStarParam) -> ResponseModel:
    """切换单词收藏状态"""
    uw = await user_word_dao.get_by_user_and_word(db, request.user.id, obj.word_id)
    if uw:
        await user_word_dao.update_model(db, uw.id, {'is_starred': obj.is_starred})
    return response_base.success()
