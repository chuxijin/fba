import uuid

from datetime import timedelta
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.question_bank_v2.crud.crud_bank import bank_revision_dao
from backend.app.question_bank_v2.crud.crud_composition import bank_section_dao
from backend.app.question_bank_v2.crud.crud_practice import (
    practice_response_dao,
    practice_session_dao,
    practice_session_item_dao,
    question_attempt_dao,
)
from backend.app.question_bank_v2.crud.crud_question import (
    question_answer_dao,
    question_explanation_dao,
    question_revision_dao,
)
from backend.app.question_bank_v2.model.practice import (
    QbPracticeSession,
    QbPracticeSessionItem,
    QbPracticeSessionResponse,
)
from backend.app.question_bank_v2.schema.practice import (
    CreatePracticeSessionParam,
    GetPracticeResponseDetail,
    GetPracticeSessionDetail,
    GetPracticeSolutionDetail,
    PracticeExplanationDetail,
    SavePracticeResponseParam,
    SubmitPracticeItemParam,
    SubmitPracticeItemResult,
    SubmitPracticeSessionResult,
)
from backend.app.question_bank_v2.service.access_service import bank_access_service
from backend.app.question_bank_v2.service.grading_service import practice_grading_service
from backend.app.question_bank_v2.service.review_schedule_service import review_schedule_service
from backend.common.exception import errors
from backend.utils.timezone import timezone


class PracticeService:
    """题库 V2 练习会话服务类"""

    @staticmethod
    async def get(*, db: AsyncSession, session_key: str, user_id: int) -> GetPracticeSessionDetail:
        """获取当前用户的练习会话与题目快照"""
        session = await practice_session_dao.get_detail(db, session_key, user_id)
        if session is None:
            raise errors.NotFoundError(msg='练习会话不存在')
        items = await practice_session_item_dao.get_all(db, session['id'])
        return GetPracticeSessionDetail(**session, items=items)

    @staticmethod
    def _ensure_session_open(*, session: QbPracticeSession) -> None:
        """校验会话仍允许写入答案"""
        if session.status not in {'created', 'in_progress'}:
            raise errors.ConflictError(msg='当前会话已结束，不能继续作答')
        if session.expires_time is not None and session.expires_time <= timezone.now():
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
            and source_snapshot.get('bank_id') == obj.bank_id
            and source_snapshot.get('section_id') == obj.section_id
            and session.mode == obj.mode
            and bool(delivery_config.get('shuffle')) == obj.shuffle
            and delivery_config.get('requested_limit') == obj.limit
        )

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
            raise errors.NotFoundError(msg='练习会话题目不存在')
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
        PracticeService._ensure_session_open(session=session)
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
        PracticeService._ensure_session_open(session=session)
        answer = await question_answer_dao.get_by_revision(db, session_item.question_revision_id)
        if answer is None:
            raise errors.ServerError(msg='题目版本缺少权威答案')
        response = await practice_response_dao.get(
            db,
            session_id=session.id,
            session_item_id=session_item.id,
            for_update=True,
        )
        if response is not None and obj.save_version is not None and response.save_version != obj.save_version:
            raise errors.ConflictError(msg='答案版本已变化，请刷新后重试')
        if response is None and obj.save_version not in {None, 0}:
            raise errors.ConflictError(msg='答案版本已变化，请刷新后重试')

        question_revision = await question_revision_dao.get(
            db,
            session_item.question_revision_id,
            question_id=session_item.question_id,
        )
        if question_revision is None:
            raise errors.ServerError(msg='题目版本不存在')

        grade = practice_grading_service.grade(
            response_data=obj.response_data,
            answer_data=answer.answer_data,
            grading_method=answer.grading_method,
            grading_config=answer.grading_config,
            question_type=question_revision.question_type,
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
                'question_revision_id': session_item.question_revision_id,
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
        await review_schedule_service.apply_attempt(
            db=db,
            attempt=attempt,
            session_item=session_item,
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
        return SubmitPracticeItemResult(
            attempt_id=attempt.id,
            attempt_no=attempt.attempt_no,
            session_item_id=session_item.id,
            grading_status=attempt.grading_status,
            grading_method=attempt.grading_method,
            is_correct=attempt.is_correct,
            score=attempt.score,
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
        """在允许的提交阶段返回固定题目版本的答案解析"""
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
        if response is None or response.status not in {'submitted', 'graded', 'review_required'}:
            raise errors.ForbiddenError(msg='提交答案后才可查看解析')
        if session.mode in {'exam', 'mock'} and session.status not in {'submitted', 'graded'}:
            raise errors.ForbiddenError(msg='考试或模考交卷后才可查看解析')

        answer = await question_answer_dao.get_by_revision(db, session_item.question_revision_id)
        if answer is None:
            raise errors.ServerError(msg='题目版本缺少权威答案')
        explanations = await question_explanation_dao.get_all(db, session_item.question_revision_id)
        return GetPracticeSolutionDetail(
            session_item_id=session_item.id,
            question_id=session_item.question_id,
            question_revision_id=session_item.question_revision_id,
            answer_data=answer.answer_data,
            grading_method=answer.grading_method,
            grading_config=answer.grading_config,
            explanations=[
                PracticeExplanationDetail(
                    content=item.content,
                    explanation_type=item.explanation_type,
                    language=item.language,
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
        PracticeService._ensure_session_open(session=session)
        has_pending_grading = await practice_response_dao.has_pending_grading(db, session.id)
        session.status = 'submitted' if has_pending_grading or session.answered_items == 0 else 'graded'
        session.submitted_time = timezone.now()
        await db.flush()
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
    async def create(
        *,
        db: AsyncSession,
        user_id: int,
        obj: CreatePracticeSessionParam,
    ) -> GetPracticeSessionDetail:
        """校验题库准入后创建固定版本的练习会话"""
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

        bank, _ = await bank_access_service.ensure_bank_access(
            db=db,
            user_id=user_id,
            bank_id=obj.bank_id,
        )
        revision = await bank_revision_dao.get(db, bank.current_revision_id, bank_id=bank.id)
        if revision is None or revision.status != 'published':
            raise errors.NotFoundError(msg='题库当前发布版本不存在')

        if obj.section_id is not None:
            section = await bank_section_dao.get(db, obj.section_id, revision_id=revision.id)
            if section is None:
                raise errors.NotFoundError(msg='题库章节不存在')

        existing_detail = await PracticeService._get_idempotent_session(
            db=db,
            session_key=session_key,
            user_id=user_id,
            obj=obj,
        )
        if existing_detail is not None:
            return existing_detail

        candidates = await practice_session_item_dao.get_candidates(
            db,
            bank_revision_id=revision.id,
            section_id=obj.section_id,
            shuffle=obj.shuffle,
            limit=obj.limit or 500,
        )
        if not candidates:
            raise errors.RequestError(msg='当前条件下没有可投递题目')

        now = timezone.now()
        expires_time = None
        if revision.duration_minutes is not None:
            expires_time = now + timedelta(minutes=revision.duration_minutes)
        source_type = 'section' if obj.section_id is not None else 'bank'
        source_ref = f'bank:{bank.id}'
        if obj.section_id is not None:
            source_ref = f'{source_ref}:section:{obj.section_id}'

        session = await practice_session_dao.create(
            db,
            {
                'session_key': session_key,
                'user_id': user_id,
                'bank_revision_id': revision.id,
                'mode': obj.mode,
                'source_type': source_type,
                'source_ref': source_ref,
                'title_snapshot': revision.name,
                'status': 'in_progress',
                'started_time': now,
                'expires_time': expires_time,
                'total_items': len(candidates),
                'delivery_config': {
                    'shuffle': obj.shuffle,
                    'requested_limit': obj.limit,
                },
                'source_snapshot': {
                    'bank_id': bank.id,
                    'bank_revision_id': revision.id,
                    'section_id': obj.section_id,
                },
            },
        )
        await practice_session_item_dao.create_all(
            db,
            session_id=session.id,
            candidates=candidates,
        )
        return await PracticeService.get(db=db, session_key=session.session_key, user_id=user_id)


practice_service: PracticeService = PracticeService()
