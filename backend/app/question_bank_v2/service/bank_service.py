import hashlib
import json

from typing import Any

from sqlalchemy import Select, false, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.admin.crud.crud_category import category_dao
from backend.app.admin.model.category import Category
from backend.app.question_bank_v2.cache.catalog_cache import public_catalog_cache
from backend.app.question_bank_v2.crud.crud_bank import bank_category_dao, bank_dao, bank_revision_dao
from backend.app.question_bank_v2.crud.crud_composition import bank_item_dao, bank_section_dao
from backend.app.question_bank_v2.crud.crud_material import question_material_dao
from backend.app.question_bank_v2.crud.crud_question import (
    question_answer_dao,
    question_dao,
    question_explanation_dao,
)
from backend.app.question_bank_v2.model.bank import QbBankItem
from backend.app.question_bank_v2.model.question import QbQuestion
from backend.app.question_bank_v2.schema.bank import (
    CreateBankParam,
    CreateBankRevisionParam,
    GetBankCategoryDetail,
    GetBankDetail,
    GetBankListItem,
    GetBankRevisionDetail,
    SetBankCategoriesParam,
    UpdateBankParam,
    UpdateBankRevisionParam,
)
from backend.app.question_bank_v2.schema.composition import GetBankSectionDetail
from backend.app.question_bank_v2.schema.material import QuestionMaterialParam
from backend.app.question_bank_v2.service.access_service import bank_access_service
from backend.app.question_bank_v2.service.material_service import material_service
from backend.common.exception import errors
from backend.utils.timezone import timezone


class BankService:
    """题库服务类"""

    @staticmethod
    async def _validate_categories(*, db: AsyncSession, category_ids: list[int]) -> None:
        """校验题库业务分类存在且可用"""
        if not category_ids:
            return
        result = await db.execute(
            select(Category.id).where(
                Category.id.in_(category_ids),
                Category.deleted == 0,
                Category.status.is_(True),
            )
        )
        existing_ids = set(result.scalars().all())
        missing_ids = set(category_ids) - existing_ids
        if missing_ids:
            raise errors.NotFoundError(msg=f'业务分类不存在或已停用: {sorted(missing_ids)}')

    @staticmethod
    def _rollup_section_counts(node: GetBankSectionDetail) -> None:
        """把后代章节题量与题型分布汇总进父节点，与篇章进度树保持同一口径"""
        for child in node.children:
            BankService._rollup_section_counts(child)
            node.question_count += child.question_count
            for question_type, count in child.question_type_counts.items():
                node.question_type_counts[question_type] = node.question_type_counts.get(question_type, 0) + count

    @staticmethod
    async def _build_detail(*, db: AsyncSession, bank: Any, user_id: int | None = None) -> GetBankDetail:
        """组装题库聚合详情，包含章节树和题型统计"""
        revision = None
        if bank.current_revision_id is not None:
            current = await bank_revision_dao.get(db, bank.current_revision_id, bank_id=bank.id)
            if current is not None:
                revision = GetBankRevisionDetail.model_validate(current)
        categories = [GetBankCategoryDetail(**item) for item in await bank_category_dao.get_all(db, bank.id)]

        # 获取按章节 + 题型细分的题量，同时汇总出全库题型分布
        question_type_counts: dict[str, int] = {}
        section_type_counts: dict[int | None, dict[str, int]] = {}
        if bank.current_revision_id is not None:
            stmt = (
                select(
                    QbBankItem.section_id,
                    QbQuestion.question_type,
                    func.count(QbBankItem.id),
                )
                .join(QbQuestion, QbQuestion.id == QbBankItem.question_id)
                .where(
                    QbBankItem.bank_revision_id == bank.current_revision_id,
                    QbBankItem.is_active.is_(True),
                    QbBankItem.deleted == 0,
                )
                .group_by(QbBankItem.section_id, QbQuestion.question_type)
            )
            for section_id, question_type, count in await db.execute(stmt):
                count = int(count)
                question_type_counts[question_type] = question_type_counts.get(question_type, 0) + count
                section_type_counts.setdefault(section_id, {})[question_type] = count

        # 获取章节树，并把后代章节题量汇总到父节点
        sections: list[GetBankSectionDetail] = []
        if bank.current_revision_id is not None:
            db_sections = await bank_section_dao.get_all(db, revision_id=bank.current_revision_id)
            section_map: dict[int, GetBankSectionDetail] = {}
            for s in db_sections:
                detail = GetBankSectionDetail.model_validate(s)
                # model_validate 会带上空 children，建树前先清掉
                detail.children = []
                own_types = section_type_counts.get(s.id, {})
                detail.question_type_counts = dict(own_types)
                detail.question_count = sum(own_types.values())
                section_map[s.id] = detail
            section_children: dict[int | None, list[GetBankSectionDetail]] = {}
            for sd in section_map.values():
                section_children.setdefault(sd.parent_id, []).append(sd)
            for sid, sd in section_map.items():
                sd.children = section_children.get(sid, [])
            root_ids = [sid for sid in section_map if section_map[sid].parent_id not in section_map]
            sections = [section_map[sid] for sid in root_ids]
            for root in sections:
                BankService._rollup_section_counts(root)

        requires_entitlement, access_allowed = await bank_access_service.describe_bank_access(
            db=db,
            bank=bank,
            user_id=user_id,
        )

        return GetBankDetail(
            id=bank.id,
            code=bank.code,
            owner_id=bank.owner_id,
            current_revision_id=bank.current_revision_id,
            visibility=bank.visibility,
            status=bank.status,
            current_revision=revision,
            categories=categories,
            question_type_counts=question_type_counts,
            requires_entitlement=requires_entitlement,
            access_allowed=access_allowed,
            sections=sections,
            created_by=bank.created_by,
            updated_by=bank.updated_by,
            created_time=bank.created_time,
            updated_time=bank.updated_time,
        )

    @staticmethod
    async def _get_content_hash(*, db: AsyncSession, revision_id: int) -> str:
        """计算题库版本编排内容哈希"""
        stmt = (
            select(
                QbBankItem.item_key,
                QbBankItem.question_id,
                QbBankItem.section_id,
                QbBankItem.score,
                QbBankItem.sort_order,
                QbBankItem.is_required,
                QbBankItem.settings,
            )
            .where(
                QbBankItem.bank_revision_id == revision_id,
                QbBankItem.deleted == 0,
                QbBankItem.is_active.is_(True),
            )
            .order_by(QbBankItem.sort_order, QbBankItem.id)
        )
        result = await db.execute(stmt)
        payload = [
            {
                **dict(row),
                'score': str(row.score),
            }
            for row in result.mappings().all()
        ]
        raw = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(raw.encode()).hexdigest()

    @staticmethod
    async def get(
        *,
        db: AsyncSession,
        pk: int,
        public_only: bool = True,
        user_id: int | None = None,
    ) -> GetBankDetail:
        """获取题库详情"""
        bank = await bank_dao.get_public(db, pk) if public_only else await bank_dao.get(db, pk)
        if bank is None:
            raise errors.NotFoundError(msg='题库不存在')
        return await BankService._build_detail(db=db, bank=bank, user_id=user_id)

    @staticmethod
    async def get_list(
        *,
        db: AsyncSession,
        category_id: int | None = None,
        include_descendants: bool = True,
        bank_kind: str | None = None,
        keyword: str | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> list[GetBankListItem]:
        """获取公开题库列表"""
        category_ids = None
        if category_id is not None:
            if include_descendants:
                category_ids = await category_dao.get_subtree_ids_by_path(db, category_id, status=True)
            else:
                category_ids = [category_id]
            if not category_ids:
                return []

        rows = await bank_dao.get_public_list(
            db,
            category_ids=category_ids,
            bank_kind=bank_kind,
            keyword=keyword,
            offset=offset,
            limit=limit,
        )
        return [GetBankListItem(**row) for row in rows]

    @staticmethod
    async def get_select(
        *,
        db: AsyncSession,
        category_id: int | None = None,
        include_descendants: bool = True,
        bank_kind: str | None = None,
        keyword: str | None = None,
    ) -> Select:
        """获取公开题库列表 Select 查询句"""
        category_ids = None
        if category_id is not None:
            if include_descendants:
                category_ids = await category_dao.get_subtree_ids_by_path(db, category_id, status=True)
            else:
                category_ids = [category_id]
            if not category_ids:
                return select().where(false())

        return bank_dao.get_public_list_stmt(
            category_ids=category_ids,
            bank_kind=bank_kind,
            keyword=keyword,
        )

    @staticmethod
    def get_admin_select(*, bank_kind: str | None = None, keyword: str | None = None) -> Select:
        """获取管理端题库列表查询。"""
        return bank_dao.get_admin_list_stmt(bank_kind=bank_kind, keyword=keyword)

    @staticmethod
    async def create(*, db: AsyncSession, obj: CreateBankParam, created_by: int) -> GetBankDetail:
        """创建题库及首个草稿版本"""
        if await bank_dao.get_by_code(db, obj.code):
            raise errors.ConflictError(msg='题库编码已存在')
        await BankService._validate_categories(db=db, category_ids=obj.category_ids)

        owner_id = created_by if obj.visibility == 'private' else None
        bank = await bank_dao.create_bank(
            db,
            code=obj.code,
            owner_id=owner_id,
            visibility=obj.visibility,
            status=obj.status,
            created_by=created_by,
        )
        await bank_revision_dao.create(
            db,
            bank_id=bank.id,
            revision_no=1,
            obj=obj.revision,
            created_by=created_by,
        )
        await bank_category_dao.replace(
            db,
            bank_id=bank.id,
            category_ids=obj.category_ids,
            primary_category_id=obj.primary_category_id,
            user_id=created_by,
        )
        await public_catalog_cache.invalidate_prefix()
        return await BankService._build_detail(db=db, bank=bank)

    @staticmethod
    async def update(*, db: AsyncSession, pk: int, obj: UpdateBankParam, updated_by: int) -> GetBankDetail:
        """更新题库稳定身份"""
        bank = await bank_dao.get(db, pk)
        if bank is None:
            raise errors.NotFoundError(msg='题库不存在')
        data = obj.model_dump(exclude_unset=True)
        if 'code' in data and data['code'] != bank.code:
            existing = await bank_dao.get_by_code(db, data['code'])
            if existing is not None and existing.id != pk:
                raise errors.ConflictError(msg='题库编码已存在')
        if data.get('visibility') == 'private' and bank.owner_id is None:
            data['owner_id'] = updated_by
        elif data.get('visibility') in {'public', 'internal'}:
            data['owner_id'] = None
        if data:
            data['updated_by'] = updated_by
            await bank_dao.update(db, pk, data)
        bank = await bank_dao.get(db, pk)
        await public_catalog_cache.invalidate_prefix()
        return await BankService._build_detail(db=db, bank=bank)

    @staticmethod
    async def set_categories(
        *,
        db: AsyncSession,
        bank_id: int,
        obj: SetBankCategoriesParam,
        updated_by: int,
    ) -> list[GetBankCategoryDetail]:
        """设置题库业务分类"""
        if await bank_dao.get(db, bank_id) is None:
            raise errors.NotFoundError(msg='题库不存在')
        await BankService._validate_categories(db=db, category_ids=obj.category_ids)
        await bank_category_dao.replace(
            db,
            bank_id=bank_id,
            category_ids=obj.category_ids,
            primary_category_id=obj.primary_category_id,
            user_id=updated_by,
        )
        await public_catalog_cache.invalidate_prefix()
        return [GetBankCategoryDetail(**item) for item in await bank_category_dao.get_all(db, bank_id)]

    @staticmethod
    async def get_revisions(*, db: AsyncSession, bank_id: int) -> list[GetBankRevisionDetail]:
        """获取题库全部版本"""
        if await bank_dao.get(db, bank_id) is None:
            raise errors.NotFoundError(msg='题库不存在')
        revisions = await bank_revision_dao.get_all(db, bank_id)
        return [GetBankRevisionDetail.model_validate(item) for item in revisions]

    @staticmethod
    async def get_revisions_select(*, db: AsyncSession, bank_id: int) -> Select:
        """校验题库并构建版本游标分页查询"""
        if await bank_dao.get(db, bank_id) is None:
            raise errors.NotFoundError(msg='题库不存在')
        return bank_revision_dao.get_list_select(bank_id=bank_id)

    @staticmethod
    async def create_revision(
        *,
        db: AsyncSession,
        bank_id: int,
        obj: CreateBankRevisionParam,
        created_by: int,
    ) -> GetBankRevisionDetail:
        """创建题库草稿版本"""
        bank = await bank_dao.get(db, bank_id, for_update=True)
        if bank is None:
            raise errors.NotFoundError(msg='题库不存在')
        revision_no = await bank_revision_dao.get_next_revision_no(db, bank_id)
        revision = await bank_revision_dao.create(
            db,
            bank_id=bank_id,
            revision_no=revision_no,
            obj=obj,
            created_by=created_by,
        )
        return GetBankRevisionDetail.model_validate(revision)

    @staticmethod
    async def update_revision(
        *,
        db: AsyncSession,
        bank_id: int,
        revision_id: int,
        obj: UpdateBankRevisionParam,
        updated_by: int,
    ) -> GetBankRevisionDetail:
        """更新题库草稿版本"""
        revision = await bank_revision_dao.get(db, revision_id, bank_id=bank_id, for_update=True)
        if revision is None:
            raise errors.NotFoundError(msg='题库版本不存在')
        if revision.status != 'draft':
            raise errors.ConflictError(msg='已发布或已退役版本不可修改')
        data = obj.model_dump(exclude_unset=True)
        if data:
            data['updated_by'] = updated_by
            await bank_revision_dao.update(db, revision_id, data)
            revision = await bank_revision_dao.get(db, revision_id, bank_id=bank_id)
        return GetBankRevisionDetail.model_validate(revision)

    @staticmethod
    async def publish_revision(
        *,
        db: AsyncSession,
        bank_id: int,
        revision_id: int,
        published_by: int,
    ) -> GetBankRevisionDetail:
        """发布题库版本并原子切换当前版本"""
        bank = await bank_dao.get(db, bank_id, for_update=True)
        if bank is None:
            raise errors.NotFoundError(msg='题库不存在')
        revision = await bank_revision_dao.get(db, revision_id, bank_id=bank_id, for_update=True)
        if revision is None:
            raise errors.NotFoundError(msg='题库版本不存在')
        if revision.status != 'draft':
            raise errors.ConflictError(msg='仅草稿版本可以发布')

        await BankService._validate_revision_publishable(db=db, revision_id=revision_id)
        question_count, total_score = await bank_revision_dao.recalculate_totals(db, revision_id)
        if question_count == 0:
            raise errors.ConflictError(msg='空题库版本不能发布')
        content_hash = await BankService._get_content_hash(db=db, revision_id=revision_id)
        now = timezone.now()
        if bank.current_revision_id is not None and bank.current_revision_id != revision_id:
            await bank_revision_dao.update_model_by_column(
                db,
                {'status': 'retired', 'updated_by': published_by},
                id=bank.current_revision_id,
                bank_id=bank_id,
                deleted=0,
                status='published',
            )
        await bank_revision_dao.update_model_by_column(
            db,
            {
                'status': 'published',
                'question_count': question_count,
                'total_score': total_score,
                'content_hash': content_hash,
                'published_by': published_by,
                'published_time': now,
                'updated_by': published_by,
            },
            id=revision_id,
            bank_id=bank_id,
            deleted=0,
            status='draft',
        )
        await bank_dao.update(
            db,
            bank_id,
            {'current_revision_id': revision_id, 'updated_by': published_by},
        )
        revision = await bank_revision_dao.get(db, revision_id, bank_id=bank_id)
        await public_catalog_cache.invalidate_prefix()
        return GetBankRevisionDetail.model_validate(revision)

    @staticmethod
    async def _validate_revision_publishable(*, db: AsyncSession, revision_id: int) -> None:
        """Validate active questions before publishing a bank revision."""
        from backend.app.question_bank_v2.service.interaction_service import interaction_service
        from backend.app.question_bank_v2.service.question_service import QuestionService

        items = [item for item in await bank_item_dao.get_all(db, revision_id) if item['is_active']]
        if not items:
            raise errors.ConflictError(msg='空题库版本不能发布')
        for item in items:
            question = await question_dao.get(db, item['question_id'])
            if question is None or question.status != 'active':
                raise errors.ConflictError(msg=f'题目 {item["question_id"]} 不可发布')
            answer = await question_answer_dao.get_by_question(db, question.id)
            if answer is None:
                raise errors.ConflictError(msg=f'题目 {question.id} 缺少权威答案')
            QuestionService._validate_answer(
                question_type=question.question_type,
                options=question.option_data,
                answer_data=answer.answer_data,
            )
            explanations = await question_explanation_dao.get_all(db, question.id)
            published = [item for item in explanations if item.status == 'published']
            if sum(item.is_default for item in published) != 1:
                raise errors.ConflictError(msg=f'题目 {question.id} 必须有一个已发布默认解析')
            materials = await question_material_dao.get_all(db, question.id)
            await material_service.ensure_references(
                db=db,
                items=[
                    QuestionMaterialParam.model_validate(
                        item,
                        from_attributes=True,
                    )
                    for item in materials
                ],
                publishable=True,
            )
            await interaction_service.ensure_publishable(
                db=db,
                question_id=question.id,
                question_type=question.question_type,
            )


bank_service: BankService = BankService()
