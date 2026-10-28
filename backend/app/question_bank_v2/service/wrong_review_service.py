import hashlib
import uuid

from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import case, func, literal_column, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.admin.crud.crud_category import category_dao
from backend.app.question_bank_v2.crud.crud_external_practice import external_practice_dao
from backend.app.question_bank_v2.crud.crud_knowledge import question_knowledge_point_dao
from backend.app.question_bank_v2.crud.crud_material import question_material_dao
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
from backend.app.question_bank_v2.model.asset import QbQuestionAsset
from backend.app.question_bank_v2.model.material import (
    QbMaterial,
    QbMaterialRevision,
    QbQuestionMaterial,
)
from backend.app.question_bank_v2.model.practice import QbQuestionAttempt
from backend.app.question_bank_v2.model.question import QbQuestion, QbQuestionAnswer, QbQuestionExplanation
from backend.app.question_bank_v2.model.review import QbQuestionReview, QbWrongQuestionState
from backend.app.question_bank_v2.schema.knowledge import KnowledgePointAssignmentParam
from backend.app.question_bank_v2.schema.material import (
    CreateMaterialParam,
    CreateMaterialRevisionParam,
    GetQuestionMaterialDetail,
    QuestionMaterialParam,
)
from backend.app.question_bank_v2.schema.review import (
    ENTRY_METADATA_BATCH_KEY,
    ENTRY_METADATA_DOMAIN_KEY,
    ENTRY_METADATA_EXTERNAL_KEY_KEY,
    ENTRY_METADATA_MODULE_PATH_KEY,
    ENTRY_METADATA_SECTION_KEY,
    ENTRY_METADATA_SOURCE_SYSTEM_KEY,
    EXTERNAL_ENTRY_SOURCES,
    REVIEW_THOUGHT_REQUIRED_MESSAGE,
    BatchImportFailure,
    BatchImportItemResult,
    BatchImportResult,
    BatchUndoResult,
    CreateExternalWrongQuestionParam,
    CreateQuestionReviewParam,
    CreateReviewTagParam,
    GetDueWrongQuestionResult,
    GetQuestionReviewDetail,
    GetReviewTagDetail,
    GetWrongQuestionDetail,
    GetWrongQuestionExplanationItem,
    GetWrongQuestionListItem,
    GetWrongQuestionOutlineItem,
    GetWrongQuestionSummaryItem,
    GetWrongReviewDashboard,
    GetWrongSectionFacet,
    GetWrongSectionFacetsResult,
    ImportBatchPage,
    ImportHistoryBatchItem,
    ImportHistorySingleItem,
    ImportSinglePage,
    SubmitQuestionReviewResult,
    UpdateWrongStateParam,
    WrongCollectionItem,
    WrongCollectionPage,
    WrongQuestionFilters,
    WrongQuestionListQuery,
    WrongQuestionStatistics,
    WrongReviewDistributionItem,
    has_review_thought,
)
from backend.app.question_bank_v2.schema.user_content import ContentGroupNode
from backend.app.question_bank_v2.service.content_group_service import content_group_service
from backend.app.question_bank_v2.service.knowledge_service import knowledge_service
from backend.app.question_bank_v2.service.material_service import material_service
from backend.app.question_bank_v2.service.practice_schedule_service import next_practice_time
from backend.app.question_bank_v2.service.preference_service import preference_service
from backend.app.question_bank_v2.service.review_schedule_service import review_schedule_service
from backend.app.question_bank_v2.utils.external_practice import question_content_digest
from backend.common.exception import errors
from backend.common.pagination import cursor_paging_data
from backend.utils.timezone import timezone

DASHBOARD_WINDOW_DAYS = 30

# 批量录入单次上限：一次请求最多 50 道题，超过由客户端分片提交
BATCH_IMPORT_LIMIT = 50

# 导入记录相关列表的分页参数
IMPORT_HISTORY_PAGE_SIZE = 20
IMPORT_HISTORY_MAX_PAGE_SIZE = 100

# 错题集合列表分页参数
COLLECTION_PAGE_SIZE = 20
COLLECTION_MAX_PAGE_SIZE = 100

# 错题录入的领域兜底：当前只有公考一个领域，历史账号没设过领域时回落到公考根分类
DEFAULT_DOMAIN_APP_CODE = 'youanshang'
DEFAULT_DOMAIN_CATEGORY_TYPE = 'product_catalog'
DEFAULT_DOMAIN_CATEGORY_CODE = 'pc_gongkao'
DEFAULT_DOMAIN_CATEGORY_NAME = '公考'

# entry_metadata 的批次/来源/章节键统一在 schema 定义，这里保留别名以兼容既有引用


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
    async def get_domain_category_ids(*, db: AsyncSession, domain_category_id: int) -> list[int]:
        """把领域根分类展开成含子分类的 ID 列表；无效分类保留空范围。"""
        return await category_dao.get_subtree_ids_by_path(db, domain_category_id)

    @staticmethod
    async def resolve_domain_scope(
        *,
        db: AsyncSession,
        user_id: int,
        domain_category_id: int | None = None,
    ) -> list[int] | None:
        """解析错题领域范围（含子分类）

        显式传入优先，其次取用户当前领域；两者都无法判断时返回 None（不过滤），
        避免历史账号因为没设过领域而看不到任何错题。
        """
        resolved = await knowledge_service.resolve_optional_domain_category_id(
            db=db,
            user_id=user_id,
            domain_category_id=domain_category_id,
        )
        if resolved is None:
            return None
        return await WrongReviewService.get_domain_category_ids(db=db, domain_category_id=resolved)

    @staticmethod
    async def get_list_page(
        *,
        db: AsyncSession,
        user_id: int,
        query: WrongQuestionListQuery,
    ) -> dict[str, Any]:
        """同一范围和游标下按固定视图投影，仅在需要时读取题干与掌握度。"""
        domain_category_ids = await WrongReviewService.resolve_domain_scope(
            db=db, user_id=user_id, domain_category_id=query.domain_category_id
        )
        stmt = wrong_question_state_dao.get_list_select(
            user_id=user_id,
            filters=query,
            domain_category_ids=domain_category_ids,
            section_name=query.section_name,
            view=query.view,
        )
        schema = {
            'full': GetWrongQuestionListItem,
            'summary': GetWrongQuestionSummaryItem,
            'outline': GetWrongQuestionOutlineItem,
        }[query.view]
        return await cursor_paging_data(db, stmt, schema)

    @staticmethod
    async def get_sections(
        *,
        db: AsyncSession,
        user_id: int,
        filters: WrongQuestionFilters,
    ) -> GetWrongSectionFacetsResult:
        """返回当前浏览范围的章节及题量；集合参数为空时跨集合汇总"""
        domain_category_ids = await WrongReviewService.resolve_domain_scope(
            db=db,
            user_id=user_id,
            domain_category_id=filters.domain_category_id,
        )
        total, rows = await wrong_question_state_dao.get_section_counts(
            db,
            user_id=user_id,
            filters=filters,
            domain_category_ids=domain_category_ids,
        )
        return GetWrongSectionFacetsResult(
            total=total,
            items=[GetWrongSectionFacet(**row) for row in rows],
        )

    @staticmethod
    def get_reviewed_select(
        *,
        user_id: int,
        mastery_state: str | None = None,
        tag_id: int | None = None,
        knowledge_point_id: int | None = None,
        keyword: str | None = None,
        domain_category_ids: Sequence[int] | None = None,
    ) -> Any:
        """构建复盘档案查询"""
        return wrong_question_state_dao.get_reviewed_list_select(
            user_id=user_id,
            mastery_state=mastery_state,
            tag_id=tag_id,
            knowledge_point_id=knowledge_point_id,
            keyword=keyword,
            domain_category_ids=domain_category_ids,
        )

    @staticmethod
    def get_pending_review_select(
        *,
        user_id: int,
        entry_scope: str | None = None,
        domain_category_ids: Sequence[int] | None = None,
        since: datetime | None = None,
    ) -> Any:
        """构建待复盘队列查询"""
        return wrong_question_state_dao.get_pending_review_list_select(
            user_id=user_id,
            entry_scope=entry_scope,
            domain_category_ids=domain_category_ids,
            since=since,
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
        wrong_history = await question_attempt_dao.get_wrong_answer_history(
            db,
            user_id=user_id,
            question_id=int(row['question_id']),
        )
        if wrong_history:
            row['last_wrong_response'] = wrong_history[0]['response_data']
            row['last_wrong_duration_ms'] = wrong_history[0]['duration_ms']
        row['wrong_answer_history'] = [
            {
                'answer': item['response_data'],
                'attempt_no': item['attempt_no'],
                'submitted_time': item['submitted_time'],
                'duration_ms': item['duration_ms'],
            }
            for item in wrong_history
        ]
        if row['review_count'] > 0:
            threshold = 1
        else:
            preference = await preference_service.get(db=db, user_id=user_id)
            threshold = preference.mastery_threshold

        # 材料：错题详情要能展示题干上方的篇章材料
        material_rows = await question_material_dao.get_all(db, int(row['question_id']))
        materials = [GetQuestionMaterialDetail(**item) for item in material_rows]

        # 解析：与练习看解析同口径，返回全部已发布版本（默认解析在前），
        # `explanation` 字段继续保留为默认解析文本，老客户端不受影响。
        explanation_rows = await question_explanation_dao.get_published_by_question(db, int(row['question_id']))
        explanations = [
            GetWrongQuestionExplanationItem(
                content=item['content'],
                explanation_type=item['explanation_type'],
                is_default=bool(item['is_default']),
            )
            for item in explanation_rows
        ]

        return GetWrongQuestionDetail(
            **row,
            resolve_threshold=max(1, threshold - row['correct_streak']),
            materials=materials,
            explanations=explanations,
        )

    @staticmethod
    async def get_review_events_select(
        *,
        db: AsyncSession,
        user_id: int,
        wrong_state_id: int,
        event_type: str | None = None,
    ) -> Any:
        """校验归属并构建一道错题的复盘时间线查询"""
        if await wrong_question_state_dao.get(db, wrong_state_id, user_id=user_id) is None:
            raise errors.NotFoundError(msg='错题不存在')
        return question_review_dao.get_by_wrong_state_select(
            user_id=user_id,
            wrong_state_id=wrong_state_id,
            event_type=event_type,
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
        domain_category_ids = await WrongReviewService.get_domain_category_ids(
            db=db,
            domain_category_id=resolved_domain_id,
        )
        knowledge_system_ids = await knowledge_service.resolve_system_ids(
            db=db,
            domain_category_id=resolved_domain_id,
            system_id=knowledge_system_id,
            user_id=user_id,
        )
        statistics = await wrong_question_state_dao.get_statistics(
            db,
            user_id=user_id,
            now=now,
            domain_category_ids=domain_category_ids,
        )
        event_count, reason_rows, knowledge_rows = await wrong_question_state_dao.get_dashboard_rows(
            db,
            user_id=user_id,
            since=now - timedelta(days=DASHBOARD_WINDOW_DAYS),
            knowledge_system_ids=knowledge_system_ids,
            domain_category_ids=domain_category_ids,
        )
        return GetWrongReviewDashboard(
            reviewed_count=statistics['reviewed_count'],
            active_reviewed_count=statistics.get('active_reviewed_count', 0),
            pending_review_count=statistics['pending_review_count'],
            review_event_count=event_count,
            reason_distribution=[WrongReviewDistributionItem(**row) for row in reason_rows],
            knowledge_point_distribution=WrongReviewService._build_knowledge_distribution(knowledge_rows),
        )

    @staticmethod
    def _build_knowledge_distribution(rows: Sequence[dict[str, Any]]) -> list[WrongReviewDistributionItem]:
        """把已去重汇总的节点接回父链，只展开知识体系总节点，不展开单个大模块。"""
        nodes = {
            int(row['id']): WrongReviewDistributionItem(
                id=int(row['id']), name=str(row['name']), count=int(row['count']), color=None
            )
            for row in rows
            if int(row['count']) > 0
        }
        roots: list[WrongReviewDistributionItem] = []
        system_names: dict[int, str] = {}
        for row in rows:
            point_id = int(row['id'])
            if point_id not in nodes:
                continue
            parent_id = row.get('parent_id')
            if parent_id is None:
                roots.append(nodes[point_id])
                system_names[point_id] = str(row.get('system_name') or '')
            elif int(parent_id) in nodes:
                nodes[int(parent_id)].children.append(nodes[point_id])

        core_modules = {'判断推理', '资料分析', '言语理解', '数量关系', '常识判断', '政治理论'}
        modules: list[WrongReviewDistributionItem] = []
        for root in roots:
            if root.name == system_names[root.id] and root.name not in core_modules:
                modules.extend(root.children)
            else:
                modules.append(root)
        return sorted(modules, key=lambda item: (-item.count, item.id))

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
        domain_category_ids = await WrongReviewService.resolve_domain_scope(
            db=db,
            user_id=user_id,
            domain_category_id=domain_category_id,
        )
        statistics = await wrong_question_state_dao.get_statistics(
            db,
            user_id=user_id,
            now=timezone.now(),
            domain_category_ids=domain_category_ids,
        )
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
            domain_category_ids=domain_category_ids,
        )
        if group_by == 'knowledge_point':
            # 题库来源的错题按知识体系补全父链，外部录入的知识点不属于当前体系，保持平铺
            bank_rows = [row for row in rows if row.get('entry_scope') != 'external']
            external_rows = [row for row in rows if row.get('entry_scope') == 'external']
            groups = await content_group_service.build_knowledge_tree(db=db, rows=bank_rows)
            if external_rows:
                external_nodes = [
                    ContentGroupNode(
                        id=row['id'],
                        name=row['name'],
                        count=int(row['count'] or 0),
                        question_ids=row.get('question_ids') or [],
                    )
                    for row in external_rows
                ]
                groups.append(
                    ContentGroupNode(
                        id=0,
                        name='自主录入',
                        count=sum(node.count for node in external_nodes),
                        children=external_nodes,
                    )
                )
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
    async def _resolve_recorded_domain_id(*, db: AsyncSession, user_id: int) -> int | None:
        """解析要写入错题 entry_metadata 的领域分类 ID

        优先取用户偏好里的当前领域；拿不到时回落到公考领域根分类，
        避免「历史账号没设过领域 → 导入的错题在小程序列表里被领域过滤掉」。
        回落失败不报错，保持原有「不写领域 = 不过滤」的语义。
        """
        resolved = await knowledge_service.resolve_optional_domain_category_id(db=db, user_id=user_id)
        if resolved is not None:
            return int(resolved)

        # 兜底 1：按领域编码查公考根分类
        try:
            category = await category_dao.get_by_code(
                db, DEFAULT_DOMAIN_APP_CODE, DEFAULT_DOMAIN_CATEGORY_TYPE, DEFAULT_DOMAIN_CATEGORY_CODE
            )
        except Exception:
            category = None
        if category is not None:
            return int(category.id)

        # 兜底 2：按领域名称查公考根分类
        try:
            category = await category_dao.get_by_name(
                db, DEFAULT_DOMAIN_APP_CODE, DEFAULT_DOMAIN_CATEGORY_TYPE, DEFAULT_DOMAIN_CATEGORY_NAME
            )
        except Exception:
            category = None
        if category is not None:
            return int(category.id)

        return None

    @staticmethod
    async def capture_external_batch(
        *,
        db: AsyncSession,
        user_id: int,
        items: Sequence[CreateExternalWrongQuestionParam],
        import_batch_id: str | None = None,
    ) -> BatchImportResult:
        """批量录入外部错题（单条失败不影响其余题目入库）

        每条题目用独立的 savepoint 隔离：任何一条抛异常（含幂等键冲突）只回滚它自己，
        不会把整个会话推进 aborted 状态导致后续题目全部失败。
        分片提交时由客户端通过请求头传入同一个 import_batch_id，保证整批共享同一批次。
        """
        if not items:
            raise errors.RequestError(msg='批量录入的错题不能为空')
        if len(items) > BATCH_IMPORT_LIMIT:
            raise errors.RequestError(msg=f'单次批量录入不能超过 {BATCH_IMPORT_LIMIT} 道题')

        batch_id = (import_batch_id or '').strip() or uuid.uuid4().hex
        succeeded_items: list[BatchImportItemResult] = []
        failures: list[BatchImportFailure] = []
        # 同批次内共享材料：link_key 相同只建一份材料实体
        material_cache: dict[str, tuple[int, int]] = {}
        # 一次 IN 查询把整批的外部键查重做完，避免逐题扫描用户错题表
        existing_lookup = await WrongReviewService._find_existing_external_state_ids(
            db=db,
            user_id=user_id,
            keys=[(obj.source_system, obj.external_key) for obj in items if obj.source_system and obj.external_key],
        )
        recorded_domain_id = await WrongReviewService._resolve_recorded_domain_id(db=db, user_id=user_id)

        for index, obj in enumerate(items):
            # 每条题从已成功条目的缓存快照开始，savepoint 释放后再并入共享缓存：
            # 失败条目创建的材料已随 savepoint 回滚，不能留在缓存里被后续题目引用
            item_cache = material_cache.copy()
            try:
                async with db.begin_nested():
                    captured = await WrongReviewService._capture_external(
                        db=db,
                        user_id=user_id,
                        obj=obj,
                        recorded_domain_id=recorded_domain_id,
                        import_batch_id=batch_id,
                        material_cache=item_cache,
                        existing_lookup=existing_lookup,
                    )
                material_cache.update(item_cache)
                # 同批次内重复的键后续也能命中，避免建出第二份
                if obj.source_system and obj.external_key:
                    existing_lookup[obj.source_system, obj.external_key] = captured.wrong_state_id
                succeeded_items.append(captured)
            except IntegrityError:
                failures.append(
                    BatchImportFailure(
                        index=index,
                        external_key=obj.external_key,
                        reason='该题已导入过（幂等键冲突）',
                    )
                )
            except Exception as exc:
                failures.append(
                    BatchImportFailure(
                        index=index,
                        external_key=obj.external_key,
                        reason=str(exc)[:200] or '未知错误',
                    )
                )

        return BatchImportResult(
            import_batch_id=batch_id,
            total=len(items),
            succeeded=len(succeeded_items),
            failed=len(failures),
            items=succeeded_items,
            failures=failures,
        )

    @staticmethod
    async def _soft_delete_wrong_states(
        *,
        db: AsyncSession,
        user_id: int,
        state_rows: Sequence[Any],
    ) -> BatchUndoResult | tuple[int, int, int]:
        """共用逻辑：软删一批错题状态、其复盘事件与可清理的私有题目"""
        state_ids = [row[0] for row in state_rows]
        question_ids = list({row[1] for row in state_rows})
        now = timezone.now()

        await db.execute(
            update(QbWrongQuestionState)
            .where(QbWrongQuestionState.id.in_(state_ids))
            # 软删标记必须写主键而不是 1：框架约定 deleted = 0 表示未删、非 0 表示已删，
            # 且 (user_id, question_id, deleted)、(user_id, idempotency_key, deleted) 这类唯一约束
            # 依赖软删行彼此不同，统一写 1 会让「撤销 → 重导 → 再撤销」触发唯一冲突。
            .values(deleted=QbWrongQuestionState.id, deleted_time=now, updated_by=user_id)
        )
        review_result = await db.execute(
            update(QbQuestionReview)
            .where(
                QbQuestionReview.user_id == user_id,
                QbQuestionReview.question_id.in_(question_ids),
                QbQuestionReview.deleted == 0,
            )
            # 这里必须写主键：幂等键唯一约束是 (user_id, idempotency_key, deleted)，
            # 若软删后一律写 1，「撤销 → 重导 → 再撤销」会与上一条已软删记录冲突
            .values(deleted=QbQuestionReview.id, deleted_time=now, updated_by=user_id)
        )
        still_referenced = select(QbWrongQuestionState.question_id).where(
            QbWrongQuestionState.user_id == user_id,
            QbWrongQuestionState.deleted == 0,
            QbWrongQuestionState.question_id.in_(question_ids),
        )
        deletable_question_ids = (
            (
                await db.execute(
                    select(QbQuestion.id).where(
                        QbQuestion.id.in_(question_ids),
                        QbQuestion.owner_id == user_id,
                        QbQuestion.visibility == 'private',
                        QbQuestion.deleted == 0,
                        QbQuestion.id.not_in(still_referenced),
                    )
                )
            )
            .scalars()
            .all()
        )
        if deletable_question_ids:
            await db.execute(
                update(QbQuestion)
                .where(QbQuestion.id.in_(deletable_question_ids))
                .values(deleted=QbQuestion.id, deleted_time=now, updated_by=user_id)
            )

        # 4. 材料清理（三层判断）：解除关联 → 零引用 → 本人创建 才软删
        deleted_materials = await WrongReviewService._cleanup_orphan_materials(
            db=db,
            user_id=user_id,
            question_ids=question_ids,
            now=now,
        )

        await db.flush()
        return (
            len(state_ids),
            len(deletable_question_ids),
            int(review_result.rowcount or 0),
            deleted_materials,
        )

    @staticmethod
    async def _cleanup_orphan_materials(
        *,
        db: AsyncSession,
        user_id: int,
        question_ids: Sequence[int],
        now: Any,
    ) -> int:
        """解除题目材料关联，并回收「零引用且本人创建」的孤儿材料

        ① 还有其他未删除题目引用 → 只解除关联，不删材料（跨批次/跨用户共享安全）
        ② 材料不是本人创建的 → 不删
        ③ 零引用且本人创建 → 软删材料及其版本
        """
        material_ids = (
            (
                await db.execute(
                    select(QbQuestionMaterial.material_id)
                    .where(
                        QbQuestionMaterial.question_id.in_(question_ids),
                        QbQuestionMaterial.deleted == 0,
                    )
                    .distinct()
                )
            )
            .scalars()
            .all()
        )
        if not material_ids:
            return 0

        await db.execute(
            update(QbQuestionMaterial)
            .where(
                QbQuestionMaterial.question_id.in_(question_ids),
                QbQuestionMaterial.deleted == 0,
            )
            .values(deleted=QbQuestionMaterial.id, deleted_time=now, updated_by=user_id)
        )

        still_used = set(
            (
                await db.execute(
                    select(QbQuestionMaterial.material_id)
                    .where(
                        QbQuestionMaterial.material_id.in_(material_ids),
                        QbQuestionMaterial.deleted == 0,
                    )
                    .distinct()
                )
            )
            .scalars()
            .all()
        )
        orphan_ids = [material_id for material_id in material_ids if material_id not in still_used]
        if not orphan_ids:
            return 0

        own_orphans = (
            (
                await db.execute(
                    select(QbMaterial.id).where(
                        QbMaterial.id.in_(orphan_ids),
                        QbMaterial.created_by == user_id,
                        QbMaterial.deleted == 0,
                    )
                )
            )
            .scalars()
            .all()
        )
        if not own_orphans:
            return 0

        await db.execute(
            update(QbMaterial)
            .where(QbMaterial.id.in_(own_orphans))
            .values(deleted=QbMaterial.id, deleted_time=now, updated_by=user_id)
        )
        await db.execute(
            update(QbMaterialRevision)
            .where(
                QbMaterialRevision.material_id.in_(own_orphans),
                QbMaterialRevision.deleted == 0,
            )
            .values(deleted=QbMaterialRevision.id, deleted_time=now, updated_by=user_id)
        )
        return len(own_orphans)

    @staticmethod
    async def get_collections_page(
        *,
        db: AsyncSession,
        user_id: int,
        mode: str = 'pending',
        domain_category_id: int | None = None,
        since: datetime | None = None,
        cursor: str | None = None,
        size: int = COLLECTION_PAGE_SIZE,
    ) -> WrongCollectionPage:
        """错题集合列表：题库 / 导入批次 / 散题

        统一按最近错题时间倒序（最新的在最上面）；时间相同再按当前页签的
        当前状态题数、集合 ID 降序。已掌握按移出时间排序；集合数量量级很小，排序与分页在内存中完成。
        """
        page_size = max(1, min(int(size or COLLECTION_PAGE_SIZE), COLLECTION_MAX_PAGE_SIZE))
        domain_category_ids = await WrongReviewService.resolve_domain_scope(
            db=db,
            user_id=user_id,
            domain_category_id=domain_category_id,
        )
        rows = await wrong_question_state_dao.get_collection_counts(
            db=db,
            user_id=user_id,
            status='resolved' if mode == 'mastered' else 'active',
            domain_category_ids=domain_category_ids,
            since=since,
        )

        sort_field = {'pending': 'pending', 'reviewed': 'reviewed', 'mastered': 'mastered'}[mode]
        # 三个页签各自只保留「有该类题目」的集合。
        rows = [row for row in rows if int(row[sort_field]) > 0]
        rows.sort(
            key=lambda row: (
                row['last_time'] or datetime.min.replace(tzinfo=timezone.tz_info),
                int(row[sort_field]),
                row['collection_id'],
            ),
            reverse=True,
        )

        offset = WrongReviewService._parse_cursor_id(cursor) or 0
        page_rows = rows[offset : offset + page_size]
        has_more = offset + page_size < len(rows)

        return WrongCollectionPage(
            items=[WrongCollectionItem(**row) for row in page_rows],
            total=await wrong_question_state_dao.get_browse_total(
                db,
                user_id=user_id,
                status='resolved' if mode == 'mastered' else 'active',
                review_state=None if mode == 'mastered' else mode,
                domain_category_ids=domain_category_ids,
                since=since,
            ),
            next_cursor=str(offset + page_size) if has_more else None,
            has_more=has_more,
        )

    @staticmethod
    def _parse_cursor_id(cursor: str | None) -> int | None:
        """解析游标：本项目游标就是上一页最后一行的自增 ID"""
        text = (cursor or '').strip()
        if not text:
            return None
        try:
            value = int(text)
        except (TypeError, ValueError):
            return None
        return value if value > 0 else None

    @staticmethod
    async def get_import_batches_page(
        *,
        db: AsyncSession,
        user_id: int,
        cursor: str | None = None,
        size: int = IMPORT_HISTORY_PAGE_SIZE,
    ) -> ImportBatchPage:
        """导入批次列表（游标分页，按批次内最大状态 ID 倒序）

        批次由 import_batch_id 聚合而来，没有可直接排序的物理列，
        因此以「批次内最大状态 ID」作为游标键——它随导入时间单调递增，分页不会漏批次。
        """
        page_size = max(1, min(int(size or IMPORT_HISTORY_PAGE_SIZE), IMPORT_HISTORY_MAX_PAGE_SIZE))
        cursor_id = WrongReviewService._parse_cursor_id(cursor)

        batch_id_expr = QbWrongQuestionState.entry_metadata[ENTRY_METADATA_BATCH_KEY].as_string()
        last_state_id = func.max(QbWrongQuestionState.id)
        stmt = (
            select(
                batch_id_expr.label('batch_id'),
                func.min(QbWrongQuestionState.entry_metadata['source'].as_string()).label('source'),
                func.count().label('total'),
                func.sum(case((QbWrongQuestionState.status == 'active', 1), else_=0)).label('active'),
                func.min(QbWrongQuestionState.created_time).label('first_time'),
                func.max(QbWrongQuestionState.created_time).label('last_time'),
                last_state_id.label('last_state_id'),
            )
            .where(
                QbWrongQuestionState.user_id == user_id,
                QbWrongQuestionState.deleted == 0,
                batch_id_expr.is_not(None),
            )
            .group_by(literal_column('1'))
        )
        if cursor_id is not None:
            stmt = stmt.having(last_state_id < cursor_id)
        stmt = stmt.order_by(last_state_id.desc()).limit(page_size + 1)

        rows = (await db.execute(stmt)).mappings().all()
        has_more = len(rows) > page_size
        rows = rows[:page_size]

        return ImportBatchPage(
            items=[
                ImportHistoryBatchItem(
                    import_batch_id=str(row['batch_id']),
                    source=row['source'],
                    total=int(row['total'] or 0),
                    active=int(row['active'] or 0),
                    first_time=row['first_time'],
                    last_time=row['last_time'],
                )
                for row in rows
            ],
            next_cursor=str(rows[-1]['last_state_id']) if has_more and rows else None,
            has_more=has_more,
        )

    @staticmethod
    async def get_import_singles_page(
        *,
        db: AsyncSession,
        user_id: int,
        cursor: str | None = None,
        size: int = IMPORT_HISTORY_PAGE_SIZE,
    ) -> ImportSinglePage:
        """无批次的散题列表（游标分页，按错题状态 ID 倒序）"""
        page_size = max(1, min(int(size or IMPORT_HISTORY_PAGE_SIZE), IMPORT_HISTORY_MAX_PAGE_SIZE))
        cursor_id = WrongReviewService._parse_cursor_id(cursor)

        stmt = (
            select(
                QbWrongQuestionState.id,
                QbWrongQuestionState.question_id,
                QbWrongQuestionState.entry_source,
                QbWrongQuestionState.created_time,
                QbWrongQuestionState.entry_metadata['source'].as_string().label('source'),
                QbQuestion.stem,
            )
            .join(QbQuestion, QbQuestion.id == QbWrongQuestionState.question_id)
            .where(
                QbWrongQuestionState.user_id == user_id,
                QbWrongQuestionState.deleted == 0,
                QbWrongQuestionState.entry_source.in_(EXTERNAL_ENTRY_SOURCES),
                QbWrongQuestionState.entry_metadata[ENTRY_METADATA_BATCH_KEY].as_string().is_(None),
            )
        )
        if cursor_id is not None:
            stmt = stmt.where(QbWrongQuestionState.id < cursor_id)
        stmt = stmt.order_by(QbWrongQuestionState.id.desc()).limit(page_size + 1)

        rows = (await db.execute(stmt)).mappings().all()
        has_more = len(rows) > page_size
        rows = rows[:page_size]

        return ImportSinglePage(
            items=[
                ImportHistorySingleItem(
                    id=row['id'],
                    question_id=row['question_id'],
                    entry_source=row['entry_source'],
                    source=row['source'],
                    stem=row['stem'] or '',
                    created_time=row['created_time'],
                )
                for row in rows
            ],
            next_cursor=str(rows[-1]['id']) if has_more and rows else None,
            has_more=has_more,
        )

    @staticmethod
    async def delete_external_wrong_question(
        *,
        db: AsyncSession,
        user_id: int,
        wrong_state_id: int,
    ) -> BatchUndoResult:
        """删除单条外部录入的错题（散题撤销）"""
        row = (
            await db.execute(
                select(QbWrongQuestionState.id, QbWrongQuestionState.question_id).where(
                    QbWrongQuestionState.id == wrong_state_id,
                    QbWrongQuestionState.user_id == user_id,
                    QbWrongQuestionState.deleted == 0,
                )
            )
        ).first()
        if row is None:
            raise errors.NotFoundError(msg='错题不存在或已删除')

        (
            deleted_states,
            deleted_questions,
            deleted_reviews,
            deleted_materials,
        ) = await WrongReviewService._soft_delete_wrong_states(
            db=db,
            user_id=user_id,
            state_rows=[row],
        )
        return BatchUndoResult(
            import_batch_id='',
            deleted_states=deleted_states,
            deleted_questions=deleted_questions,
            deleted_reviews=deleted_reviews,
            deleted_materials=deleted_materials,
        )

    @staticmethod
    async def undo_import_batch(
        *,
        db: AsyncSession,
        user_id: int,
        import_batch_id: str,
    ) -> BatchUndoResult:
        """撤销一次批量导入：软删该批次带进来的错题状态、题目与复盘事件

        只处理当前用户自己、且 entry_metadata.import_batch_id 匹配的记录；
        题目仅在「本人私有且不再被其他错题状态引用」时才清理，避免误删仍在使用的内容。
        """
        batch_id = (import_batch_id or '').strip()
        if not batch_id:
            raise errors.RequestError(msg='批次 ID 不能为空')

        state_rows = (
            await db.execute(
                select(QbWrongQuestionState.id, QbWrongQuestionState.question_id).where(
                    QbWrongQuestionState.user_id == user_id,
                    QbWrongQuestionState.deleted == 0,
                    QbWrongQuestionState.entry_metadata[ENTRY_METADATA_BATCH_KEY].as_string() == batch_id,
                )
            )
        ).all()
        if not state_rows:
            raise errors.NotFoundError(msg='未找到该导入批次，可能已被撤销')

        (
            deleted_states,
            deleted_questions,
            deleted_reviews,
            deleted_materials,
        ) = await WrongReviewService._soft_delete_wrong_states(
            db=db,
            user_id=user_id,
            state_rows=state_rows,
        )
        return BatchUndoResult(
            import_batch_id=batch_id,
            deleted_states=deleted_states,
            deleted_questions=deleted_questions,
            deleted_reviews=deleted_reviews,
            deleted_materials=deleted_materials,
        )

    @staticmethod
    async def _build_material_links(
        *,
        db: AsyncSession,
        user_id: int,
        materials: Sequence[Any],
        cache: dict[str, tuple[int, int]] | None = None,
    ) -> list[QuestionMaterialParam]:
        """把内联材料落成真正的材料实体，返回待关联列表"""
        shared = cache if cache is not None else {}
        links: list[QuestionMaterialParam] = []

        for item in materials:
            key = (item.link_key or '').strip()
            reference = shared.get(key) if key else None

            if reference is None:
                # 跨批次复用：同一用户导入过完全相同标题+正文的材料时直接沿用，
                # 避免同一篇资料在每次导入时各存一份（不跨用户，避免串号）
                existing = (
                    await db.execute(
                        select(QbQuestionMaterial.material_id, QbQuestionMaterial.material_revision_id)
                        .join(QbMaterial, QbMaterial.id == QbQuestionMaterial.material_id)
                        .join(
                            QbMaterialRevision,
                            QbMaterialRevision.id == QbQuestionMaterial.material_revision_id,
                        )
                        .where(
                            QbMaterial.created_by == user_id,
                            QbMaterial.deleted == 0,
                            QbMaterial.status == 'active',
                            QbMaterialRevision.deleted == 0,
                            QbMaterialRevision.status.in_(('published', 'retired')),
                            QbMaterialRevision.title == item.title,
                            QbMaterialRevision.content == item.content,
                            QbMaterialRevision.content_format == item.content_format,
                        )
                        .order_by(QbMaterial.id.desc())
                        .limit(1)
                    )
                ).first()

                if existing is not None:
                    reference = (int(existing[0]), int(existing[1]))

            if reference is None:
                detail = await material_service.create(
                    db=db,
                    obj=CreateMaterialParam(
                        code=f'usr.{user_id}.mat.{uuid.uuid4().hex}',
                        status='active',
                        revision=CreateMaterialRevisionParam(
                            title=item.title,
                            content=item.content,
                            content_format=item.content_format,
                        ),
                    ),
                    created_by=user_id,
                )
                if detail.revision is None:
                    raise errors.RequestError(msg='材料创建失败：缺少草稿版本')
                await material_service.publish_revision(
                    db=db,
                    material_id=detail.id,
                    revision_id=detail.revision.id,
                    published_by=user_id,
                )
                reference = (detail.id, detail.revision.id)

            if key and reference is not None:
                shared[key] = reference

            links.append(
                QuestionMaterialParam(
                    material_id=reference[0],
                    material_revision_id=reference[1],
                    role=item.role,
                    sort_order=item.sort_order,
                )
            )
        return links

    @staticmethod
    async def _attach_materials(
        *,
        db: AsyncSession,
        user_id: int,
        question_id: int,
        materials: Sequence[Any],
        cache: dict[str, tuple[int, int]] | None = None,
    ) -> None:
        """把内联材料落成真正的材料实体并全量关联到题目"""
        links = await WrongReviewService._build_material_links(
            db=db,
            user_id=user_id,
            materials=materials,
            cache=cache,
        )
        await question_material_dao.replace(
            db,
            question_id=question_id,
            items=links,
            user_id=user_id,
        )

    @staticmethod
    async def _merge_materials(
        *,
        db: AsyncSession,
        user_id: int,
        question_id: int,
        materials: Sequence[Any],
        cache: dict[str, tuple[int, int]] | None = None,
    ) -> None:
        """复用题目时只追加缺失材料，保留题目已有材料"""
        existing = await question_material_dao.get_all(db, question_id)
        existing_keys = {
            (
                str(row.get('title') or ''),
                str(row.get('content') or ''),
                str(row.get('content_format') or ''),
                str(row.get('role') or ''),
            )
            for row in existing
        }
        missing = [
            item
            for item in materials
            if (
                str(item.title or ''),
                str(item.content or ''),
                str(item.content_format or ''),
                str(item.role or ''),
            )
            not in existing_keys
        ]
        if not missing:
            return
        links = [
            QuestionMaterialParam(
                material_id=int(row['material_id']),
                material_revision_id=int(row['material_revision_id']),
                role=row.get('role'),
                sort_order=int(row.get('sort_order') or 0),
            )
            for row in existing
        ]
        links.extend(
            await WrongReviewService._build_material_links(
                db=db,
                user_id=user_id,
                materials=missing,
                cache=cache,
            )
        )
        await question_material_dao.replace(
            db,
            question_id=question_id,
            items=links,
            user_id=user_id,
        )

    @staticmethod
    async def _find_existing_external_state_ids(
        *,
        db: AsyncSession,
        user_id: int,
        keys: Sequence[tuple[str, str]],
    ) -> dict[tuple[str, str], int]:
        """一次性批量查重：一次 IN 查询替代「每道题查一次」

        未走索引用 anyway 都是用户维度扫描，逐题查会让导入随数据量线性变慢；
        批量查询把 N 次扫描压成 1 次。
        """
        wanted = {(source, key) for source, key in keys if source and key}
        if not wanted:
            return {}

        external_key_expr = QbWrongQuestionState.entry_metadata[ENTRY_METADATA_EXTERNAL_KEY_KEY].as_string()
        rows = (
            (
                await db.execute(
                    select(
                        external_key_expr.label('external_key'),
                        QbWrongQuestionState
                        .entry_metadata[ENTRY_METADATA_SOURCE_SYSTEM_KEY]
                        .as_string()
                        .label('source_system'),
                        QbWrongQuestionState.id,
                    ).where(
                        QbWrongQuestionState.user_id == user_id,
                        QbWrongQuestionState.deleted == 0,
                        external_key_expr.in_([key for _, key in wanted]),
                    )
                )
            )
            .mappings()
            .all()
        )

        found: dict[tuple[str, str], int] = {}
        for row in rows:
            pair = (row['source_system'], row['external_key'])
            if pair in wanted and pair not in found:
                found[pair] = int(row['id'])
        return found

    @staticmethod
    async def _find_existing_external_state_id(
        *,
        db: AsyncSession,
        user_id: int,
        source_system: str | None,
        external_key: str | None,
    ) -> int | None:
        """按「来源系统 + 外部唯一键」查找同一道题已录入的错题状态

        重复导入直接复用已有记录，即使客户端清缓存、换设备、幂等键变化也不会重复建题。
        """
        if not source_system or not external_key:
            return None
        existing = (
            await db.execute(
                select(QbWrongQuestionState.id)
                .where(
                    QbWrongQuestionState.user_id == user_id,
                    QbWrongQuestionState.deleted == 0,
                    QbWrongQuestionState.entry_metadata[ENTRY_METADATA_SOURCE_SYSTEM_KEY].as_string() == source_system,
                    QbWrongQuestionState.entry_metadata[ENTRY_METADATA_EXTERNAL_KEY_KEY].as_string() == external_key,
                )
                .limit(1)
            )
        ).scalar()
        return int(existing) if existing is not None else None

    @staticmethod
    async def _reuse_or_create_question(
        *,
        db: AsyncSession,
        user_id: int,
        obj: CreateExternalWrongQuestionParam,
    ) -> tuple[QbQuestion, bool]:
        """同一用户下内容一致即复用已有私有题，与刷题记录导入共用一份题目"""
        content_hash = question_content_digest(
            stem=obj.stem,
            content_format=obj.content_format,
            question_type=obj.question_type,
            options=[item.model_dump(mode='json') for item in obj.options],
        )
        question = await external_practice_dao.find_reusable_question(db, user_id=user_id, content_hash=content_hash)
        if question is not None:
            return question, True
        return (
            await question_dao.create(
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
                content_hash=content_hash,
                created_by=user_id,
            ),
            False,
        )

    @staticmethod
    async def _find_state_id_by_question(db: AsyncSession, *, user_id: int, question_id: int) -> int | None:
        """复用题目时若已有错题状态，直接返回原状态，避免唯一约束冲突"""
        state = await wrong_question_state_dao.get_by_question(
            db, user_id=user_id, question_id=question_id, for_update=True
        )
        return state.id if state is not None else None

    @staticmethod
    async def _fill_missing_content(
        *,
        db: AsyncSession,
        user_id: int,
        question: QbQuestion,
        obj: CreateExternalWrongQuestionParam,
        material_cache: dict[str, tuple[int, int]] | None = None,
    ) -> None:
        """复用已有题目时只补缺失的答案、解析、资产和材料，不覆盖原内容"""
        has_answer = (
            await db.execute(
                select(QbQuestionAnswer.id)
                .where(QbQuestionAnswer.question_id == question.id, QbQuestionAnswer.deleted == 0)
                .limit(1)
            )
        ).scalar() is not None
        if not has_answer:
            await question_answer_dao.upsert(db, question_id=question.id, obj=obj.answer, user_id=user_id)
        if obj.explanations:
            has_explanation = (
                await db.execute(
                    select(QbQuestionExplanation.id)
                    .where(
                        QbQuestionExplanation.question_id == question.id,
                        QbQuestionExplanation.deleted == 0,
                    )
                    .limit(1)
                )
            ).scalar() is not None
            if not has_explanation:
                await question_explanation_dao.replace(
                    db,
                    question_id=question.id,
                    items=obj.explanations,
                    user_id=user_id,
                    status='published',
                )
        if obj.assets:
            existing_keys = {
                key
                for key in (
                    await db.execute(
                        select(QbQuestionAsset.link_key).where(
                            QbQuestionAsset.question_id == question.id,
                            QbQuestionAsset.deleted == 0,
                        )
                    )
                )
                .scalars()
                .all()
                if key
            }
            missing_assets = [item for item in obj.assets if not item.link_key or item.link_key not in existing_keys]
            if missing_assets:
                await review_reference_dao.create_question_asset_links(
                    db,
                    question_id=question.id,
                    items=missing_assets,
                    user_id=user_id,
                )
        if obj.materials:
            await WrongReviewService._merge_materials(
                db=db,
                user_id=user_id,
                question_id=question.id,
                materials=obj.materials,
                cache=material_cache,
            )

    @staticmethod
    async def _merge_knowledge_points(
        *,
        db: AsyncSession,
        user_id: int,
        question_id: int,
        knowledge_point_ids: list[int],
    ) -> None:
        """复用题目时把用户新选的知识点并入原有标注，不覆盖已有体系"""
        existing = await question_knowledge_point_dao.get_all(db, question_id)
        existing_ids = {int(row['knowledge_point_id']) for row in existing}
        items = [
            KnowledgePointAssignmentParam(
                knowledge_point_id=int(row['knowledge_point_id']),
                source=str(row.get('source') or 'manual'),
            )
            for row in existing
        ]
        items.extend(
            KnowledgePointAssignmentParam(knowledge_point_id=point_id, source='manual')
            for point_id in knowledge_point_ids
            if point_id not in existing_ids
        )
        if items:
            await question_knowledge_point_dao.replace(
                db,
                question_id=question_id,
                items=items,
                user_id=user_id,
            )

    @staticmethod
    async def _write_question_content(
        *,
        db: AsyncSession,
        user_id: int,
        question: QbQuestion,
        obj: CreateExternalWrongQuestionParam,
        reused: bool,
        material_cache: dict[str, tuple[int, int]] | None,
    ) -> None:
        """新题完整写入；复用题只补缺失内容，避免覆盖已有官方答案和解析"""
        if reused:
            await WrongReviewService._fill_missing_content(
                db=db,
                user_id=user_id,
                question=question,
                obj=obj,
                material_cache=material_cache,
            )
            await WrongReviewService._merge_knowledge_points(
                db=db,
                user_id=user_id,
                question_id=question.id,
                knowledge_point_ids=obj.knowledge_point_ids,
            )
            return
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
                status='published',
            )
        if obj.assets:
            await review_reference_dao.create_question_asset_links(
                db,
                question_id=question.id,
                items=obj.assets,
                user_id=user_id,
            )
        if obj.materials:
            await WrongReviewService._attach_materials(
                db=db,
                user_id=user_id,
                question_id=question.id,
                materials=obj.materials,
                cache=material_cache,
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

    @staticmethod
    async def _resolve_existing_state_id(
        *,
        db: AsyncSession,
        user_id: int,
        obj: CreateExternalWrongQuestionParam,
        existing_lookup: dict[tuple[str, str], int] | None = None,
    ) -> int | None:
        """解析该题是否已录入过：批量导入用预查好的映射，单条走即时查询"""
        if not obj.source_system or not obj.external_key:
            return None
        if existing_lookup is not None:
            return existing_lookup.get((obj.source_system, obj.external_key))
        return await WrongReviewService._find_existing_external_state_id(
            db=db,
            user_id=user_id,
            source_system=obj.source_system,
            external_key=obj.external_key,
        )

    @staticmethod
    async def _module_path_metadata(
        *,
        db: AsyncSession,
        user_id: int,
        question_id: int,
        section_name: str | None = None,
    ) -> dict[str, Any]:
        """从最近一次练习快照补原试卷模块路径，供章节内按题型聚拢。"""
        module_path = await question_attempt_dao.get_latest_module_path(
            db,
            user_id=user_id,
            question_id=question_id,
            section_name=section_name,
        )
        return {ENTRY_METADATA_MODULE_PATH_KEY: module_path} if module_path else {}

    @staticmethod
    async def _fill_existing_state_content(
        *,
        db: AsyncSession,
        user_id: int,
        wrong_state_id: int,
        obj: CreateExternalWrongQuestionParam,
        recorded_domain_id: int | None,
        material_cache: dict[str, tuple[int, int]] | None = None,
    ) -> QbWrongQuestionState:
        """重复录入时给已有错题补缺失内容；知识点需先校验，此处只补题目内容"""
        state = await wrong_question_state_dao.get(
            db,
            wrong_state_id,
            user_id=user_id,
            for_update=True,
        )
        if state is None:
            raise errors.NotFoundError(msg='错题不存在')
        question = await question_dao.get(db, state.question_id)
        if question is None:
            raise errors.NotFoundError(msg='错题不存在')
        await WrongReviewService._fill_missing_content(
            db=db,
            user_id=user_id,
            question=question,
            obj=obj,
            material_cache=material_cache,
        )
        # 只补缺失元数据，不覆盖已有批次/领域/章节，避免重复导入改变原归属
        metadata = dict(state.entry_metadata or {})
        changed = False
        for key, value in obj.entry_metadata.items():
            if value not in (None, '') and not metadata.get(key):
                metadata[key] = value
                changed = True
        if recorded_domain_id is not None and not metadata.get(ENTRY_METADATA_DOMAIN_KEY):
            metadata[ENTRY_METADATA_DOMAIN_KEY] = int(recorded_domain_id)
            changed = True
        if not metadata.get(ENTRY_METADATA_MODULE_PATH_KEY):
            module_metadata = await WrongReviewService._module_path_metadata(
                db=db,
                user_id=user_id,
                question_id=state.question_id,
                section_name=metadata.get(ENTRY_METADATA_SECTION_KEY),
            )
            if module_metadata:
                metadata.update(module_metadata)
                changed = True
        # 旧版本导入没有保存作答快照：重复导入时补上，不覆盖已有作答记录
        if obj.wrong_response is not None and state.last_wrong_response is None:
            state.last_wrong_response = obj.wrong_response
            changed = True
        if changed:
            state.entry_metadata = metadata
            await db.flush()
        return state

    @staticmethod
    async def capture_external(
        *,
        db: AsyncSession,
        user_id: int,
        obj: CreateExternalWrongQuestionParam,
        import_batch_id: str | None = None,
        material_cache: dict[str, tuple[int, int]] | None = None,
        existing_lookup: dict[tuple[str, str], int] | None = None,
    ) -> GetWrongQuestionDetail:
        """单条录入在共用写入核心之后装配一次详情。"""
        recorded_domain_id = await WrongReviewService._resolve_recorded_domain_id(db=db, user_id=user_id)
        captured = await WrongReviewService._capture_external(
            db=db,
            user_id=user_id,
            obj=obj,
            recorded_domain_id=recorded_domain_id,
            import_batch_id=import_batch_id,
            material_cache=material_cache,
            existing_lookup=existing_lookup,
        )
        return await WrongReviewService.get_detail(db=db, user_id=user_id, wrong_state_id=captured.wrong_state_id)

    @staticmethod
    async def _capture_external(
        *,
        db: AsyncSession,
        user_id: int,
        obj: CreateExternalWrongQuestionParam,
        recorded_domain_id: int | None,
        import_batch_id: str | None = None,
        material_cache: dict[str, tuple[int, int]] | None = None,
        existing_lookup: dict[tuple[str, str], int] | None = None,
    ) -> BatchImportItemResult:
        """将用户外部错题统一录入为可重练的私有题目

        existing_lookup 由批量导入预先查好（一次 IN 查询），避免逐题扫描用户错题表。
        批量与单条共用写入，只返回已有 ID，批量不逐题回读完整详情。
        """
        existing_state_id = await WrongReviewService._resolve_existing_state_id(
            db=db,
            user_id=user_id,
            obj=obj,
            existing_lookup=existing_lookup,
        )
        if existing_state_id is not None:
            # 外部 key 已存在时也补齐这次导入带来的答案/解析/材料，避免重复导入丢内容
            state = await WrongReviewService._fill_existing_state_content(
                db=db,
                user_id=user_id,
                wrong_state_id=existing_state_id,
                obj=obj,
                recorded_domain_id=recorded_domain_id,
                material_cache=material_cache,
            )
            return BatchImportItemResult(
                external_key=obj.external_key,
                question_id=state.question_id,
                wrong_state_id=existing_state_id,
            )

        await WrongReviewService._validate_links(
            db=db,
            user_id=user_id,
            tag_ids=obj.tag_ids,
            knowledge_point_ids=obj.knowledge_point_ids,
        )
        await WrongReviewService._validate_assets(db=db, user_id=user_id, obj=obj)

        # 自主录入的错题没有题库归属，把录入当时的领域记进 entry_metadata，
        # 之后按领域筛选待复盘/错题列表时才有依据（拿不到领域时不写，保持不过滤语义）
        entry_metadata = dict(obj.entry_metadata)
        if recorded_domain_id is not None:
            entry_metadata[ENTRY_METADATA_DOMAIN_KEY] = int(recorded_domain_id)
        # 批次标识：一次批量导入共享同一个 import_batch_id，整批撤销时按此归集
        if import_batch_id:
            entry_metadata[ENTRY_METADATA_BATCH_KEY] = import_batch_id
        # 来源标识：供跨设备/清缓存后的重复导入识别
        if obj.source_system:
            entry_metadata[ENTRY_METADATA_SOURCE_SYSTEM_KEY] = obj.source_system
        if obj.external_key:
            entry_metadata[ENTRY_METADATA_EXTERNAL_KEY_KEY] = obj.external_key

        question, reused = await WrongReviewService._reuse_or_create_question(
            db=db,
            user_id=user_id,
            obj=obj,
        )
        if not entry_metadata.get(ENTRY_METADATA_MODULE_PATH_KEY):
            entry_metadata.update(
                await WrongReviewService._module_path_metadata(
                    db=db,
                    user_id=user_id,
                    question_id=question.id,
                    section_name=entry_metadata.get(ENTRY_METADATA_SECTION_KEY),
                )
            )
        if reused:
            existing_state_id = await WrongReviewService._find_state_id_by_question(
                db=db,
                user_id=user_id,
                question_id=question.id,
            )
            if existing_state_id is not None:
                # 复用题目命中已有错题时，仍要把新导入的解析/材料补进去
                state = await WrongReviewService._fill_existing_state_content(
                    db=db,
                    user_id=user_id,
                    wrong_state_id=existing_state_id,
                    obj=obj,
                    recorded_domain_id=recorded_domain_id,
                    material_cache=material_cache,
                )
                await WrongReviewService._merge_knowledge_points(
                    db=db,
                    user_id=user_id,
                    question_id=question.id,
                    knowledge_point_ids=obj.knowledge_point_ids,
                )
                return BatchImportItemResult(
                    external_key=obj.external_key,
                    question_id=state.question_id,
                    wrong_state_id=existing_state_id,
                )
        await WrongReviewService._write_question_content(
            db=db,
            user_id=user_id,
            question=question,
            obj=obj,
            reused=reused,
            material_cache=material_cache,
        )

        now = timezone.now()
        await review_schedule_service.ensure_mastery(
            db=db,
            user_id=user_id,
            question_id=question.id,
            for_update=True,
        )
        source_attempt_stmt = (
            select(QbQuestionAttempt.id)
            .where(
                QbQuestionAttempt.user_id == user_id,
                QbQuestionAttempt.question_id == question.id,
                QbQuestionAttempt.deleted == 0,
            )
            .order_by(QbQuestionAttempt.submitted_time.desc(), QbQuestionAttempt.id.desc())
            .limit(1)
        )
        source_attempt_id = (await db.execute(source_attempt_stmt)).scalar_one_or_none()
        wrong_state = await wrong_question_state_dao.create(
            db,
            {
                'user_id': user_id,
                'question_id': question.id,
                'source_attempt_id': source_attempt_id,
                'entry_source': obj.entry_source,
                'entry_metadata': entry_metadata,
                'status': 'active',
                'wrong_count': 1,
                'first_wrong_time': now,
                'last_wrong_time': now,
                'last_wrong_response': obj.wrong_response,
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
                'source_attempt_id': source_attempt_id,
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
            (obj.summary and obj.summary.strip()) or obj.review_data or obj.tag_ids or obj.knowledge_point_ids
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
        return BatchImportItemResult(
            external_key=obj.external_key,
            question_id=question.id,
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
        if not has_review_thought(obj.summary, obj.review_data):
            raise errors.RequestError(msg=REVIEW_THOUGHT_REQUIRED_MESSAGE)
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
