#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
练习会话和答题记录接口

设计原则：
- 基于会话的答题流程：创建会话 → 答题 → 提交会话
- 支持多种练习模式：章节练习、随机练习、错题练习等
- 记录用户的答题历史和统计数据
"""
from typing import Annotated

from fastapi import APIRouter, Body, Path, Query, Request
from sqlalchemy import select

from backend.app.question_bank.crud.crud_practice_record import practice_record_dao
from backend.app.question_bank.crud.crud_practice_session import practice_session_dao
from backend.app.question_bank.model import QuestionBank
from backend.app.question_bank.schema.practice import (
    AnswerCardItem,
    BatchCreatePracticeRecordsParam,
    CreatePracticeRecordParam,
    CreatePracticeSessionParam,
    DailyPracticeStatistics,
    GetPracticeRecordDetail,
    GetPracticeRecordListItem,
    GetPracticeSessionDetail,
    GetPracticeSessionListItem,
    QuestionTypeStatistics,
    SessionSummaryData,
    SubmitPracticeSessionParam,
    UpdatePracticeSessionParam,
    UserPracticeStatistics,
)
from backend.app.question_bank.security import DependsCustomerAuth
from backend.common.pagination import DependsPagination, PageData, paging_data
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.auth_strategy import AuthUser
from backend.database.db import CurrentSession, CurrentSessionTransaction
from backend.utils.timezone import timezone

router = APIRouter()


# ============ 练习会话接口 ============


@router.post('', summary='创建练习会话', name='qbank_practice_create_session')
async def create_session(
    db: CurrentSessionTransaction,
    obj: CreatePracticeSessionParam,
    current_user: AuthUser = DependsCustomerAuth,
) -> ResponseSchemaModel[GetPracticeSessionDetail]:
    """
    创建练习会话

    用户开始练习时创建会话，记录本次练习的基本信息
    """
    session_dict = obj.model_dump()
    session_dict['start_time'] = timezone.now()
    session_dict['user_id'] = current_user.user_id
    session_dict['created_by'] = current_user.user_id

    # 查询题库名称并保存到 practice_name
    if session_dict.get('bank_id'):
        result = await db.execute(select(QuestionBank.name).where(QuestionBank.id == session_dict['bank_id']))
        bank_name = result.scalar_one_or_none()
        session_dict['practice_name'] = bank_name

    new_session = await practice_session_dao.create(db=db, obj_dict=session_dict)
    return response_base.success(data=GetPracticeSessionDetail.model_validate(new_session))


@router.get('/{pk}', summary='获取练习会话详情', name='qbank_practice_get_session')
async def get_session(
    db: CurrentSession,
    pk: Annotated[int, Path(description='会话 ID')],
    current_user: AuthUser = DependsCustomerAuth,
) -> ResponseSchemaModel[GetPracticeSessionDetail]:
    """获取练习会话详情"""
    session = await practice_session_dao.get(db=db, session_id=pk)
    if not session:
        return response_base.fail(msg='会话不存在')
    if session.user_id != current_user.user_id:
        return response_base.fail(msg='无权访问此会话')

    return response_base.success(data=GetPracticeSessionDetail.model_validate(session))


@router.get(
    '',
    summary='获取用户练习会话列表',
    name='qbank_practice_get_sessions',
    dependencies=[DependsPagination],
)
async def get_sessions(
    db: CurrentSession,
    current_user: AuthUser = DependsCustomerAuth,
    session_type: Annotated[str | None, Query(description='会话类型')] = None,
    status: Annotated[str | None, Query(description='状态')] = None,
) -> ResponseSchemaModel[PageData[GetPracticeSessionListItem]]:
    """
    获取用户的练习会话列表（分页）

    支持按会话类型和状态筛选
    """
    stmt = await practice_session_dao.get_select(
        user_id=current_user.user_id, session_type=session_type, status=status
    )
    page_data = await paging_data(db, stmt, GetPracticeSessionListItem)
    return response_base.success(data=page_data)


@router.get('/latest', summary='获取最新的进行中会话', name='qbank_practice_get_latest_session')
async def get_latest_session(
    db: CurrentSession,
    current_user: AuthUser = DependsCustomerAuth,
    bank_id: Annotated[int | None, Query(description='题库 ID')] = None,
    chapter_id: Annotated[int | None, Query(description='章节 ID')] = None,
) -> ResponseSchemaModel[GetPracticeSessionDetail]:
    """
    获取用户最新的进行中会话

    用于恢复未完成的练习
    """
    session = await practice_session_dao.get_latest_session(
        db=db, user_id=current_user.user_id, bank_id=bank_id, chapter_id=chapter_id
    )
    if not session:
        return response_base.fail(msg='没有进行中的会话')

    return response_base.success(data=GetPracticeSessionDetail.model_validate(session))


@router.put('/{pk}', summary='更新练习会话统计', name='qbank_practice_update_session')
async def update_session(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='会话 ID')],
    obj: UpdatePracticeSessionParam,
    current_user: AuthUser = DependsCustomerAuth,
) -> ResponseModel:
    """
    更新练习会话统计数据

    做题过程中实时更新已完成数量、正确数、错误数等
    """
    session = await practice_session_dao.get(db=db, session_id=pk)
    if not session:
        return response_base.fail(msg='会话不存在')
    if session.user_id != current_user.user_id:
        return response_base.fail(msg='无权操作此会话')

    update_dict = obj.model_dump(exclude_none=True)
    if update_dict:
        await practice_session_dao.update_statistics(
            db=db,
            session_id=pk,
            completed_count=update_dict.get('completed_count', session.completed_count),
            correct_count=update_dict.get('correct_count', session.correct_count),
            wrong_count=update_dict.get('wrong_count', session.wrong_count),
            total_time=update_dict.get('total_time', session.total_time),
        )
        return response_base.success()

    return response_base.fail(msg='没有需要更新的数据')


@router.post('/{pk}/submit', summary='提交练习会话', name='qbank_practice_submit_session')
async def submit_session(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='会话 ID')],
    obj: SubmitPracticeSessionParam,
    current_user: AuthUser = DependsCustomerAuth,
) -> ResponseModel:
    """
    提交练习会话

    标记会话为已完成，记录提交时间
    """
    session = await practice_session_dao.get(db=db, session_id=pk)
    if not session:
        return response_base.fail(msg='会话不存在')
    if session.user_id != current_user.user_id:
        return response_base.fail(msg='无权操作此会话')

    submit_time = timezone.now()
    count = await practice_session_dao.submit_session(db=db, session_id=pk, submit_time=submit_time, score=obj.score)

    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.post('/{pk}/abandon', summary='放弃练习会话', name='qbank_practice_abandon_session')
async def abandon_session(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='会话 ID')],
    current_user: AuthUser = DependsCustomerAuth,
) -> ResponseModel:
    """
    放弃练习会话

    用户中途退出练习时调用
    """
    session = await practice_session_dao.get(db=db, session_id=pk)
    if not session:
        return response_base.fail(msg='会话不存在')
    if session.user_id != current_user.user_id:
        return response_base.fail(msg='无权操作此会话')

    count = await practice_session_dao.abandon_session(db=db, session_id=pk)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete('/{pk}', summary='删除练习会话', name='qbank_practice_delete_session')
async def delete_session(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='会话 ID')],
    current_user: AuthUser = DependsCustomerAuth,
) -> ResponseModel:
    """
    删除练习会话

    删除会话及其关联的所有答题记录
    """
    session = await practice_session_dao.get(db=db, session_id=pk)
    if not session:
        return response_base.fail(msg='会话不存在')
    if session.user_id != current_user.user_id:
        return response_base.fail(msg='无权操作此会话')

    count = await practice_session_dao.delete(db=db, session_id=pk)
    if count > 0:
        return response_base.success()
    return response_base.fail()


# ============ 答题记录接口 ============


@router.post('/records', summary='创建答题记录', name='qbank_practice_create_record')
async def create_record(
    db: CurrentSessionTransaction,
    obj: CreatePracticeRecordParam,
    current_user: AuthUser = DependsCustomerAuth,
) -> ResponseSchemaModel[GetPracticeRecordDetail]:
    """创建单条答题记录"""
    record_dict = obj.model_dump()
    record_dict['user_id'] = current_user.user_id
    record_dict['created_by'] = current_user.user_id  # 答题者即创建者

    new_record = await practice_record_dao.create(db=db, obj_dict=record_dict)
    return response_base.success(data=GetPracticeRecordDetail.model_validate(new_record))


@router.post('/records/batch', summary='批量创建答题记录', name='qbank_practice_batch_create_records')
async def batch_create_records(
    db: CurrentSessionTransaction,
    obj: BatchCreatePracticeRecordsParam,
    current_user: AuthUser = DependsCustomerAuth,
) -> ResponseModel:
    """
    批量创建答题记录

    适合考试/试卷场景，一次性提交所有答题记录
    注意：会先删除该会话的所有旧记录，再批量创建新记录（避免重复数据）
    """
    # 获取会话信息获取 bank_id 和 chapter_id
    session = await practice_session_dao.get(db=db, session_id=obj.session_id)
    if not session:
        return response_base.fail(msg='会话不存在')
    if session.user_id != current_user.user_id:
        return response_base.fail(msg='无权操作此会话')

    # 🔥 先删除该会话的所有旧记录（避免重复数据）
    deleted_count = await practice_record_dao.delete_by_session(db=db, session_id=obj.session_id)

    records_dict = []
    for record in obj.records:
        record_dict = record.model_dump()
        record_dict['user_id'] = current_user.user_id
        record_dict['session_id'] = obj.session_id
        record_dict['bank_id'] = session.bank_id
        record_dict['chapter_id'] = session.chapter_id
        record_dict['created_by'] = current_user.user_id  # 答题者即创建者
        records_dict.append(record_dict)

    await practice_record_dao.batch_create(db=db, records=records_dict)
    return response_base.success()


@router.get('/records/{pk}', summary='获取答题记录详情', name='qbank_practice_get_record')
async def get_record(
    db: CurrentSession,
    pk: Annotated[int, Path(description='记录 ID')],
    current_user: AuthUser = DependsCustomerAuth,
) -> ResponseSchemaModel[GetPracticeRecordDetail]:
    """获取答题记录详情"""
    record = await practice_record_dao.get(db=db, record_id=pk)
    if not record:
        return response_base.fail(msg='记录不存在')
    if record.user_id != current_user.user_id:
        return response_base.fail(msg='无权访问此记录')

    return response_base.success(data=GetPracticeRecordDetail.model_validate(record))


@router.get(
    '/records',
    summary='获取答题记录列表',
    name='qbank_practice_get_records',
    dependencies=[DependsPagination],
)
async def get_records(
    db: CurrentSession,
    current_user: AuthUser = DependsCustomerAuth,
    session_id: Annotated[int | None, Query(description='会话 ID')] = None,
    question_id: Annotated[int | None, Query(description='题目 ID')] = None,
) -> ResponseSchemaModel[PageData[GetPracticeRecordListItem]]:
    """
    获取答题记录列表（分页）

    支持按会话、题目筛选
    """
    stmt = await practice_record_dao.get_select(
        user_id=current_user.user_id, session_id=session_id, question_id=question_id
    )
    page_data = await paging_data(db, stmt, GetPracticeRecordListItem)
    return response_base.success(data=page_data)


@router.get('/{pk}/records', summary='获取会话的所有答题记录', name='qbank_practice_get_session_records')
async def get_session_records(
    db: CurrentSession,
    pk: Annotated[int, Path(description='会话 ID')],
    current_user: AuthUser = DependsCustomerAuth,
) -> ResponseSchemaModel[list[GetPracticeRecordDetail]]:
    """获取会话的所有答题记录"""
    session = await practice_session_dao.get(db=db, session_id=pk)
    if not session:
        return response_base.fail(msg='会话不存在')
    if session.user_id != current_user.user_id:
        return response_base.fail(msg='无权访问此会话')

    records = await practice_record_dao.get_by_session(db=db, session_id=pk)
    return response_base.success(data=[GetPracticeRecordDetail.model_validate(r) for r in records])


@router.get('/{pk}/summary', summary='获取会话结算数据', name='qbank_practice_get_session_summary')
async def get_session_summary(
    db: CurrentSession,
    pk: Annotated[int, Path(description='会话 ID')],
    current_user: AuthUser = DependsCustomerAuth,
) -> ResponseSchemaModel[SessionSummaryData]:
    """
    获取会话结算数据（用于结算页面）

    包含统计信息、答题卡数据、错题 ID 列表
    """
    session = await practice_session_dao.get(db=db, session_id=pk)
    if not session:
        return response_base.fail(msg='会话不存在')
    if session.user_id != current_user.user_id:
        return response_base.fail(msg='无权访问此会话')

    # 查询所有答题记录
    records = await practice_record_dao.get_by_session(db=db, session_id=pk)

    # 构造答题卡数据和错题列表
    answer_items = []
    wrong_question_ids = []

    if session.question_ids:
        record_map = {r.question_id: r for r in records}

        for index, question_id in enumerate(session.question_ids):
            record = record_map.get(question_id)

            if record is None:
                status = 'unanswered'
            elif record.is_correct:
                status = 'correct'
            else:
                status = 'wrong'
                wrong_question_ids.append(question_id)

            # 🔥 题号从 1 开始（不是从 0）
            answer_items.append(AnswerCardItem(index=index + 1, question_id=question_id, status=status))
    else:
        for index, record in enumerate(records):
            status = 'correct' if record.is_correct else 'wrong'
            if not record.is_correct:
                wrong_question_ids.append(record.question_id)

            # 🔥 题号从 1 开始（不是从 0）
            answer_items.append(AnswerCardItem(index=index + 1, question_id=record.question_id, status=status))

    unanswered_count = session.total_count - session.completed_count

    summary_data = SessionSummaryData(
        session_id=session.id,
        bank_id=session.bank_id,
        practice_name=session.practice_name,
        session_type=session.session_type,
        total_count=session.total_count,
        completed_count=session.completed_count,
        correct_count=session.correct_count,
        wrong_count=session.wrong_count,
        unanswered_count=unanswered_count,
        accuracy_rate=session.accuracy_rate,
        total_time=session.total_time,
        status=session.status,
        answer_items=answer_items,
        wrong_question_ids=wrong_question_ids,
    )

    return response_base.success(data=summary_data)


# ============ 统计接口 ============


# @router.get('/statistics', summary='获取用户练习统计')
# async def get_user_statistics(
#     db: CurrentSession,
#     current_user: AuthUser = DependsCustomerAuth,
# ) -> ResponseSchemaModel[UserPracticeStatistics]:
#     """获取用户的练习统计数据"""
#     # TODO: 实现统计逻辑
#     pass


# @router.get('/statistics/daily', summary='获取每日练习统计')
# async def get_daily_statistics(
#     db: CurrentSession,
#     current_user: AuthUser = DependsCustomerAuth,
#     days: Annotated[int, Query(description='天数（7/30）')] = 7,
# ) -> ResponseSchemaModel[list[DailyPracticeStatistics]]:
#     """获取用户每日练习统计"""
#     # TODO: 实现统计逻辑
#     pass


# @router.get('/statistics/question-types', summary='获取题型统计')
# async def get_question_type_statistics(
#     db: CurrentSession,
#     current_user: AuthUser = DependsCustomerAuth,
# ) -> ResponseSchemaModel[list[QuestionTypeStatistics]]:
#     """获取用户各题型的练习统计"""
#     # TODO: 实现统计逻辑
#     pass
