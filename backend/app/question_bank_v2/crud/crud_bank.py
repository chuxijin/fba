from collections.abc import Sequence
from decimal import Decimal
from typing import Any

from sqlalchemy import Select, and_, exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.admin.model.category import Category
from backend.app.question_bank_v2.model.bank import QbBank, QbBankRevision
from backend.app.question_bank_v2.model.catalog import QbBankCategory
from backend.app.question_bank_v2.schema.bank import CreateBankRevisionParam


class CRUDBank(CRUDPlus[QbBank]):
    """题库稳定身份数据库操作类"""

    @staticmethod
    def _active_stmt() -> Select[tuple[QbBank]]:
        return select(QbBank).where(QbBank.deleted == 0)

    async def get(self, db: AsyncSession, pk: int, *, for_update: bool = False) -> QbBank | None:
        """获取题库稳定身份"""
        stmt = self._active_stmt().where(QbBank.id == pk)
        if for_update:
            stmt = stmt.with_for_update()
        result = await db.execute(stmt)
        return result.scalars().first()

    async def get_by_code(self, db: AsyncSession, code: str) -> QbBank | None:
        """通过业务编码获取题库"""
        result = await db.execute(self._active_stmt().where(QbBank.code == code))
        return result.scalars().first()

    async def get_public(self, db: AsyncSession, pk: int) -> QbBank | None:
        """获取公开可用题库"""
        stmt = self._active_stmt().where(
            QbBank.id == pk,
            QbBank.visibility == 'public',
            QbBank.status == 'active',
            QbBank.current_revision_id.is_not(None),
        )
        result = await db.execute(stmt)
        return result.scalars().first()

    async def get_public_list(
        self,
        db: AsyncSession,
        *,
        category_ids: list[int] | None = None,
        bank_kind: str | None = None,
        keyword: str | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """获取公开题库列表映射"""
        primary_link = QbBankCategory.__table__.alias('primary_bank_category')
        primary_category = Category.__table__.alias('primary_category')
        stmt = (
            select(
                QbBank.id,
                QbBank.code,
                QbBank.visibility,
                QbBank.status,
                QbBankRevision.id.label('revision_id'),
                QbBankRevision.revision_no,
                QbBankRevision.name,
                QbBankRevision.bank_kind,
                QbBankRevision.description,
                QbBankRevision.cover_url,
                QbBankRevision.duration_minutes,
                QbBankRevision.pass_score,
                QbBankRevision.question_count,
                QbBankRevision.total_score,
                primary_link.c.category_id.label('primary_category_id'),
                primary_category.c.name.label('primary_category_name'),
            )
            .join(
                QbBankRevision,
                and_(
                    QbBankRevision.bank_id == QbBank.id,
                    QbBankRevision.id == QbBank.current_revision_id,
                    QbBankRevision.deleted == 0,
                    QbBankRevision.status == 'published',
                ),
            )
            .outerjoin(
                primary_link,
                and_(
                    primary_link.c.bank_id == QbBank.id,
                    primary_link.c.is_primary.is_(True),
                    primary_link.c.deleted == 0,
                ),
            )
            .outerjoin(
                primary_category,
                and_(
                    primary_category.c.id == primary_link.c.category_id,
                    primary_category.c.deleted == 0,
                ),
            )
            .where(
                QbBank.deleted == 0,
                QbBank.visibility == 'public',
                QbBank.status == 'active',
            )
        )
        if category_ids:
            category_match = exists(
                select(QbBankCategory.id).where(
                    QbBankCategory.bank_id == QbBank.id,
                    QbBankCategory.category_id.in_(category_ids),
                    QbBankCategory.deleted == 0,
                )
            )
            stmt = stmt.where(category_match)
        if bank_kind is not None:
            stmt = stmt.where(QbBankRevision.bank_kind == bank_kind)
        if keyword:
            stmt = stmt.where(QbBankRevision.name.ilike(f'%{keyword}%'))

        stmt = stmt.order_by(QbBankRevision.published_time.desc(), QbBank.id.desc()).offset(offset).limit(limit)
        result = await db.execute(stmt)
        return [dict(row) for row in result.mappings().all()]

    async def create_bank(
        self,
        db: AsyncSession,
        *,
        code: str,
        owner_id: int | None,
        visibility: str,
        status: str,
        created_by: int,
    ) -> QbBank:
        """创建题库稳定身份"""
        bank = QbBank(
            code=code,
            owner_id=owner_id,
            visibility=visibility,
            status=status,
            created_by=created_by,
        )
        db.add(bank)
        await db.flush()
        return bank

    async def update(self, db: AsyncSession, pk: int, data: dict[str, Any]) -> int:
        """更新题库稳定身份"""
        return await self.update_model_by_column(db, data, id=pk, deleted=0)


class CRUDBankRevision(CRUDPlus[QbBankRevision]):
    """题库版本数据库操作类"""

    async def get(
        self,
        db: AsyncSession,
        pk: int,
        *,
        bank_id: int | None = None,
        for_update: bool = False,
    ) -> QbBankRevision | None:
        """获取题库版本"""
        stmt = select(QbBankRevision).where(QbBankRevision.id == pk, QbBankRevision.deleted == 0)
        if bank_id is not None:
            stmt = stmt.where(QbBankRevision.bank_id == bank_id)
        if for_update:
            stmt = stmt.with_for_update()
        result = await db.execute(stmt)
        return result.scalars().first()

    async def get_all(self, db: AsyncSession, bank_id: int) -> Sequence[QbBankRevision]:
        """获取题库全部版本"""
        stmt = (
            select(QbBankRevision)
            .where(QbBankRevision.bank_id == bank_id, QbBankRevision.deleted == 0)
            .order_by(QbBankRevision.revision_no.desc())
        )
        result = await db.execute(stmt)
        return result.scalars().all()

    async def get_next_revision_no(self, db: AsyncSession, bank_id: int) -> int:
        """获取下一个题库版本号"""
        stmt = select(func.coalesce(func.max(QbBankRevision.revision_no), 0) + 1).where(
            QbBankRevision.bank_id == bank_id
        )
        result = await db.execute(stmt)
        return int(result.scalar_one())

    async def create(
        self,
        db: AsyncSession,
        *,
        bank_id: int,
        revision_no: int,
        obj: CreateBankRevisionParam,
        created_by: int,
    ) -> QbBankRevision:
        """创建题库草稿版本"""
        revision = QbBankRevision(
            bank_id=bank_id,
            revision_no=revision_no,
            created_by=created_by,
            **obj.model_dump(),
        )
        db.add(revision)
        await db.flush()
        return revision

    async def update(self, db: AsyncSession, pk: int, data: dict[str, Any]) -> int:
        """更新题库草稿版本"""
        return await self.update_model_by_column(db, data, id=pk, deleted=0, status='draft')

    async def recalculate_totals(self, db: AsyncSession, revision_id: int) -> tuple[int, Decimal]:
        """根据有效编排题目计算发布快照"""
        from backend.app.question_bank_v2.model.bank import QbBankItem

        stmt = select(func.count(QbBankItem.id), func.coalesce(func.sum(QbBankItem.score), 0)).where(
            QbBankItem.bank_revision_id == revision_id,
            QbBankItem.deleted == 0,
            QbBankItem.is_active.is_(True),
        )
        result = await db.execute(stmt)
        count, score = result.one()
        return int(count), Decimal(score)


class CRUDBankCategory(CRUDPlus[QbBankCategory]):
    """题库业务分类关联数据库操作类"""

    async def get_all(self, db: AsyncSession, bank_id: int) -> list[dict[str, Any]]:
        """获取题库业务分类关联"""
        stmt = (
            select(
                QbBankCategory.category_id,
                Category.name.label('category_name'),
                QbBankCategory.is_primary,
                QbBankCategory.sort_order,
            )
            .join(Category, and_(Category.id == QbBankCategory.category_id, Category.deleted == 0))
            .where(QbBankCategory.bank_id == bank_id, QbBankCategory.deleted == 0)
            .order_by(QbBankCategory.is_primary.desc(), QbBankCategory.sort_order, QbBankCategory.id)
        )
        result = await db.execute(stmt)
        return [dict(row) for row in result.mappings().all()]

    async def replace(
        self,
        db: AsyncSession,
        *,
        bank_id: int,
        category_ids: list[int],
        primary_category_id: int | None,
        user_id: int,
    ) -> None:
        """替换题库业务分类关联"""
        current_result = await db.execute(
            select(QbBankCategory).where(QbBankCategory.bank_id == bank_id, QbBankCategory.deleted == 0)
        )
        current = {item.category_id: item for item in current_result.scalars().all()}
        requested = set(category_ids)

        # PostgreSQL 主分类使用部分唯一索引，先清空旧主分类以避免交换时的瞬时冲突。
        if any(item.is_primary for item in current.values()):
            for item in current.values():
                item.is_primary = False
                item.updated_by = user_id
            await db.flush()

        for category_id, item in current.items():
            if category_id not in requested:
                await self.delete_model(db, item.id)

        for sort_order, category_id in enumerate(category_ids):
            item = current.get(category_id)
            if item is None:
                db.add(
                    QbBankCategory(
                        bank_id=bank_id,
                        category_id=category_id,
                        is_primary=category_id == primary_category_id,
                        sort_order=sort_order,
                        created_by=user_id,
                    )
                )
            else:
                item.is_primary = category_id == primary_category_id
                item.sort_order = sort_order
                item.updated_by = user_id
        await db.flush()


bank_dao: CRUDBank = CRUDBank(QbBank)
bank_revision_dao: CRUDBankRevision = CRUDBankRevision(QbBankRevision)
bank_category_dao: CRUDBankCategory = CRUDBankCategory(QbBankCategory)
