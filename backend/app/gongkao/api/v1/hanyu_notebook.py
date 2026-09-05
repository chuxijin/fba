#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Path, Query, Request

from backend.database.db import CurrentSession
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.utils.timezone import timezone

router = APIRouter(dependencies=[DependsJwtAuth])


# ============ 词语本浏览与激活 ============

@router.get('/books', summary='获取可用的词语本列表', response_model=ResponseSchemaModel)
async def hanyu_list_wordbooks(db: CurrentSession):
    """获取所有词语本列表"""
    from backend.app.gongkao.crud.crud_hanyu_wordbook import hanyu_wordbook_dao

    books = await hanyu_wordbook_dao.select_models(db)
    return response_base.success(data=books)


@router.post('/books/{book_id}/start', summary='开始学习词语本')
async def hanyu_start_book(
    request: Request,
    db: CurrentSession,
    book_id: Annotated[int, Path(description='词语本 ID')],
):
    """开始学习某词语本（设为当前活跃）"""
    from backend.app.gongkao.crud.crud_hanyu_user_book import hanyu_user_book_dao

    user_id = request.user.id

    await hanyu_user_book_dao.deactivate_all(db, user_id)

    ub = await hanyu_user_book_dao.get_by_user_and_book(db, user_id, book_id)
    if ub:
        ub.is_active = True
        ub.finished_at = None
        await db.commit()
        await db.refresh(ub)
    else:
        from backend.app.gongkao.model import GkHanyuUserBook
        ub = GkHanyuUserBook(
            user_id=user_id,
            book_id=book_id,
            is_active=True,
            started_at=timezone.now(),
        )
        db.add(ub)
        await db.commit()
        await db.refresh(ub)

    return response_base.success(data={'id': ub.id, 'book_id': ub.book_id, 'is_active': ub.is_active})


@router.post('/books/{book_id}/finish', summary='完成/放弃词语本')
async def hanyu_finish_book(
    request: Request,
    db: CurrentSession,
    book_id: Annotated[int, Path(description='词语本 ID')],
):
    """完成或放弃学习某词语本"""
    from backend.app.gongkao.crud.crud_hanyu_user_book import hanyu_user_book_dao

    ub = await hanyu_user_book_dao.get_by_user_and_book(db, request.user.id, book_id)
    if ub:
        ub.is_active = False
        ub.finished_at = timezone.now()
        await db.commit()
    return response_base.success()


@router.get('/books/{book_id}/entries', summary='获取词语本的条目列表', response_model=ResponseSchemaModel)
async def hanyu_list_wordbook_entries(
    db: CurrentSession,
    book_id: Annotated[int, Path(description='词语本 ID')],
):
    """获取词语本的所有条目（含关联的 gk_hanyu 数据）"""
    from sqlalchemy import select
    from backend.app.gongkao.model import GkHanyuWordbookEntry, GkHanyu

    stmt = (
        select(GkHanyuWordbookEntry, GkHanyu)
        .join(GkHanyu, GkHanyu.id == GkHanyuWordbookEntry.hanyu_id)
        .where(GkHanyuWordbookEntry.wordbook_id == book_id)
        .order_by(GkHanyuWordbookEntry.sort_order)
    )
    result = await db.execute(stmt)
    rows = result.all()
    data = [
        {
            'entry_id': entry.id,
            'hanyu_id': hanyu.id,
            'group_name': entry.group_name,
            'category': entry.category,
            'word': hanyu.name,
            'pinyin': hanyu.pinyin,
            'type': hanyu.type,
            'meaning': entry.meaning,
            'commentary': entry.commentary,
            'example': entry.example,
            'definition_info': hanyu.definition_info,
            'detail_means': hanyu.detail_means,
        }
        for entry, hanyu in rows
    ]
    return response_base.success(data=data)


# ============ 学习核心 ============

@router.get('/session', summary='获取今日学习会话')
async def hanyu_get_study_session(
    request: Request,
    db: CurrentSession,
    mode: Annotated[str, Query(description='模式: all-所有, learn-仅新词, review-仅复习')] = 'all',
):
    """获取今日学习会话（待复习、新词或全部）"""
    from backend.app.gongkao.service.hanyu_study_service import hanyu_study_service

    data = await hanyu_study_service.get_study_session(db=db, user_id=request.user.id, mode=mode)
    return response_base.success(data=data)


@router.get('/stats', summary='获取学习统计')
async def hanyu_get_study_stats(request: Request, db: CurrentSession):
    """获取学习统计数据"""
    from backend.app.gongkao.service.hanyu_study_service import hanyu_study_service

    data = await hanyu_study_service.get_study_stats(db=db, user_id=request.user.id)
    return response_base.success(data=data)


# ============ 复习 ============

@router.post('/review', summary='提交复习结果', response_model=ResponseSchemaModel, name='hanyu_submit_review')
async def hanyu_submit_review(
    request: Request,
    db: CurrentSession,
    hanyu_id: Annotated[int, Query(description='汉语词汇 ID')],
    rating: Annotated[int, Query(ge=1, le=4, description='评分(1 Again 2 Hard 3 Good 4 Easy)')],
    review_mode: Annotated[str, Query(description='学习模式')] = 'word',
    duration_ms: Annotated[int | None, Query(description='耗时(毫秒)')] = None,
):
    """提交词语复习评分"""
    from backend.app.gongkao.schema.hanyu_review import SubmitReviewParam
    from backend.app.gongkao.service.hanyu_review_service import hanyu_review_service

    obj = SubmitReviewParam(hanyu_id=hanyu_id, rating=rating, review_mode=review_mode, duration_ms=duration_ms)
    result = await hanyu_review_service.submit_review(db=db, user_id=request.user.id, obj=obj)
    return response_base.success(data=result)


@router.get('/review/forecast/{hanyu_id}', summary='预览复习时间', response_model=ResponseSchemaModel)
async def hanyu_review_forecast(
    request: Request,
    db: CurrentSession,
    hanyu_id: Annotated[int, Path(description='汉语词汇 ID')],
):
    """预览各评分对应的下次复习时间"""
    from backend.app.gongkao.service.hanyu_review_service import hanyu_review_service

    result = await hanyu_review_service.get_review_forecast(db=db, user_id=request.user.id, hanyu_id=hanyu_id)
    return response_base.success(data=result)


# ============ 收藏 ============

@router.post('/star', summary='切换收藏')
async def hanyu_toggle_star(
    request: Request,
    db: CurrentSession,
    hanyu_id: Annotated[int, Query(description='汉语词汇 ID')],
    is_starred: Annotated[bool, Query(description='是否收藏')],
):
    """切换词语收藏状态"""
    from backend.app.gongkao.crud.crud_hanyu_user_word import hanyu_user_word_dao

    uw = await hanyu_user_word_dao.get_by_user_and_word(db, request.user.id, hanyu_id)
    if uw:
        uw.is_starred = is_starred
        await db.commit()
    return response_base.success()


# ============ 打卡 ============

@router.get('/checkin/today', summary='今日打卡状态', response_model=ResponseSchemaModel)
async def hanyu_today_checkin(request: Request, db: CurrentSession):
    """获取今日打卡状态"""
    from backend.app.gongkao.service.hanyu_checkin_service import hanyu_checkin_service

    result = await hanyu_checkin_service.get_today_status(db=db, user_id=request.user.id)
    return response_base.success(data=result)


@router.get('/checkin/streak', summary='连续打卡信息')
async def hanyu_streak_info(request: Request, db: CurrentSession):
    """获取连续打卡信息"""
    from backend.app.gongkao.service.hanyu_checkin_service import hanyu_checkin_service

    result = await hanyu_checkin_service.get_streak_info(db=db, user_id=request.user.id)
    return response_base.success(data=result)


@router.get('/checkin/history', summary='打卡历史')
async def hanyu_checkin_history(
    request: Request,
    db: CurrentSession,
    year: Annotated[int, Query(description='年份')],
    month: Annotated[int, Query(description='月份')],
):
    """获取打卡历史记录"""
    from backend.app.gongkao.service.hanyu_checkin_service import hanyu_checkin_service

    result = await hanyu_checkin_service.get_checkin_history(
        db=db, user_id=request.user.id, year=year, month=month
    )
    return response_base.success(data=result)


# ============ 设置 ============

@router.get('/settings', summary='获取学习设置')
async def hanyu_get_setting(request: Request, db: CurrentSession):
    """获取用户学习设置"""
    from backend.app.gongkao.crud.crud_hanyu_user_setting import hanyu_user_setting_dao
    from backend.app.gongkao.schema.hanyu_setting import GetHanyuSettingDetail

    setting = await hanyu_user_setting_dao.get_or_create(db, request.user.id)
    return response_base.success(data=GetHanyuSettingDetail.model_validate(setting))


@router.put('/settings', summary='更新学习设置')
async def hanyu_update_setting(request: Request, db: CurrentSession):
    """更新用户学习设置"""
    from backend.app.gongkao.crud.crud_hanyu_user_setting import hanyu_user_setting_dao
    from backend.app.gongkao.schema.hanyu_setting import GetHanyuSettingDetail, UpdateHanyuSettingParam

    body = await request.json()
    obj = UpdateHanyuSettingParam(**body)
    setting = await hanyu_user_setting_dao.get_or_create(db, request.user.id)
    update_data = obj.model_dump(exclude_unset=True)
    if update_data:
        await hanyu_user_setting_dao.update_model(db, setting.id, update_data)
        await db.refresh(setting)
    return response_base.success(data=GetHanyuSettingDetail.model_validate(setting))


# ============ 待复习 ============

@router.get('/due', summary='待复习词语列表', response_model=ResponseSchemaModel)
async def hanyu_due_words(
    request: Request,
    db: CurrentSession,
    limit: int = 20,
):
    """获取今日待复习的词语"""
    from sqlalchemy import select
    from backend.app.gongkao.model import GkHanyuUserWord, GkHanyuWordbookEntry, GkHanyu
    from backend.utils.timezone import timezone as tz

    now = tz.now()
    stmt = (
        select(GkHanyuUserWord, GkHanyuWordbookEntry, GkHanyu)
        .join(GkHanyuWordbookEntry, GkHanyuWordbookEntry.hanyu_id == GkHanyuUserWord.hanyu_id)
        .join(GkHanyu, GkHanyu.id == GkHanyuUserWord.hanyu_id)
        .where(GkHanyuUserWord.user_id == request.user.id)
        .where(GkHanyuUserWord.due <= now)
        .order_by(GkHanyuUserWord.due.asc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    rows = result.all()
    data = [
        {
            'hanyu_id': hanyu.id,
            'word': hanyu.name,
            'pinyin': hanyu.pinyin,
            'type': hanyu.type,
            'state': uw.state,
            'stability': uw.stability,
            'difficulty': uw.difficulty,
            'group_name': entry.group_name,
            'category': entry.category,
            'meaning': entry.meaning,
            'commentary': entry.commentary,
        }
        for uw, entry, hanyu in rows
    ]
    return response_base.success(data=data)
