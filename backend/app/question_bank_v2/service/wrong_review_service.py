import hashlib
import json
import uuid

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.question_bank_v2.crud.crud_practice import (
    practice_session_item_dao,
    question_attempt_dao,
)
from backend.app.question_bank_v2.crud.crud_question import (
    question_answer_dao,
    question_dao,
    question_explanation_dao,
    question_external_ref_dao,
    question_revision_dao,
)
from backend.app.question_bank_v2.crud.crud_review import (
    question_review_dao,
    review_reference_dao,
    review_tag_dao,
    user_question_mastery_dao,
    wrong_question_state_dao,
)
from backend.app.question_bank_v2.model.practice import QbQuestionAttempt
from backend.app.question_bank_v2.model.review import QbQuestionReview, QbWrongQuestionState
from backend.app.question_bank_v2.model.statistics import QbUserQuestionMastery
from backend.app.question_bank_v2.schema.review import (
    CreateExternalWrongQuestionParam,
    CreateQuestionReviewParam,
    CreateReviewTagParam,
    GetDueWrongQuestionResult,
    GetQuestionReviewDetail,
    GetReviewTagDetail,
    GetWrongQuestionListItem,
    SubmitQuestionReviewResult,
)
from backend.app.question_bank_v2.service.question_service import question_service
from backend.app.question_bank_v2.service.review_schedule_service import review_schedule_service
from backend.common.exception import errors
from backend.utils.timezone import timezone

CAPTURE_SOURCE_SYSTEM = 'qbank_v2_capture'


class WrongReviewService:
    """错题录入、当前状态和复盘事件服务类"""

    @staticmethod
    def _request_fingerprint(*, obj: CreateExternalWrongQuestionParam) -> str:
        """计算与客户端幂等键绑定的规范化录入请求指纹"""
        payload = json.dumps(
            obj.model_dump(mode='json', exclude={'idempotency_key'}),
            ensure_ascii=True,
            separators=(',', ':'),
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode()).hexdigest()

    @staticmethod
    async def _validate_links(
        *,
        db: AsyncSession,
        user_id: int,
        tag_ids: list[int],
        knowledge_point_ids: list[int],
    ) -> None:
        """校验复盘标签和知识点引用"""
        valid_tag_ids = await review_reference_dao.get_valid_tag_ids(db, user_id=user_id, tag_ids=tag_ids)
        missing_tag_ids = set(tag_ids) - valid_tag_ids
        if missing_tag_ids:
            raise errors.NotFoundError(msg=f'复盘标签不存在或不可用: {sorted(missing_tag_ids)}')

        valid_knowledge_point_ids = await review_reference_dao.get_valid_knowledge_point_ids(
            db,
            knowledge_point_ids=knowledge_point_ids,
        )
        missing_knowledge_point_ids = set(knowledge_point_ids) - valid_knowledge_point_ids
        if missing_knowledge_point_ids:
            raise errors.NotFoundError(msg=f'知识点不存在: {sorted(missing_knowledge_point_ids)}')

    @staticmethod
    async def _validate_assets(
        *,
        db: AsyncSession,
        user_id: int,
        obj: CreateExternalWrongQuestionParam,
    ) -> None:
        """校验外部错题引用的题库资产"""
        asset_ids = [item.asset_id for item in obj.assets]
        valid_asset_ids = await review_reference_dao.get_valid_asset_ids(
            db,
            user_id=user_id,
            asset_ids=asset_ids,
        )
        missing_asset_ids = set(asset_ids) - valid_asset_ids
        if missing_asset_ids:
            raise errors.NotFoundError(msg=f'题目资产不存在、未就绪或不可访问: {sorted(missing_asset_ids)}')

    @staticmethod
    async def _build_review_detail(*, db: AsyncSession, review: QbQuestionReview) -> GetQuestionReviewDetail:
        """组装复盘事件及其规范化关联"""
        tag_ids, knowledge_point_ids = await question_review_dao.get_link_ids(db, review.id)
        return GetQuestionReviewDetail(
            id=review.id,
            wrong_state_id=review.wrong_state_id,
            question_id=review.question_id,
            question_revision_id=review.question_revision_id,
            source_attempt_id=review.source_attempt_id,
            event_type=review.event_type,
            rating=review.rating,
            rating_source=review.rating_source,
            duration_ms=review.duration_ms,
            summary=review.summary,
            outcome=review.outcome,
            review_data=review.review_data,
            tag_ids=tag_ids,
            knowledge_point_ids=knowledge_point_ids,
            algorithm_name=review.algorithm_name,
            algorithm_version=review.algorithm_version,
            due_before=review.due_before,
            due_after=review.due_after,
            reviewed_time=review.reviewed_time,
        )

    @staticmethod
    async def _get_wrong_item(*, db: AsyncSession, wrong_state_id: int, user_id: int) -> GetWrongQuestionListItem:
        """获取一条用户错题展示数据"""
        row = await wrong_question_state_dao.get_detail_row(
            db,
            pk=wrong_state_id,
            user_id=user_id,
        )
        if row is None:
            raise errors.NotFoundError(msg='错题不存在')
        return GetWrongQuestionListItem(**row)

    @staticmethod
    async def get_list(
        *,
        db: AsyncSession,
        user_id: int,
        status: str | None = 'active',
        entry_source: str | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> list[GetWrongQuestionListItem]:
        """获取当前用户统一的系统和外部错题列表"""
        rows = await wrong_question_state_dao.get_list(
            db,
            user_id=user_id,
            status=status,
            entry_source=entry_source,
            offset=offset,
            limit=limit,
        )
        return [GetWrongQuestionListItem(**row) for row in rows]

    @staticmethod
    async def get_due(
        *,
        db: AsyncSession,
        user_id: int,
        limit: int = 100,
    ) -> GetDueWrongQuestionResult:
        """获取当前用户已经到期的 FSRS 错题"""
        total, rows = await wrong_question_state_dao.get_due(
            db,
            user_id=user_id,
            now=timezone.now(),
            limit=limit,
        )
        return GetDueWrongQuestionResult(
            total_due=total,
            items=[GetWrongQuestionListItem(**row) for row in rows],
        )

    @staticmethod
    async def get_tags(*, db: AsyncSession, user_id: int) -> list[GetReviewTagDetail]:
        """获取系统和当前用户自定义复盘标签"""
        tags = await review_tag_dao.get_all(db, user_id=user_id)
        return [GetReviewTagDetail.model_validate(tag, from_attributes=True) for tag in tags]

    @staticmethod
    async def create_tag(
        *,
        db: AsyncSession,
        user_id: int,
        obj: CreateReviewTagParam,
    ) -> GetReviewTagDetail:
        """创建用户自定义复盘标签"""
        name = obj.name.strip()
        if await review_tag_dao.get_by_name(db, user_id=user_id, name=name) is not None:
            raise errors.ConflictError(msg='复盘标签名称已存在')
        tag = await review_tag_dao.create(
            db,
            {
                'name': name,
                'user_id': user_id,
                'tag_type': obj.tag_type,
                'color': obj.color,
                'created_by': user_id,
            },
        )
        return GetReviewTagDetail.model_validate(tag, from_attributes=True)

    @staticmethod
    async def _get_idempotent_capture(
        *,
        db: AsyncSession,
        user_id: int,
        obj: CreateExternalWrongQuestionParam,
    ) -> GetWrongQuestionListItem | None:
        """获取已经完成的同一外部错题录入"""
        capture_ref = await question_external_ref_dao.get_by_source(
            db,
            owner_id=user_id,
            source_system=CAPTURE_SOURCE_SYSTEM,
            external_key=obj.idempotency_key,
        )
        if capture_ref is None:
            return None
        request_hash = (capture_ref.metadata_json or {}).get('request_hash')
        if request_hash != WrongReviewService._request_fingerprint(obj=obj):
            raise errors.ConflictError(msg='错题录入幂等键已被其他请求使用')
        wrong_state = await wrong_question_state_dao.get_by_question(
            db,
            user_id=user_id,
            question_id=capture_ref.question_id,
        )
        if wrong_state is None:
            raise errors.ServerError(msg='外部错题录入状态不完整')
        return await WrongReviewService._get_wrong_item(
            db=db,
            wrong_state_id=wrong_state.id,
            user_id=user_id,
        )

    @staticmethod
    async def capture_external(
        *,
        db: AsyncSession,
        user_id: int,
        obj: CreateExternalWrongQuestionParam,
    ) -> GetWrongQuestionListItem:
        """将用户外部错题统一录入为私有版本化题目"""
        existing = await WrongReviewService._get_idempotent_capture(
            db=db,
            user_id=user_id,
            obj=obj,
        )
        if existing is not None:
            return existing

        await WrongReviewService._validate_links(
            db=db,
            user_id=user_id,
            tag_ids=obj.tag_ids,
            knowledge_point_ids=obj.knowledge_point_ids,
        )
        await WrongReviewService._validate_assets(db=db, user_id=user_id, obj=obj)

        question = await question_dao.create(
            db,
            code=f'usr.{user_id}.wrong.{uuid.uuid4().hex}',
            owner_id=user_id,
            visibility='private',
            origin_type='user_created' if obj.entry_source == 'manual' else 'imported',
            status='active',
            created_by=user_id,
        )
        revision = await question_revision_dao.create_data(
            db,
            question_id=question.id,
            revision_no=1,
            created_by=user_id,
            data={
                'stem': obj.stem,
                'content_format': obj.content_format,
                'question_type': obj.question_type,
                'option_data': [item.model_dump() for item in obj.options],
                'default_score': obj.default_score,
                'difficulty': obj.difficulty,
                'language': obj.language,
                'status': 'draft',
            },
        )
        if obj.answer is not None:
            await question_answer_dao.upsert(
                db,
                revision_id=revision.id,
                obj=obj.answer,
                user_id=user_id,
            )
        if obj.explanations:
            await question_explanation_dao.replace(
                db,
                revision_id=revision.id,
                items=obj.explanations,
                user_id=user_id,
            )
        if obj.assets:
            await review_reference_dao.create_question_asset_links(
                db,
                revision_id=revision.id,
                items=obj.assets,
                user_id=user_id,
            )
        if obj.answer is not None and obj.explanations:
            await question_service.publish_revision(
                db=db,
                question_id=question.id,
                revision_id=revision.id,
                published_by=user_id,
            )

        await question_external_ref_dao.create(
            db,
            question_id=question.id,
            owner_id=user_id,
            source_system=CAPTURE_SOURCE_SYSTEM,
            external_key=obj.idempotency_key,
            source_url=None,
            metadata={
                'entry_source': obj.entry_source,
                'request_hash': WrongReviewService._request_fingerprint(obj=obj),
            },
            created_by=user_id,
        )
        if obj.source_system is not None and obj.external_key is not None:
            existing_source = await question_external_ref_dao.get_by_source(
                db,
                owner_id=user_id,
                source_system=obj.source_system,
                external_key=obj.external_key,
            )
            if existing_source is not None:
                raise errors.ConflictError(msg='该外部来源题目已经录入')
            await question_external_ref_dao.create(
                db,
                question_id=question.id,
                owner_id=user_id,
                source_system=obj.source_system,
                external_key=obj.external_key,
                source_url=obj.source_url,
                metadata=obj.entry_metadata,
                created_by=user_id,
            )

        now = timezone.now()
        mastery = await review_schedule_service.ensure_mastery(
            db=db,
            user_id=user_id,
            question_id=question.id,
            question_revision_id=revision.id,
            now=now,
            for_update=True,
        )
        wrong_state = await wrong_question_state_dao.create(
            db,
            {
                'user_id': user_id,
                'question_id': question.id,
                'last_question_revision_id': revision.id,
                'entry_source': obj.entry_source,
                'entry_metadata': obj.entry_metadata,
                'status': 'active',
                'wrong_count': 1,
                'first_wrong_time': now,
                'last_wrong_time': now,
                'created_by': user_id,
            },
        )
        capture_event_key = f'capture:{hashlib.sha256(obj.idempotency_key.encode()).hexdigest()}'
        capture_event = await question_review_dao.create(
            db,
            {
                'user_id': user_id,
                'question_id': question.id,
                'question_revision_id': revision.id,
                'wrong_state_id': wrong_state.id,
                'event_type': 'capture',
                'duration_ms': 0,
                'summary': obj.summary,
                'outcome': 'continue',
                'review_data': obj.review_data,
                'algorithm_name': mastery.algorithm_name,
                'algorithm_version': mastery.algorithm_version,
                'due_after': mastery.next_review_time,
                'idempotency_key': capture_event_key,
                'reviewed_time': now,
                'created_by': user_id,
            },
        )
        await question_review_dao.create_links(
            db,
            review_id=capture_event.id,
            tag_ids=obj.tag_ids,
            knowledge_point_ids=obj.knowledge_point_ids,
        )
        return await WrongReviewService._get_wrong_item(
            db=db,
            wrong_state_id=wrong_state.id,
            user_id=user_id,
        )

    @staticmethod
    async def _build_submit_result(
        *,
        db: AsyncSession,
        review: QbQuestionReview,
        wrong_state: QbWrongQuestionState,
        mastery: QbUserQuestionMastery,
    ) -> SubmitQuestionReviewResult:
        """构建复习事件与当前调度结果"""
        if mastery.next_review_time is None:
            raise errors.ServerError(msg='复习调度结果缺少下次复习时间')
        return SubmitQuestionReviewResult(
            review=await WrongReviewService._build_review_detail(db=db, review=review),
            wrong_status=wrong_state.status,
            next_review_time=mastery.next_review_time,
            forecast=review_schedule_service.forecast(mastery=mastery),
        )

    @staticmethod
    async def _get_idempotent_review_result(
        *,
        db: AsyncSession,
        user_id: int,
        wrong_state_id: int,
        obj: CreateQuestionReviewParam,
    ) -> SubmitQuestionReviewResult | None:
        """复用已经完成的同一复习提交"""
        existing = await question_review_dao.get_by_idempotency_key(
            db,
            user_id=user_id,
            idempotency_key=obj.idempotency_key,
        )
        if existing is None:
            return None
        if existing.event_type != 'review' or existing.wrong_state_id != wrong_state_id:
            raise errors.ConflictError(msg='复习提交幂等键已被其他请求使用')
        retry_fields_match = (
            existing.rating == obj.rating
            and existing.rating_source == obj.rating_source
            and existing.source_attempt_id == obj.source_attempt_id
            and existing.duration_ms == obj.duration_ms
            and existing.summary == obj.summary
            and existing.outcome == obj.outcome
            and existing.review_data == obj.review_data
        )
        if not retry_fields_match:
            raise errors.ConflictError(msg='复习提交幂等键已被其他请求使用')
        tag_ids, knowledge_point_ids = await question_review_dao.get_link_ids(db, existing.id)
        if set(tag_ids) != set(obj.tag_ids) or set(knowledge_point_ids) != set(obj.knowledge_point_ids):
            raise errors.ConflictError(msg='复习提交幂等键已被其他请求使用')
        wrong_state = await wrong_question_state_dao.get(
            db,
            wrong_state_id,
            user_id=user_id,
        )
        mastery = await user_question_mastery_dao.get_by_question(
            db,
            user_id=user_id,
            question_id=existing.question_id,
        )
        if wrong_state is None or mastery is None:
            raise errors.ServerError(msg='复习提交状态不完整')
        return await WrongReviewService._build_submit_result(
            db=db,
            review=existing,
            wrong_state=wrong_state,
            mastery=mastery,
        )

    @staticmethod
    async def _resolve_review_source(
        *,
        db: AsyncSession,
        user_id: int,
        wrong_state: QbWrongQuestionState,
        source_attempt_id: int | None,
    ) -> tuple[int, QbQuestionAttempt | None, int | None]:
        """校验关联作答并解析题目版本和题库上下文"""
        if wrong_state.last_question_revision_id is None:
            raise errors.ServerError(msg='错题缺少可复习的题目版本')
        if source_attempt_id is None:
            return wrong_state.last_question_revision_id, None, None

        source_attempt = await question_attempt_dao.get(
            db,
            source_attempt_id,
            user_id=user_id,
            question_id=wrong_state.question_id,
        )
        if source_attempt is None:
            raise errors.NotFoundError(msg='复习关联的作答事实不存在')
        bank_item_id = None
        if source_attempt.session_item_id is not None:
            session_item = await practice_session_item_dao.get(db, source_attempt.session_item_id)
            bank_item_id = session_item.bank_item_id if session_item is not None else None
        return source_attempt.question_revision_id, source_attempt, bank_item_id

    @staticmethod
    def _apply_review_outcome(
        *,
        wrong_state: QbWrongQuestionState,
        mastery: QbUserQuestionMastery,
        outcome: str,
        rating: int,
        reviewed_time: datetime,
    ) -> None:
        """应用复盘后的错题当前状态"""
        if outcome == 'mastered':
            wrong_state.status = 'resolved'
            wrong_state.resolved_time = reviewed_time
        elif outcome == 'reopened' or rating == 1:
            wrong_state.status = 'active'
            wrong_state.resolved_time = None
        if wrong_state.status == 'resolved':
            mastery.state = 'mastered'

    @staticmethod
    async def submit_review(
        *,
        db: AsyncSession,
        user_id: int,
        wrong_state_id: int,
        obj: CreateQuestionReviewParam,
    ) -> SubmitQuestionReviewResult:
        """幂等追加真正复习事件并原子推进 FSRS"""
        existing_result = await WrongReviewService._get_idempotent_review_result(
            db=db,
            user_id=user_id,
            wrong_state_id=wrong_state_id,
            obj=obj,
        )
        if existing_result is not None:
            return existing_result

        wrong_state = await wrong_question_state_dao.get(
            db,
            wrong_state_id,
            user_id=user_id,
            for_update=True,
        )
        if wrong_state is None:
            raise errors.NotFoundError(msg='错题不存在')
        existing_result = await WrongReviewService._get_idempotent_review_result(
            db=db,
            user_id=user_id,
            wrong_state_id=wrong_state_id,
            obj=obj,
        )
        if existing_result is not None:
            return existing_result
        if wrong_state.status == 'suspended':
            raise errors.ConflictError(msg='已暂停的错题不能提交复习')
        question_revision_id, source_attempt, bank_item_id = await WrongReviewService._resolve_review_source(
            db=db,
            user_id=user_id,
            wrong_state=wrong_state,
            source_attempt_id=obj.source_attempt_id,
        )

        await WrongReviewService._validate_links(
            db=db,
            user_id=user_id,
            tag_ids=obj.tag_ids,
            knowledge_point_ids=obj.knowledge_point_ids,
        )
        reviewed_time = timezone.now()
        mastery = await review_schedule_service.ensure_mastery(
            db=db,
            user_id=user_id,
            question_id=wrong_state.question_id,
            question_revision_id=question_revision_id,
            now=reviewed_time,
            for_update=True,
        )
        due_before, schedule_result, _ = await review_schedule_service.schedule_review(
            db=db,
            mastery=mastery,
            rating=obj.rating,
            reviewed_time=reviewed_time,
        )

        wrong_state.last_question_revision_id = question_revision_id
        WrongReviewService._apply_review_outcome(
            wrong_state=wrong_state,
            mastery=mastery,
            outcome=obj.outcome,
            rating=obj.rating,
            reviewed_time=reviewed_time,
        )
        review = await question_review_dao.create(
            db,
            {
                'user_id': user_id,
                'question_id': wrong_state.question_id,
                'question_revision_id': question_revision_id,
                'wrong_state_id': wrong_state.id,
                'source_attempt_id': source_attempt.id if source_attempt is not None else None,
                'bank_item_id': bank_item_id,
                'event_type': 'review',
                'rating': obj.rating,
                'rating_source': obj.rating_source,
                'duration_ms': obj.duration_ms,
                'summary': obj.summary,
                'outcome': obj.outcome,
                'review_data': obj.review_data,
                'algorithm_name': mastery.algorithm_name,
                'algorithm_version': mastery.algorithm_version,
                'due_before': due_before,
                'due_after': schedule_result.next_due,
                'idempotency_key': obj.idempotency_key,
                'reviewed_time': reviewed_time,
                'created_by': user_id,
            },
        )
        await question_review_dao.create_links(
            db,
            review_id=review.id,
            tag_ids=obj.tag_ids,
            knowledge_point_ids=obj.knowledge_point_ids,
        )
        await db.flush()
        return await WrongReviewService._build_submit_result(
            db=db,
            review=review,
            wrong_state=wrong_state,
            mastery=mastery,
        )

    @staticmethod
    async def get_review(
        *,
        db: AsyncSession,
        user_id: int,
        review_id: int,
    ) -> GetQuestionReviewDetail:
        """获取当前用户的一次复盘详情"""
        review = await question_review_dao.get(db, review_id, user_id=user_id)
        if review is None:
            raise errors.NotFoundError(msg='复盘记录不存在')
        return await WrongReviewService._build_review_detail(db=db, review=review)


wrong_review_service: WrongReviewService = WrongReviewService()
