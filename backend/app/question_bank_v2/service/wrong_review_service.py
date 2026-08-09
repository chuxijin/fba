import hashlib
import uuid

from collections.abc import Sequence
from datetime import timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.question_bank_v2.crud.crud_knowledge import question_knowledge_point_dao
from backend.app.question_bank_v2.crud.crud_practice import (
    practice_session_item_dao,
    question_attempt_dao,
)
from backend.app.question_bank_v2.crud.crud_question import (
    question_answer_dao,
    question_dao,
    question_explanation_dao,
)
from backend.app.question_bank_v2.crud.crud_review import (
    question_review_dao,
    review_reference_dao,
    review_tag_dao,
    wrong_question_state_dao,
)
from backend.app.question_bank_v2.model.practice import QbQuestionAttempt
from backend.app.question_bank_v2.model.review import QbQuestionReview, QbWrongQuestionState
from backend.app.question_bank_v2.schema.knowledge import KnowledgePointAssignmentParam
from backend.app.question_bank_v2.schema.review import (
    CreateExternalWrongQuestionParam,
    CreateQuestionReviewParam,
    CreateReviewTagParam,
    GetDueWrongQuestionResult,
    GetQuestionReviewDetail,
    GetReviewTagDetail,
    GetWrongQuestionDetail,
    GetWrongQuestionListItem,
    GetWrongReviewDashboard,
    SubmitQuestionReviewResult,
    UpdateWrongStateParam,
    WrongQuestionStatistics,
    WrongReviewDistributionItem,
)
from backend.app.question_bank_v2.schema.user_content import ContentGroupNode
from backend.app.question_bank_v2.service.content_group_service import content_group_service
from backend.app.question_bank_v2.service.knowledge_service import knowledge_service
from backend.app.question_bank_v2.service.practice_schedule_service import next_practice_time
from backend.app.question_bank_v2.service.preference_service import preference_service
from backend.app.question_bank_v2.service.review_schedule_service import review_schedule_service
from backend.common.exception import errors
from backend.utils.timezone import timezone

DASHBOARD_WINDOW_DAYS = 30


class WrongReviewService:
    """错题录入、当前状态和复盘事件服务类"""

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

        # 知识点 ID 全局唯一，用户是从某一版本的树上选的；这里只需校验存在且未跨版本混选
        if knowledge_point_ids:
            await knowledge_service.ensure_point_ids(db=db, point_ids=knowledge_point_ids)

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
            source_attempt_id=review.source_attempt_id,
            event_type=review.event_type,
            duration_ms=review.duration_ms,
            summary=review.summary,
            review_data=review.review_data,
            tag_ids=tag_ids,
            knowledge_point_ids=knowledge_point_ids,
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
    def get_list_select(
        *,
        user_id: int,
        status: str | None = 'active',
        entry_source: str | None = None,
        entry_scope: str | None = None,
    ) -> Any:
        """构建当前用户统一错题列表查询"""
        return wrong_question_state_dao.get_list_select(
            user_id=user_id,
            status=status,
            entry_source=entry_source,
            entry_scope=entry_scope,
        )

    @staticmethod
    def get_reviewed_select(
        *,
        user_id: int,
        mastery_state: str | None = None,
        tag_id: int | None = None,
        knowledge_point_id: int | None = None,
    ) -> Any:
        """构建复盘档案查询"""
        return wrong_question_state_dao.get_reviewed_list_select(
            user_id=user_id,
            mastery_state=mastery_state,
            tag_id=tag_id,
            knowledge_point_id=knowledge_point_id,
        )

    @staticmethod
    def get_pending_review_select(
        *,
        user_id: int,
        entry_scope: str | None = None,
    ) -> Any:
        """构建待复盘队列查询"""
        return wrong_question_state_dao.get_pending_review_list_select(
            user_id=user_id,
            entry_scope=entry_scope,
        )

    @staticmethod
    async def get_detail(
        *,
        db: AsyncSession,
        user_id: int,
        wrong_state_id: int,
    ) -> GetWrongQuestionDetail:
        """获取错题详情，含答案解析与还需连对几次"""
        row = await wrong_question_state_dao.get_detail_row(db, pk=wrong_state_id, user_id=user_id)
        if row is None:
            raise errors.NotFoundError(msg='错题不存在')
        preference = await preference_service.get(db=db, user_id=user_id)
        threshold = 1 if row['review_count'] > 0 else preference.mastery_threshold
        return GetWrongQuestionDetail(
            **row,
            resolve_threshold=max(1, threshold - row['correct_streak']),
        )

    @staticmethod
    async def get_review_events_select(
        *,
        db: AsyncSession,
        user_id: int,
        wrong_state_id: int,
    ) -> Any:
        """校验归属并构建一道错题的复盘时间线查询"""
        if await wrong_question_state_dao.get(db, wrong_state_id, user_id=user_id) is None:
            raise errors.NotFoundError(msg='错题不存在')
        return question_review_dao.get_by_wrong_state_select(
            user_id=user_id,
            wrong_state_id=wrong_state_id,
        )

    @staticmethod
    async def build_review_page(*, db: AsyncSession, reviews: Sequence[Any]) -> list[GetQuestionReviewDetail]:
        """批量装配一页复盘事件，避免逐事件查询关联表"""
        tag_ids, knowledge_point_ids = await question_review_dao.get_link_ids_batch(
            db,
            [review.id for review in reviews],
        )
        return [
            GetQuestionReviewDetail(
                id=review.id,
                wrong_state_id=review.wrong_state_id,
                question_id=review.question_id,
                source_attempt_id=review.source_attempt_id,
                event_type=review.event_type,
                duration_ms=review.duration_ms,
                summary=review.summary,
                review_data=dict(review.review_data or {}),
                tag_ids=tag_ids.get(review.id, []),
                knowledge_point_ids=knowledge_point_ids.get(review.id, []),
                reviewed_time=review.reviewed_time,
            )
            for review in reviews
        ]

    @staticmethod
    async def get_due(
        *,
        db: AsyncSession,
        user_id: int,
        limit: int | None = None,
    ) -> GetDueWrongQuestionResult:
        """获取当前用户已经到期重练的错题"""
        if limit is None:
            preference = await preference_service.get(db=db, user_id=user_id)
            limit = preference.review_daily_limit
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
    async def get_dashboard(
        *,
        db: AsyncSession,
        user_id: int,
        knowledge_system_id: int | None = None,
        domain_category_id: int | None = None,
    ) -> GetWrongReviewDashboard:
        """获取错因与知识点复盘看板"""
        now = timezone.now()
        resolved_domain_id = await knowledge_service.resolve_domain_category_id(
            db=db,
            user_id=user_id,
            domain_category_id=domain_category_id,
        )
        knowledge_system_ids = await knowledge_service.resolve_system_ids(
            db=db,
            domain_category_id=resolved_domain_id,
            system_id=knowledge_system_id,
            user_id=user_id,
        )
        statistics = await wrong_question_state_dao.get_statistics(db, user_id=user_id, now=now)
        event_count, reason_rows, knowledge_rows = await wrong_question_state_dao.get_dashboard_rows(
            db,
            user_id=user_id,
            since=now - timedelta(days=DASHBOARD_WINDOW_DAYS),
            knowledge_system_ids=knowledge_system_ids,
        )
        return GetWrongReviewDashboard(
            reviewed_count=statistics['reviewed_count'],
            pending_review_count=statistics['pending_review_count'],
            review_event_count=event_count,
            reason_distribution=[WrongReviewDistributionItem(**row) for row in reason_rows],
            knowledge_point_distribution=[
                WrongReviewDistributionItem(**row, color=None) for row in knowledge_rows
            ],
        )

    @staticmethod
    async def get_statistics(
        *,
        db: AsyncSession,
        user_id: int,
        group_by: str,
        knowledge_system_id: int | None = None,
        domain_category_id: int | None = None,
    ) -> WrongQuestionStatistics:
        """获取错题汇总及题库或知识点分组"""
        statistics = await wrong_question_state_dao.get_statistics(db, user_id=user_id, now=timezone.now())
        knowledge_system_ids: list[int] = []
        if group_by == 'knowledge_point':
            resolved_domain_id = await knowledge_service.resolve_domain_category_id(
                db=db,
                user_id=user_id,
                domain_category_id=domain_category_id,
            )
            knowledge_system_ids = await knowledge_service.resolve_system_ids(
                db=db,
                domain_category_id=resolved_domain_id,
                system_id=knowledge_system_id,
                user_id=user_id,
            )
        rows = await wrong_question_state_dao.get_group_counts(
            db,
            user_id=user_id,
            group_by=group_by,
            knowledge_system_ids=knowledge_system_ids,
        )
        if group_by == 'knowledge_point':
            groups = [
                ContentGroupNode(id=row['id'], name=row['name'], count=int(row['count'] or 0))
                for row in rows
            ]
        else:
            groups = await content_group_service.build_bank_tree(
                db=db,
                rows=rows,
                ungrouped_name='自主录入',
            )
        return WrongQuestionStatistics(**statistics, groups=groups)

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
    async def capture_external(
        *,
        db: AsyncSession,
        user_id: int,
        obj: CreateExternalWrongQuestionParam,
    ) -> GetWrongQuestionDetail:
        """将用户外部错题统一录入为可重练的私有题目"""
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
            stem=obj.stem,
            content_format=obj.content_format,
            question_type=obj.question_type,
            option_data=[item.model_dump() for item in obj.options],
            default_score=obj.default_score,
            difficulty=None,
            content_hash=None,
            created_by=user_id,
        )
        # 权威答案是必填的：没有答案就无法判分，录入的错题也就进不了刷题系统
        await question_answer_dao.upsert(
            db,
            question_id=question.id,
            obj=obj.answer,
            user_id=user_id,
        )
        if obj.explanations:
            await question_explanation_dao.replace(
                db,
                question_id=question.id,
                items=obj.explanations,
                user_id=user_id,
            )
        if obj.assets:
            await review_reference_dao.create_question_asset_links(
                db,
                question_id=question.id,
                items=obj.assets,
                user_id=user_id,
            )
        await question_knowledge_point_dao.replace(
            db,
            question_id=question.id,
            items=[
                KnowledgePointAssignmentParam(knowledge_point_id=point_id, source='manual')
                for point_id in obj.knowledge_point_ids
            ],
            user_id=user_id,
        )

        now = timezone.now()
        await review_schedule_service.ensure_mastery(
            db=db,
            user_id=user_id,
            question_id=question.id,
            for_update=True,
        )
        wrong_state = await wrong_question_state_dao.create(
            db,
            {
                'user_id': user_id,
                'question_id': question.id,
                'entry_source': obj.entry_source,
                'entry_metadata': obj.entry_metadata,
                'status': 'active',
                'wrong_count': 1,
                'first_wrong_time': now,
                'last_wrong_time': now,
                'next_practice_time': next_practice_time(level=0, now=now),
                'created_by': user_id,
            },
        )
        capture_event_key = f'capture:{hashlib.sha256(obj.idempotency_key.encode()).hexdigest()}'
        capture_event = await question_review_dao.create(
            db,
            {
                'user_id': user_id,
                'question_id': question.id,
                'wrong_state_id': wrong_state.id,
                'event_type': 'capture',
                'duration_ms': 0,
                'summary': None,
                'review_data': {},
                'idempotency_key': capture_event_key,
                'reviewed_time': now,
                'created_by': user_id,
            },
        )
        await question_review_dao.create_links(
            db,
            review_id=capture_event.id,
            tag_ids=[],
            knowledge_point_ids=[],
        )
        has_review_content = bool(
            (obj.summary and obj.summary.strip())
            or obj.review_data
            or obj.tag_ids
            or obj.knowledge_point_ids
        )
        if has_review_content:
            review_event = await question_review_dao.create(
                db,
                {
                    'user_id': user_id,
                    'question_id': question.id,
                    'wrong_state_id': wrong_state.id,
                    'event_type': 'review',
                    'duration_ms': 0,
                    'summary': obj.summary,
                    'review_data': obj.review_data,
                    'idempotency_key': f'review:{hashlib.sha256(obj.idempotency_key.encode()).hexdigest()}',
                    'reviewed_time': now,
                    'created_by': user_id,
                },
            )
            await question_review_dao.create_links(
                db,
                review_id=review_event.id,
                tag_ids=obj.tag_ids,
                knowledge_point_ids=obj.knowledge_point_ids,
            )
            wrong_state.review_count = 1
            wrong_state.last_reviewed_time = now
            await db.flush()
        return await WrongReviewService.get_detail(
            db=db,
            user_id=user_id,
            wrong_state_id=wrong_state.id,
        )

    @staticmethod
    async def _build_submit_result(
        *,
        db: AsyncSession,
        review: QbQuestionReview,
        wrong_state: QbWrongQuestionState,
    ) -> SubmitQuestionReviewResult:
        """构建复盘事件结果；复盘不改错题本状态，也不推进重练排期"""
        return SubmitQuestionReviewResult(
            review=await WrongReviewService._build_review_detail(db=db, review=review),
            wrong_status=wrong_state.status,
            review_count=wrong_state.review_count,
            next_practice_time=wrong_state.next_practice_time,
        )

    @staticmethod
    async def _get_idempotent_review_result(
        *,
        db: AsyncSession,
        user_id: int,
        wrong_state_id: int,
        obj: CreateQuestionReviewParam,
    ) -> SubmitQuestionReviewResult | None:
        """复用已经完成的同一复盘提交"""
        existing = await question_review_dao.get_by_idempotency_key(
            db,
            user_id=user_id,
            idempotency_key=obj.idempotency_key,
        )
        if existing is None:
            return None
        if existing.event_type != 'review' or existing.wrong_state_id != wrong_state_id:
            raise errors.ConflictError(msg='复盘提交幂等键已被其他请求使用')
        retry_fields_match = (
            existing.source_attempt_id == obj.source_attempt_id
            and existing.duration_ms == obj.duration_ms
            and existing.summary == obj.summary
            and existing.review_data == obj.review_data
        )
        if not retry_fields_match:
            raise errors.ConflictError(msg='复盘提交幂等键已被其他请求使用')
        tag_ids, knowledge_point_ids = await question_review_dao.get_link_ids(db, existing.id)
        if set(tag_ids) != set(obj.tag_ids) or set(knowledge_point_ids) != set(obj.knowledge_point_ids):
            raise errors.ConflictError(msg='复盘提交幂等键已被其他请求使用')
        wrong_state = await wrong_question_state_dao.get(db, wrong_state_id, user_id=user_id)
        if wrong_state is None:
            raise errors.ServerError(msg='复盘提交状态不完整')
        return await WrongReviewService._build_submit_result(
            db=db,
            review=existing,
            wrong_state=wrong_state,
        )

    @staticmethod
    async def _resolve_review_source(
        *,
        db: AsyncSession,
        user_id: int,
        wrong_state: QbWrongQuestionState,
        source_attempt_id: int | None,
    ) -> tuple[QbQuestionAttempt | None, int | None]:
        """校验关联作答并解析题库上下文"""
        if source_attempt_id is None:
            return None, None

        source_attempt = await question_attempt_dao.get(
            db,
            source_attempt_id,
            user_id=user_id,
            question_id=wrong_state.question_id,
        )
        if source_attempt is None:
            raise errors.NotFoundError(msg='复盘关联的作答事实不存在')
        bank_item_id = None
        if source_attempt.session_item_id is not None:
            session_item = await practice_session_item_dao.get(db, source_attempt.session_item_id)
            bank_item_id = session_item.bank_item_id if session_item is not None else None
        return source_attempt, bank_item_id

    @staticmethod
    async def submit_review(
        *,
        db: AsyncSession,
        user_id: int,
        wrong_state_id: int,
        obj: CreateQuestionReviewParam,
    ) -> SubmitQuestionReviewResult:
        """幂等追加一次复盘事件

        复盘只记录反思，不改错题本状态、不推进重练排期 —— 那条线由客观作答驱动。
        已移出错题本的题仍可复盘，方便考前回顾时补记录。
        """
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
            raise errors.ConflictError(msg='已暂停的错题不能提交复盘')
        source_attempt, bank_item_id = await WrongReviewService._resolve_review_source(
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
        review = await question_review_dao.create(
            db,
            {
                'user_id': user_id,
                'question_id': wrong_state.question_id,
                'wrong_state_id': wrong_state.id,
                'source_attempt_id': source_attempt.id if source_attempt is not None else None,
                'bank_item_id': bank_item_id,
                'event_type': 'review',
                'duration_ms': obj.duration_ms,
                'summary': obj.summary,
                'review_data': obj.review_data,
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
        wrong_state.review_count += 1
        wrong_state.last_reviewed_time = reviewed_time
        await db.flush()
        return await WrongReviewService._build_submit_result(
            db=db,
            review=review,
            wrong_state=wrong_state,
        )

    @staticmethod
    async def update_state(
        *,
        db: AsyncSession,
        user_id: int,
        wrong_state_id: int,
        obj: UpdateWrongStateParam,
    ) -> GetWrongQuestionListItem:
        """手动调整错题本状态"""
        wrong_state = await wrong_question_state_dao.get(
            db,
            wrong_state_id,
            user_id=user_id,
            for_update=True,
        )
        if wrong_state is None:
            raise errors.NotFoundError(msg='错题不存在')
        now = timezone.now()

        if obj.action == 'pin':
            wrong_state.is_pinned = True
            wrong_state.pinned_time = now
        elif obj.action == 'unpin':
            wrong_state.is_pinned = False
            wrong_state.pinned_time = None
        elif obj.action == 'resolve':
            wrong_state.status = 'resolved'
            wrong_state.resolved_time = now
            wrong_state.next_practice_time = None
        elif obj.action == 'suspend':
            wrong_state.status = 'suspended'
            wrong_state.next_practice_time = None
        else:
            wrong_state.status = 'active'
            wrong_state.resolved_time = None
            review_schedule_service.reschedule(wrong_state=wrong_state, now=now)

        if obj.action in {'resolve', 'reopen', 'resume'}:
            mastery = await review_schedule_service.ensure_mastery(
                db=db,
                user_id=user_id,
                question_id=wrong_state.question_id,
                for_update=True,
            )
            mastery.state = 'mastered' if obj.action == 'resolve' else 'learning'

        await db.flush()
        return await WrongReviewService._get_wrong_item(
            db=db,
            wrong_state_id=wrong_state.id,
            user_id=user_id,
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
