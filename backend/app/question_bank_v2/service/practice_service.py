import hashlib
import json
import uuid

from collections.abc import Sequence
from datetime import timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from backend.app.access.constants import ReasonCode
from backend.app.question_bank_v2.crud.crud_bank import bank_revision_dao
from backend.app.question_bank_v2.crud.crud_composition import bank_section_dao
from backend.app.question_bank_v2.crud.crud_material import question_interaction_dao, question_material_dao
from backend.app.question_bank_v2.crud.crud_practice import (
    practice_response_dao,
    practice_session_dao,
    practice_session_item_dao,
    question_attempt_dao,
)
from backend.app.question_bank_v2.crud.crud_question import (
    question_answer_dao,
    question_dao,
    question_explanation_dao,
)
from backend.app.question_bank_v2.crud.crud_user_content import favorite_folder_dao
from backend.app.question_bank_v2.model.practice import (
    QbPracticeSession,
    QbPracticeSessionItem,
    QbPracticeSessionResponse,
)
from backend.app.question_bank_v2.schema.practice import (
    TIMED_PRACTICE_MODES,
    CreatePracticeSessionParam,
    GetPracticeResponseDetail,
    GetPracticeSessionDetail,
    GetPracticeSessionReport,
    GetPracticeSessionSolutionItem,
    GetPracticeSolutionDetail,
    PracticeExplanationDetail,
    PracticeReportItem,
    SavePracticeResponseParam,
    SubmitPracticeItemParam,
    SubmitPracticeItemResult,
    SubmitPracticeSessionResult,
)
from backend.app.question_bank_v2.schema.question import CollectQuestionsParam, CollectQuestionsResult
from backend.app.question_bank_v2.service.access_service import BankAccessService, bank_access_service
from backend.app.question_bank_v2.service.grading_service import practice_grading_service
from backend.app.question_bank_v2.service.knowledge_service import knowledge_service
from backend.app.question_bank_v2.service.preference_service import preference_service
from backend.app.question_bank_v2.service.review_schedule_service import review_schedule_service
from backend.app.question_bank_v2.service.statistics_service import statistics_service
from backend.common.exception import errors
from backend.common.log import log
from backend.utils.timezone import timezone


class PracticeService:
    """题库 V2 练习会话服务类"""

    @staticmethod
    def _attach_delivery_materials(
        *,
        items: list[dict[str, Any]],
        materials: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """为题目附加轻量引用并返回按固定版本去重的材料目录"""
        materials_by_question: dict[int, list[dict[str, Any]]] = {}
        material_catalog: dict[tuple[int, int], dict[str, Any]] = {}
        for material in materials:
            reference = {
                key: material[key]
                for key in (
                    'id',
                    'question_id',
                    'material_id',
                    'material_revision_id',
                    'role',
                    'sort_order',
                    'display_config',
                )
            }
            materials_by_question.setdefault(material['question_id'], []).append(reference)
            material_key = (material['material_id'], material['material_revision_id'])
            if material_key not in material_catalog:
                material_catalog[material_key] = {
                    key: material[key]
                    for key in (
                        'material_id',
                        'material_revision_id',
                        'title',
                        'content',
                        'content_format',
                        'structured_data',
                        'source_name',
                        'source_url',
                        'content_hash',
                    )
                }
        for item in items:
            item['materials'] = materials_by_question.get(item['question_id'], [])
        return list(material_catalog.values())

    @staticmethod
    def _attach_delivery_interactions(
        *,
        items: list[dict[str, Any]],
        interactions: list[dict[str, Any]],
    ) -> None:
        """为各投递题目附加已启用交互定义"""
        by_question: dict[int, list[dict[str, Any]]] = {}
        for interaction in interactions:
            by_question.setdefault(interaction['question_id'], []).append(interaction)
        for item in items:
            item['interactions'] = by_question.get(item['question_id'], [])

    @staticmethod
    async def _filter_accessible_candidates(
        *,
        db: AsyncSession,
        user_id: int,
        bank_id: int | None,
        candidates: Sequence[Any],
        source_ref_prefix: str,
        consume: bool,
    ) -> list[Any]:
        """按投递顺序应用题库准入与试看策略"""
        if bank_id is None:
            return list(candidates)

        accessible: list[Any] = []
        total = len(candidates)
        for ordinal, candidate in enumerate(candidates):
            _, decision = await bank_access_service.ensure_bank_access(
                db=db,
                user_id=user_id,
                bank_id=bank_id,
                question_ordinal=ordinal,
                question_total=total,
                consume=consume,
                source_ref=f'{source_ref_prefix}:{ordinal}',
                raise_on_deny=False,
            )
            if not decision.allowed:
                if not accessible:
                    raise errors.ForbiddenError(msg=BankAccessService._deny_message(decision))
                break
            accessible.append(candidate)
        return accessible

    @staticmethod
    async def get(*, db: AsyncSession, session_key: str, user_id: int) -> GetPracticeSessionDetail:
        """获取当前用户的练习会话与题目快照"""
        session = await practice_session_dao.get_detail(db, session_key, user_id)
        if session is None:
            raise errors.NotFoundError(msg='练习会话不存在')
        if session['status'] in {'created', 'in_progress'}:
            session_model = await practice_session_dao.get_by_key(db, session_key, user_id=user_id, for_update=True)
            if session_model is not None:
                await PracticeService._expire_if_due(db=db, session=session_model)
                session = await practice_session_dao.get_detail(db, session_key, user_id)
        items = await practice_session_item_dao.get_all(db, session['id'])
        if session['mode'] in {'exam', 'mock'} and session['status'] not in {'submitted', 'graded', 'expired'}:
            for item in items:
                item['is_correct'] = None
                item['score'] = None
        materials = await question_material_dao.get_all_by_questions(
            db,
            [item['question_id'] for item in items],
        )
        interactions = await question_interaction_dao.get_all(
            db,
            question_ids=[item['question_id'] for item in items],
            active_only=True,
        )
        material_catalog = PracticeService._attach_delivery_materials(items=items, materials=materials)
        PracticeService._attach_delivery_interactions(items=items, interactions=interactions)
        return GetPracticeSessionDetail(**session, materials=material_catalog, items=items)

    @staticmethod
    def get_list_select(
        *,
        user_id: int,
        status: str | None,
        mode: str | None,
        source_type: str | None,
        bank_id: int | None,
    ) -> Select:
        """构建当前用户会话历史分页查询"""
        return practice_session_dao.get_list_select(
            user_id=user_id,
            status=status,
            mode=mode,
            source_type=source_type,
            bank_id=bank_id,
        )

    @staticmethod
    async def hide(*, db: AsyncSession, session_key: str, user_id: int) -> None:
        """隐藏用户会话，但保留作答事实、错题和统计来源"""
        session = await practice_session_dao.get_by_key(
            db,
            session_key,
            user_id=user_id,
            for_update=True,
        )
        if session is None:
            raise errors.NotFoundError(msg='练习会话不存在')
        session.status = 'cancelled'
        session.deleted = session.id
        session.deleted_time = timezone.now()
        await db.flush()

    @staticmethod
    def _report_status(row: dict) -> str:
        """将当前作答投影转换为互斥答题卡状态"""
        if row['is_correct'] is True:
            return 'correct'
        if row['is_correct'] is False:
            return 'wrong'
        if row['response_status'] in {'submitted', 'graded', 'review_required'}:
            return 'pending'
        return 'unanswered'

    @staticmethod
    async def get_report(
        *,
        db: AsyncSession,
        session_key: str,
        user_id: int,
    ) -> GetPracticeSessionReport:
        """获取整场报告，主观题待判与未答题分开统计"""
        session = await practice_session_dao.get_detail(db, session_key, user_id)
        if session is None:
            raise errors.NotFoundError(msg='练习会话不存在')
        if session['status'] in {'created', 'in_progress'}:
            session_model = await practice_session_dao.get_by_key(db, session_key, user_id=user_id, for_update=True)
            if session_model is not None:
                await PracticeService._expire_if_due(db=db, session=session_model)
                session = await practice_session_dao.get_detail(db, session_key, user_id)
        if session['mode'] in {'exam', 'mock'} and session['status'] not in {'submitted', 'graded', 'expired'}:
            raise errors.ForbiddenError(msg='考试或模考交卷后才可查看报告')
        rows = await practice_session_dao.get_report_items(db, session['id'])
        items = [
            PracticeReportItem(
                session_item_id=row['session_item_id'],
                position=row['position'],
                question_id=row['question_id'],
                bank_item_id=row['bank_item_id'],
                section_id=row['section_id'],
                section_name=row['section_name'],
                status=PracticeService._report_status(row),
                duration_ms=row['duration_ms'],
                score=row['score'],
                max_score=row['max_score'],
            )
            for row in rows
        ]
        graded_items = sum(item.status in {'correct', 'wrong'} for item in items)
        correct_items = sum(item.status == 'correct' for item in items)
        wrong_items = sum(item.status == 'wrong' for item in items)
        pending_items = sum(item.status == 'pending' for item in items)
        unanswered_items = sum(item.status == 'unanswered' for item in items)
        answered_items = len(items) - unanswered_items
        accuracy_rate = (
            (Decimal(correct_items) / Decimal(graded_items)).quantize(Decimal('0.0001'))
            if graded_items
            else Decimal('0.0000')
        )
        return GetPracticeSessionReport(
            session_id=session['id'],
            session_key=session['session_key'],
            bank_id=session['bank_id'],
            mode=session['mode'],
            source_type=session['source_type'],
            title_snapshot=session['title_snapshot'],
            status=session['status'],
            total_items=len(items),
            answered_items=answered_items,
            graded_items=graded_items,
            correct_items=correct_items,
            wrong_items=wrong_items,
            pending_items=pending_items,
            unanswered_items=unanswered_items,
            accuracy_rate=accuracy_rate,
            score=session['score'],
            total_score=sum((item.max_score for item in items), start=Decimal(0)),
            total_duration_ms=sum(item.duration_ms for item in items),
            started_time=session['started_time'],
            submitted_time=session['submitted_time'],
            items=items,
            wrong_question_ids=[item.question_id for item in items if item.status == 'wrong'],
        )

    @staticmethod
    async def get_session_solutions(
        *,
        db: AsyncSession,
        session_key: str,
        user_id: int,
    ) -> list[GetPracticeSessionSolutionItem]:
        """交卷后批量返回整场题目答案解析"""
        session = await practice_session_dao.get_by_key(db, session_key, user_id=user_id)
        if session is None:
            raise errors.NotFoundError(msg='练习会话不存在')
        if getattr(session, 'status', None) in {'created', 'in_progress'}:
            await PracticeService._expire_if_due(db=db, session=session)
        if session.status not in {'submitted', 'graded', 'expired'}:
            raise errors.ForbiddenError(msg='交卷后才可查看整场答案解析')
        rows = await practice_session_dao.get_solutions(db, session.id)
        return [GetPracticeSessionSolutionItem(**row) for row in rows]

    @staticmethod
    async def _expire_if_due(*, db: AsyncSession, session: QbPracticeSession) -> bool:
        """Persist the terminal state when a timed session reaches its deadline."""
        if (
            session.status in {'created', 'in_progress'}
            and getattr(session, 'expires_time', None) is not None
            and session.expires_time <= timezone.now()
        ):
            session.status = 'expired'
            session.submitted_time = timezone.now()
            await PracticeService._apply_deferred_attempts(db=db, session=session)
            await statistics_service.apply_session_submission(db=db, user_id=session.user_id)
            await db.commit()
            return True
        return False

    @staticmethod
    async def _apply_deferred_attempts(*, db: AsyncSession, session: QbPracticeSession) -> None:
        """Apply exam projections only after the session reaches a terminal state."""
        if session.mode not in {'exam', 'mock'}:
            return
        preference = await preference_service.get(db=db, user_id=session.user_id)
        for attempt, session_item in await question_attempt_dao.get_latest_by_session(db, session.id):
            await review_schedule_service.apply_attempt(
                db=db,
                attempt=attempt,
                session_item=session_item,
                resolve_threshold=preference.mastery_threshold,
            )
            await statistics_service.apply_attempt(
                db=db,
                attempt=attempt,
                max_score=session_item.max_score,
            )

    @staticmethod
    async def _ensure_session_open(*, db: AsyncSession, session: QbPracticeSession) -> None:
        """校验会话仍允许写入答案"""
        if session.status not in {'created', 'in_progress'}:
            raise errors.ConflictError(msg='当前会话已结束，不能继续作答')
        if await PracticeService._expire_if_due(db=db, session=session):
            raise errors.ConflictError(msg='当前会话已过期')

    @staticmethod
    def _matches_create_request(
        *,
        session: QbPracticeSession,
        user_id: int,
        obj: CreatePracticeSessionParam,
    ) -> bool:
        """判断客户端幂等键对应的会话是否来自同一创建请求"""
        source_snapshot = session.source_snapshot or {}
        delivery_config = session.delivery_config or {}
        return (
            session.user_id == user_id
            and source_snapshot.get('requested_source_type', 'bank') == obj.source_type
            and source_snapshot.get('bank_id') == obj.bank_id
            and source_snapshot.get('section_id') == obj.section_id
            and source_snapshot.get('favorite_folder_id') == obj.favorite_folder_id
            and list(source_snapshot.get('question_ids') or []) == obj.question_ids
            and list(source_snapshot.get('knowledge_point_ids') or []) == obj.knowledge_point_ids
            and (
                obj.knowledge_system_id is None
                or source_snapshot.get('knowledge_system_id') == obj.knowledge_system_id
            )
            and session.mode == obj.mode
            and (obj.title is None or getattr(session, 'title_snapshot', None) == obj.title)
            and bool(delivery_config.get('shuffle')) == obj.shuffle
            and delivery_config.get('requested_limit') == obj.limit
            and delivery_config.get('requested_duration_minutes') == obj.duration_minutes
            and list(delivery_config.get('question_types') or []) == obj.question_types
            and delivery_config.get('year_start') == obj.year_start
            and delivery_config.get('year_end') == obj.year_end
            and delivery_config.get('region') == obj.region
            and bool(delivery_config.get('include_knowledge_descendants', True)) == obj.include_knowledge_descendants
        )

    @staticmethod
    def _build_source_context(*, obj: CreatePracticeSessionParam) -> tuple[str, str]:
        """构建会话来源类型和长度稳定的来源引用"""
        if obj.source_type == 'bank':
            source_type = 'knowledge_point' if obj.knowledge_point_ids else ('section' if obj.section_id else 'bank')
            source_ref = f'bank:{obj.bank_id}'
            if obj.section_id is not None:
                source_ref = f'{source_ref}:section:{obj.section_id}'
            if obj.knowledge_point_ids:
                canonical = json.dumps(obj.knowledge_point_ids, separators=(',', ':'))
                source_ref = f'{source_ref}:knowledge:{hashlib.sha256(canonical.encode()).hexdigest()[:16]}'
            return source_type, source_ref
        if obj.source_type == 'favorite' and obj.favorite_folder_id is not None:
            return obj.source_type, f'favorite:folder:{obj.favorite_folder_id}'
        if obj.source_type == 'custom':
            canonical = json.dumps(obj.question_ids, separators=(',', ':'))
            return obj.source_type, f'custom:{hashlib.sha256(canonical.encode()).hexdigest()[:16]}'
        source_ref = obj.source_type
        if obj.bank_id is not None:
            source_ref = f'{source_ref}:bank:{obj.bank_id}'
        return obj.source_type, source_ref

    @staticmethod
    async def _get_owned_item(
        *,
        db: AsyncSession,
        session_key: str,
        user_id: int,
        session_item_id: int,
        for_update: bool,
    ) -> tuple[QbPracticeSession, QbPracticeSessionItem]:
        """获取用户会话内题目，避免脱离题库上下文访问题目"""
        context = await practice_session_dao.get_owned_item(
            db,
            session_key=session_key,
            user_id=user_id,
            session_item_id=session_item_id,
            for_update=for_update,
        )
        if context is None:
            raise errors.NotFoundError(msg='练习会题目不存在')
        return context

    @staticmethod
    def _build_response_detail(response: QbPracticeSessionResponse) -> GetPracticeResponseDetail:
        """构建作答草稿响应"""
        return GetPracticeResponseDetail(
            session_item_id=response.session_item_id,
            response_data=response.response_data,
            status=response.status,
            is_flagged=response.is_flagged,
            duration_ms=response.duration_ms,
            save_version=response.save_version,
            is_correct=response.is_correct,
            score=response.score,
            grading_status=response.grading_status,
            last_saved_time=response.last_saved_time,
            last_submitted_time=response.last_submitted_time,
        )

    @staticmethod
    async def save_response(
        *,
        db: AsyncSession,
        session_key: str,
        user_id: int,
        session_item_id: int,
        obj: SavePracticeResponseParam,
    ) -> GetPracticeResponseDetail:
        """使用乐观版本号自动保存题目答案"""
        session, _ = await PracticeService._get_owned_item(
            db=db,
            session_key=session_key,
            user_id=user_id,
            session_item_id=session_item_id,
            for_update=True,
        )
        await PracticeService._ensure_session_open(db=db, session=session)
        response = await practice_response_dao.get(
            db,
            session_id=session.id,
            session_item_id=session_item_id,
            for_update=True,
        )
        if response is not None and response.status in {'submitted', 'graded', 'review_required'}:
            raise errors.ConflictError(msg='题目已提交，如需重答请直接再次提交')
        if response is None and obj.save_version != 0:
            raise errors.ConflictError(msg='答案版本已变化，请刷新后重试')
        if response is not None and response.save_version != obj.save_version:
            raise errors.ConflictError(msg='答案版本已变化，请刷新后重试')

        now = timezone.now()
        status = 'answered' if obj.response_data is not None else 'viewing'
        if response is None:
            response = await practice_response_dao.create(
                db,
                {
                    'session_id': session.id,
                    'session_item_id': session_item_id,
                    'response_data': obj.response_data,
                    'status': status,
                    'is_flagged': obj.is_flagged,
                    'duration_ms': obj.duration_ms,
                    'save_version': 1,
                    'first_viewed_time': now,
                    'last_saved_time': now,
                },
            )
        else:
            response.response_data = obj.response_data
            response.status = status
            response.is_flagged = obj.is_flagged
            response.duration_ms = max(response.duration_ms, obj.duration_ms)
            response.save_version += 1
            response.last_saved_time = now
            response.grading_status = 'not_requested'
            response.is_correct = None
            response.score = None
            await db.flush()
        if session.status == 'created':
            session.status = 'in_progress'
            await db.flush()
        return PracticeService._build_response_detail(response)

    @staticmethod
    async def submit_item(
        *,
        db: AsyncSession,
        session_key: str,
        user_id: int,
        session_item_id: int,
        obj: SubmitPracticeItemParam,
    ) -> SubmitPracticeItemResult:
        """追加单题提交事实并更新会话当前判分缓存"""
        session, session_item = await PracticeService._get_owned_item(
            db=db,
            session_key=session_key,
            user_id=user_id,
            session_item_id=session_item_id,
            for_update=True,
        )
        await PracticeService._ensure_session_open(db=db, session=session)
        answer = await question_answer_dao.get_by_question(db, session_item.question_id)
        if answer is None:
            raise errors.ServerError(msg='题目缺少权威答案')
        response = await practice_response_dao.get(
            db,
            session_id=session.id,
            session_item_id=session_item.id,
            for_update=True,
        )
        if session.mode in {'exam', 'mock'} and response is not None and response.status in {
            'submitted', 'graded', 'review_required',
        }:
            raise errors.ConflictError(msg='考试或模考题目不能重复提交')
        if response is not None and obj.save_version is not None and response.save_version != obj.save_version:
            raise errors.ConflictError(msg='答案版本已变化，请刷新后重试')
        if response is None and obj.save_version not in {None, 0}:
            raise errors.ConflictError(msg='答案版本已变化，请刷新后重试')

        question = await question_dao.get(db, session_item.question_id)
        if question is None:
            raise errors.ServerError(msg='题目不存在')

        grade = practice_grading_service.grade(
            response_data=obj.response_data,
            answer_data=answer.answer_data,
            grading_method=answer.grading_method,
            grading_config=answer.grading_config,
            question_type=question.question_type,
            max_score=session_item.max_score,
        )
        response_status = 'graded' if grade.grading_status == 'graded' else 'submitted'
        now = timezone.now()
        was_answered = response is not None and response.status in {'submitted', 'graded', 'review_required'}
        previous_correct = response.is_correct if was_answered else None
        previous_score = response.score if was_answered and response.score is not None else Decimal(0)

        if response is None:
            response = await practice_response_dao.create(
                db,
                {
                    'session_id': session.id,
                    'session_item_id': session_item.id,
                    'response_data': obj.response_data,
                    'status': response_status,
                    'duration_ms': obj.duration_ms,
                    'save_version': 1,
                    'is_correct': grade.is_correct,
                    'score': grade.score,
                    'grading_status': grade.grading_status,
                    'first_viewed_time': now,
                    'last_saved_time': now,
                    'last_submitted_time': now,
                    'graded_time': now if grade.grading_status == 'graded' else None,
                },
            )
        else:
            response.response_data = obj.response_data
            response.status = response_status
            response.duration_ms = max(response.duration_ms, obj.duration_ms)
            response.save_version += 1
            response.is_correct = grade.is_correct
            response.score = grade.score
            response.grading_status = grade.grading_status
            response.last_saved_time = now
            response.last_submitted_time = now
            response.graded_time = now if grade.grading_status == 'graded' else None
            await db.flush()

        attempt_no = await question_attempt_dao.get_next_attempt_no(db, session_item.id)
        attempt = await question_attempt_dao.create(
            db,
            {
                'user_id': user_id,
                'question_id': session_item.question_id,
                'response_data': obj.response_data,
                'session_id': session.id,
                'session_item_id': session_item.id,
                'attempt_no': attempt_no,
                'is_correct': grade.is_correct,
                'score': grade.score,
                'duration_ms': obj.duration_ms,
                'grading_status': grade.grading_status,
                'grading_method': grade.grading_method,
                'grading_result': grade.details,
                'submitted_time': now,
            },
        )
        if session.mode not in {'exam', 'mock'}:
            preference = await preference_service.get(db=db, user_id=user_id)
            await review_schedule_service.apply_attempt(
                db=db,
                attempt=attempt,
                session_item=session_item,
                resolve_threshold=preference.mastery_threshold,
            )
            await statistics_service.apply_attempt(
                db=db,
                attempt=attempt,
                max_score=session_item.max_score,
            )

        if not was_answered:
            session.answered_items += 1
        session.correct_items = max(
            0,
            session.correct_items + int(grade.is_correct is True) - int(previous_correct is True),
        )
        session.score = max(Decimal(0), session.score - previous_score + (grade.score or Decimal(0)))
        if session.status == 'created':
            session.status = 'in_progress'
        await db.flush()
        reveal_grade = session.mode not in {'exam', 'mock'} or session.status in {'submitted', 'graded'}
        return SubmitPracticeItemResult(
            attempt_id=attempt.id,
            attempt_no=attempt.attempt_no,
            session_item_id=session_item.id,
            grading_status=attempt.grading_status,
            grading_method=attempt.grading_method,
            is_correct=attempt.is_correct if reveal_grade else None,
            score=attempt.score if reveal_grade else None,
            max_score=session_item.max_score,
            response_status=response.status,
            save_version=response.save_version,
        )

    @staticmethod
    async def get_solution(
        *,
        db: AsyncSession,
        session_key: str,
        user_id: int,
        session_item_id: int,
    ) -> GetPracticeSolutionDetail:
        """在允许的提交阶段返回题目答案解析"""
        session, session_item = await PracticeService._get_owned_item(
            db=db,
            session_key=session_key,
            user_id=user_id,
            session_item_id=session_item_id,
            for_update=False,
        )
        response = await practice_response_dao.get(
            db,
            session_id=session.id,
            session_item_id=session_item.id,
        )
        if response is None:
            if session.mode != 'practice':
                raise errors.ForbiddenError(msg='提交答案后才可查看解析')
        elif response.status not in {'submitted', 'graded', 'review_required'}:
            raise errors.ForbiddenError(msg='提交答案后才可查看解析')
        if session.mode in {'exam', 'mock'} and session.status not in {'submitted', 'graded'}:
            raise errors.ForbiddenError(msg='考试或模考交卷后才可查看解析')

        answer = await question_answer_dao.get_by_question(db, session_item.question_id)
        if answer is None:
            raise errors.ServerError(msg='题目缺少权威答案')
        explanations = await question_explanation_dao.get_all(db, session_item.question_id)
        return GetPracticeSolutionDetail(
            session_item_id=session_item.id,
            question_id=session_item.question_id,
            answer_data=answer.answer_data,
            grading_method=answer.grading_method,
            grading_config=answer.grading_config,
            explanations=[
                PracticeExplanationDetail(
                    content=item.content,
                    explanation_type=item.explanation_type,
                    is_default=item.is_default,
                )
                for item in explanations
                if item.status == 'published'
            ],
        )

    @staticmethod
    async def submit_session(
        *,
        db: AsyncSession,
        session_key: str,
        user_id: int,
    ) -> SubmitPracticeSessionResult:
        """交卷并冻结会话继续作答入口"""
        session = await practice_session_dao.get_by_key(
            db,
            session_key,
            user_id=user_id,
            for_update=True,
        )
        if session is None:
            raise errors.NotFoundError(msg='练习会话不存在')
        if session.status in {'submitted', 'graded'} and session.submitted_time is not None:
            return SubmitPracticeSessionResult(
                session_key=session.session_key,
                status=session.status,
                total_items=session.total_items,
                answered_items=session.answered_items,
                correct_items=session.correct_items,
                score=session.score,
                submitted_time=session.submitted_time,
            )
        await PracticeService._ensure_session_open(db=db, session=session)
        await PracticeService._apply_deferred_attempts(db=db, session=session)
        has_pending_grading = await practice_response_dao.has_pending_grading(db, session.id)
        session.status = 'submitted' if has_pending_grading or session.answered_items == 0 else 'graded'
        session.submitted_time = timezone.now()
        await statistics_service.apply_session_submission(db=db, user_id=user_id)
        await db.flush()
        await PracticeService._notify_study_plan(db=db, session=session, user_id=user_id)
        return SubmitPracticeSessionResult(
            session_key=session.session_key,
            status=session.status,
            total_items=session.total_items,
            answered_items=session.answered_items,
            correct_items=session.correct_items,
            score=session.score,
            submitted_time=session.submitted_time,
        )

    @staticmethod
    async def _notify_study_plan(
        *,
        db: AsyncSession,
        session: QbPracticeSession,
        user_id: int,
    ) -> None:
        """交卷后回调学习计划，自动完成绑定该会话的计划项"""
        # lazy import 避免题库与学习计划模块循环依赖
        from backend.app.study_plan.service.session_hook import handle_session_completed

        try:
            async with db.begin_nested():
                await handle_session_completed(
                    db,
                    session_key=session.session_key,
                    user_id=user_id,
                    correct_count=session.correct_items,
                    total_count=session.answered_items,
                )
        except SQLAlchemyError as exc:
            # 学习计划同步失败不应阻断交卷主流程
            log.warning(
                'study_plan_session_hook_failed | user_id={} session_key={} error={}',
                user_id,
                session.session_key,
                exc,
            )

    @staticmethod
    async def _get_idempotent_session(
        *,
        db: AsyncSession,
        session_key: str,
        user_id: int,
        obj: CreatePracticeSessionParam,
    ) -> GetPracticeSessionDetail | None:
        """按客户端幂等键获取同一创建请求已经生成的会话"""
        existing = await practice_session_dao.get_by_key(db, session_key)
        if existing is None:
            return None
        if not PracticeService._matches_create_request(session=existing, user_id=user_id, obj=obj):
            raise errors.ConflictError(msg='会话标识已被其他请求使用')
        return await PracticeService.get(db=db, session_key=session_key, user_id=user_id)

    @staticmethod
    async def create(  # noqa: C901
        *,
        db: AsyncSession,
        user_id: int,
        obj: CreatePracticeSessionParam,
    ) -> GetPracticeSessionDetail:
        """校验来源准入后创建练习会话"""
        session_key = obj.session_key or uuid.uuid4().hex
        if obj.session_key is not None:
            existing_detail = await PracticeService._get_idempotent_session(
                db=db,
                session_key=session_key,
                user_id=user_id,
                obj=obj,
            )
            if existing_detail is not None:
                return existing_detail

        bank = None
        revision = None
        initial_decision = None
        if obj.bank_id is not None:
            bank, initial_decision = await bank_access_service.ensure_bank_access(
                db=db,
                user_id=user_id,
                bank_id=obj.bank_id,
                question_ordinal=0,
                question_total=obj.limit or 500,
                consume=False,
                raise_on_deny=False,
            )
            if not initial_decision.allowed:
                raise errors.ForbiddenError(msg=BankAccessService._deny_message(initial_decision))
            if obj.source_type == 'bank' or obj.section_id is not None:
                revision = await bank_revision_dao.get(db, bank.current_revision_id, bank_id=bank.id)
                if revision is None or revision.status != 'published':
                    raise errors.NotFoundError(msg='题库当前发布版本不存在')
                if obj.section_id is not None:
                    section = await bank_section_dao.get(db, obj.section_id, revision_id=revision.id)
                    if section is None:
                        raise errors.NotFoundError(msg='题库篇章不存在')

        if obj.favorite_folder_id is not None:
            folder = await favorite_folder_dao.get(db, obj.favorite_folder_id, user_id=user_id)
            if folder is None or folder.status != 'active':
                raise errors.NotFoundError(msg='收藏夹不存在')

        resolved_knowledge_point_ids: set[int] = set()
        resolved_knowledge_system_id: int | None = None
        if obj.knowledge_point_ids:
            resolved_knowledge_point_ids = await knowledge_service.resolve_point_ids(
                db=db,
                point_ids=obj.knowledge_point_ids,
                include_descendants=obj.include_knowledge_descendants,
                system_id=obj.knowledge_system_id,
            )
            resolved_knowledge_system_id = obj.knowledge_system_id or await knowledge_service.resolve_point_system_id(
                db=db,
                point_ids=obj.knowledge_point_ids,
            )

        existing_detail = await PracticeService._get_idempotent_session(
            db=db,
            session_key=session_key,
            user_id=user_id,
            obj=obj,
        )
        if existing_detail is not None:
            return existing_detail

        if obj.source_type == 'bank':
            if revision is None:
                raise errors.ServerError(msg='题库当前发布版本不存在')
            candidates = await practice_session_item_dao.get_candidates(
                db,
                bank_revision_id=revision.id,
                section_id=obj.section_id,
                knowledge_point_ids=sorted(resolved_knowledge_point_ids),
                question_types=obj.question_types,
                year_start=obj.year_start,
                year_end=obj.year_end,
                shuffle=obj.shuffle,
                limit=obj.limit or 500,
                region=obj.region,
            )
        else:
            candidates = await practice_session_item_dao.get_user_candidates(
                db,
                user_id=user_id,
                source_type=obj.source_type,
                bank_id=obj.bank_id,
                section_id=obj.section_id,
                favorite_folder_id=obj.favorite_folder_id,
                question_ids=obj.question_ids,
                knowledge_point_ids=sorted(resolved_knowledge_point_ids),
                question_types=obj.question_types,
                year_start=obj.year_start,
                year_end=obj.year_end,
                shuffle=obj.shuffle,
                limit=obj.limit or 500,
                region=obj.region,
            )
        if not candidates:
            raise errors.RequestError(msg='当前条件下没有可投递题目')
        if obj.source_type == 'custom' and len(candidates) != min(len(obj.question_ids), obj.limit or 500):
            raise errors.NotFoundError(msg='部分指定题目不存在、未发布或不可访问')

        if initial_decision is not None and initial_decision.reason_code in {
            ReasonCode.METERED_CONSUMED,
            ReasonCode.TRIAL_POLICY,
        }:
            candidates = await PracticeService._filter_accessible_candidates(
                db=db,
                user_id=user_id,
                bank_id=bank.id,
                candidates=candidates,
                source_ref_prefix=f'qbank_v2:{session_key}',
                consume=True,
            )
        if not candidates:
            raise errors.RequestError(msg='当前账号没有可投递的题目')

        now = timezone.now()
        # 仅限时模式套用过期时间：顺序练习 / 背题不应因题库版本配了时长而中途过期
        expires_time = None
        if obj.mode in TIMED_PRACTICE_MODES:
            duration_minutes = obj.duration_minutes
            if duration_minutes is None and revision is not None:
                duration_minutes = revision.duration_minutes
            if duration_minutes is not None:
                expires_time = now + timedelta(minutes=duration_minutes)
        source_type, source_ref = PracticeService._build_source_context(obj=obj)
        title = obj.title
        if title is None and revision is not None:
            title = revision.name
        if title is None:
            title = {
                'wrong': '错题重练',
                'favorite': '收藏练习',
                'note': '笔记练习',
                'custom': '自选练习',
            }[obj.source_type]

        session = await practice_session_dao.create(
            db,
            {
                'session_key': session_key,
                'user_id': user_id,
                'bank_revision_id': revision.id if obj.source_type == 'bank' and revision is not None else None,
                'mode': obj.mode,
                'source_type': source_type,
                'source_ref': source_ref,
                'title_snapshot': title,
                'status': 'in_progress',
                'started_time': now,
                'expires_time': expires_time,
                'total_items': len(candidates),
                'delivery_config': {
                    'shuffle': obj.shuffle,
                    'requested_limit': obj.limit,
                    'requested_duration_minutes': obj.duration_minutes,
                    'question_types': obj.question_types,
                    'year_start': obj.year_start,
                    'year_end': obj.year_end,
                    'region': obj.region,
                    'include_knowledge_descendants': obj.include_knowledge_descendants,
                },
                'source_snapshot': {
                    'requested_source_type': obj.source_type,
                    'bank_id': bank.id if bank is not None else None,
                    'bank_revision_id': revision.id if obj.source_type == 'bank' and revision is not None else None,
                    'section_id': obj.section_id,
                    'favorite_folder_id': obj.favorite_folder_id,
                    'question_ids': obj.question_ids,
                    'knowledge_system_id': resolved_knowledge_system_id,
                    'knowledge_point_ids': obj.knowledge_point_ids,
                    'resolved_knowledge_point_ids': sorted(resolved_knowledge_point_ids),
                },
            },
        )
        await practice_session_item_dao.create_all(
            db,
            session_id=session.id,
            candidates=candidates,
        )
        return await PracticeService.get(db=db, session_key=session.session_key, user_id=user_id)

    @staticmethod
    async def collect_questions(  # noqa: C901
        *,
        db: AsyncSession,
        user_id: int,
        obj: CollectQuestionsParam,
    ) -> CollectQuestionsResult:
        """按与练习会话相同的来源规则采集题目 ID"""
        bank = None
        revision = None
        initial_decision = None
        if obj.bank_id is not None:
            bank, initial_decision = await bank_access_service.ensure_bank_access(
                db=db,
                user_id=user_id,
                bank_id=obj.bank_id,
                question_ordinal=0,
                question_total=obj.limit or 500,
                consume=False,
                raise_on_deny=False,
            )
            if not initial_decision.allowed:
                raise errors.ForbiddenError(msg=BankAccessService._deny_message(initial_decision))
            if obj.source_type == 'bank' or obj.section_id is not None:
                revision = await bank_revision_dao.get(db, bank.current_revision_id, bank_id=bank.id)
                if revision is None or revision.status != 'published':
                    raise errors.NotFoundError(msg='题库当前发布版本不存在')
                if obj.section_id is not None:
                    section = await bank_section_dao.get(db, obj.section_id, revision_id=revision.id)
                    if section is None:
                        raise errors.NotFoundError(msg='题库篇章不存在')
        if obj.favorite_folder_id is not None:
            folder = await favorite_folder_dao.get(db, obj.favorite_folder_id, user_id=user_id)
            if folder is None or folder.status != 'active':
                raise errors.NotFoundError(msg='收藏夹不存在')
        resolved_point_ids = await knowledge_service.resolve_point_ids(
            db=db,
            point_ids=obj.knowledge_point_ids,
            include_descendants=obj.include_knowledge_descendants,
            system_id=obj.knowledge_system_id,
        )
        if obj.source_type == 'bank':
            if revision is None:
                raise errors.ServerError(msg='题库当前发布版本不存在')
            candidates = await practice_session_item_dao.get_candidates(
                db,
                bank_revision_id=revision.id,
                section_id=obj.section_id,
                knowledge_point_ids=sorted(resolved_point_ids),
                question_types=obj.question_types,
                year_start=obj.year_start,
                year_end=obj.year_end,
                shuffle=False,
                limit=obj.limit,
                region=obj.region,
            )
        else:
            candidates = await practice_session_item_dao.get_user_candidates(
                db,
                user_id=user_id,
                source_type=obj.source_type,
                bank_id=obj.bank_id,
                section_id=obj.section_id,
                favorite_folder_id=obj.favorite_folder_id,
                question_ids=obj.question_ids,
                knowledge_point_ids=sorted(resolved_point_ids),
                question_types=obj.question_types,
                year_start=obj.year_start,
                year_end=obj.year_end,
                shuffle=False,
                limit=obj.limit,
                region=obj.region,
            )
        if initial_decision is not None and initial_decision.reason_code == ReasonCode.TRIAL_POLICY:
            candidates = await PracticeService._filter_accessible_candidates(
                db=db,
                user_id=user_id,
                bank_id=bank.id,
                candidates=candidates,
                source_ref_prefix=f'qbank_v2:collect:{user_id}:{obj.bank_id}',
                consume=False,
            )
        question_ids = list(dict.fromkeys(item.question_id for item in candidates))
        if obj.source_type == 'custom' and len(question_ids) != min(len(obj.question_ids), obj.limit):
            raise errors.NotFoundError(msg='部分指定题目不存在、未发布或不可访问')
        return CollectQuestionsResult(
            source_type=obj.source_type,
            question_ids=question_ids,
            total=len(question_ids),
        )


practice_service: PracticeService = PracticeService()
