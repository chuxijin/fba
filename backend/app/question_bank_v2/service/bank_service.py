import hashlib
import json

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.admin.crud.crud_category import category_dao
from backend.app.admin.model.category import Category
from backend.app.question_bank_v2.crud.crud_bank import bank_category_dao, bank_dao, bank_revision_dao
from backend.app.question_bank_v2.model.bank import QbBankItem
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
    async def _build_detail(*, db: AsyncSession, bank: Any) -> GetBankDetail:
        """组装题库聚合详情"""
        revision = None
        if bank.current_revision_id is not None:
            current = await bank_revision_dao.get(db, bank.current_revision_id, bank_id=bank.id)
            if current is not None:
                revision = GetBankRevisionDetail.model_validate(current)
        categories = [GetBankCategoryDetail(**item) for item in await bank_category_dao.get_all(db, bank.id)]
        return GetBankDetail(
            id=bank.id,
            code=bank.code,
            owner_id=bank.owner_id,
            current_revision_id=bank.current_revision_id,
            visibility=bank.visibility,
            status=bank.status,
            current_revision=revision,
            categories=categories,
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
                QbBankItem.question_revision_id,
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
    async def get(*, db: AsyncSession, pk: int, public_only: bool = True) -> GetBankDetail:
        """获取题库详情"""
        bank = await bank_dao.get_public(db, pk) if public_only else await bank_dao.get(db, pk)
        if bank is None:
            raise errors.NotFoundError(msg='题库不存在')
        return await BankService._build_detail(db=db, bank=bank)

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
        return [GetBankCategoryDetail(**item) for item in await bank_category_dao.get_all(db, bank_id)]

    @staticmethod
    async def get_revisions(*, db: AsyncSession, bank_id: int) -> list[GetBankRevisionDetail]:
        """获取题库全部版本"""
        if await bank_dao.get(db, bank_id) is None:
            raise errors.NotFoundError(msg='题库不存在')
        revisions = await bank_revision_dao.get_all(db, bank_id)
        return [GetBankRevisionDetail.model_validate(item) for item in revisions]

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
        return GetBankRevisionDetail.model_validate(revision)


bank_service: BankService = BankService()
