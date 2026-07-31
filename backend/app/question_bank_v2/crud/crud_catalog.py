from collections.abc import Sequence
from typing import Any

from sqlalchemy import Select, and_, case, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.admin.model.category import Category
from backend.app.question_bank_v2.model.bank import QbBank, QbBankRevision
from backend.app.question_bank_v2.model.catalog import QbBankCategory, QbCollection, QbCollectionBank


class CRUDCollection(CRUDPlus[QbCollection]):
    """题库合集数据库操作类"""

    async def get_subtree_ids(self, db: AsyncSession, root_id: int) -> list[int]:
        """获取合集及其全部后代合集 ID（公开且启用）"""
        rows = await db.execute(
            select(QbCollection.id, QbCollection.parent_id).where(
                QbCollection.deleted == 0,
                QbCollection.visibility == 'public',
                QbCollection.status == 'active',
            )
        )
        children: dict[int | None, list[int]] = {}
        for cid, parent_id in rows.all():
            children.setdefault(parent_id, []).append(cid)

        result: list[int] = []
        stack = [root_id]
        seen: set[int] = set()
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            result.append(current)
            stack.extend(children.get(current, []))
        return result

    async def get(self, db: AsyncSession, pk: int, *, for_update: bool = False) -> QbCollection | None:
        """获取题库合集"""
        stmt = select(QbCollection).where(QbCollection.id == pk, QbCollection.deleted == 0)
        if for_update:
            stmt = stmt.with_for_update()
        result = await db.execute(stmt)
        return result.scalars().first()

    async def get_by_code(self, db: AsyncSession, code: str) -> QbCollection | None:
        """通过业务编码获取题库合集"""
        stmt = select(QbCollection).where(QbCollection.code == code, QbCollection.deleted == 0)
        result = await db.execute(stmt)
        return result.scalars().first()

    async def get_all(self, db: AsyncSession) -> Sequence[QbCollection]:
        """获取全部题库合集"""
        stmt = self.get_select()
        result = await db.execute(stmt)
        return result.scalars().all()

    def get_select(self) -> Select:
        """获取全部题库合集 Select 查询句"""
        return (
            select(QbCollection)
            .where(QbCollection.deleted == 0)
            .order_by(QbCollection.parent_id.nulls_first(), QbCollection.sort_order, QbCollection.id)
        )

    async def create(self, db: AsyncSession, data: dict[str, Any]) -> QbCollection:
        """创建题库合集"""
        collection = QbCollection(**data)
        db.add(collection)
        await db.flush()
        return collection

    async def update(self, db: AsyncSession, pk: int, data: dict[str, Any]) -> int:
        """更新题库合集"""
        return await self.update_model_by_column(db, data, id=pk, deleted=0)

    async def get_public_catalog(self, db: AsyncSession) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """以固定两次查询获取公开合集及有效题库挂载"""
        collection_stmt = (
            select(
                QbCollection.id,
                QbCollection.code,
                QbCollection.name,
                QbCollection.parent_id,
                QbCollection.description,
                QbCollection.sort_order,
            )
            .where(
                QbCollection.deleted == 0,
                QbCollection.visibility == 'public',
                QbCollection.status == 'active',
            )
            .order_by(QbCollection.sort_order, QbCollection.id)
        )
        collection_result = await db.execute(collection_stmt)
        collections = [dict(row) for row in collection_result.mappings().all()]

        primary_link = QbBankCategory.__table__.alias('catalog_primary_bank_category')
        primary_category = Category.__table__.alias('catalog_primary_category')
        effective_revision_id = case(
            (QbCollectionBank.follow_latest.is_(True), QbBank.current_revision_id),
            else_=QbCollectionBank.bank_revision_id,
        )
        mount_stmt = (
            select(
                QbCollectionBank.collection_id,
                QbCollectionBank.sort_order.label('mount_sort_order'),
                QbCollectionBank.display_name,
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
                QbCollection,
                and_(
                    QbCollection.id == QbCollectionBank.collection_id,
                    QbCollection.deleted == 0,
                    QbCollection.visibility == 'public',
                    QbCollection.status == 'active',
                ),
            )
            .join(QbBank, and_(QbBank.id == QbCollectionBank.bank_id, QbBank.deleted == 0))
            .join(
                QbBankRevision,
                and_(
                    QbBankRevision.id == effective_revision_id,
                    QbBankRevision.bank_id == QbBank.id,
                    QbBankRevision.deleted == 0,
                    QbBankRevision.status.in_(('published', 'retired')),
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
                QbCollectionBank.deleted == 0,
                QbCollectionBank.is_active.is_(True),
                QbBank.visibility == 'public',
                QbBank.status == 'active',
            )
            .order_by(QbCollectionBank.collection_id, QbCollectionBank.sort_order, QbCollectionBank.id)
        )
        mount_result = await db.execute(mount_stmt)
        mounts = [dict(row) for row in mount_result.mappings().all()]
        return collections, mounts


class CRUDCollectionBank(CRUDPlus[QbCollectionBank]):
    """题库合集挂载数据库操作类"""

    async def get(self, db: AsyncSession, pk: int) -> QbCollectionBank | None:
        """获取题库合集挂载"""
        stmt = select(QbCollectionBank).where(QbCollectionBank.id == pk, QbCollectionBank.deleted == 0)
        result = await db.execute(stmt)
        return result.scalars().first()

    async def get_by_bank(
        self,
        db: AsyncSession,
        *,
        collection_id: int,
        bank_id: int,
    ) -> QbCollectionBank | None:
        """通过合集和题库获取有效挂载"""
        stmt = select(QbCollectionBank).where(
            QbCollectionBank.collection_id == collection_id,
            QbCollectionBank.bank_id == bank_id,
            QbCollectionBank.deleted == 0,
        )
        result = await db.execute(stmt)
        return result.scalars().first()

    async def get_all(self, db: AsyncSession, collection_id: int) -> Sequence[QbCollectionBank]:
        """获取合集全部题库挂载"""
        stmt = (
            select(QbCollectionBank)
            .where(QbCollectionBank.collection_id == collection_id, QbCollectionBank.deleted == 0)
            .order_by(QbCollectionBank.sort_order, QbCollectionBank.id)
        )
        result = await db.execute(stmt)
        return result.scalars().all()

    def get_select_by_collection(self, collection_id: int) -> Select:
        """构建合集关联的题库挂载查询表达式"""
        effective_revision_id = case(
            (QbCollectionBank.follow_latest.is_(True), QbBank.current_revision_id),
            else_=QbCollectionBank.bank_revision_id,
        )
        return (
            select(
                QbCollectionBank.id,
                QbCollectionBank.collection_id,
                QbCollectionBank.bank_id,
                QbBankRevision.name.label('bank_name'),
                QbCollectionBank.bank_revision_id,
                QbBankRevision.revision_no,
                QbCollectionBank.follow_latest,
                QbCollectionBank.display_name,
                QbCollectionBank.sort_order,
                QbCollectionBank.is_active,
                QbCollectionBank.created_time,
            )
            .join(QbBank, and_(QbBank.id == QbCollectionBank.bank_id, QbBank.deleted == 0))
            .outerjoin(
                QbBankRevision,
                and_(
                    QbBankRevision.id == effective_revision_id,
                    QbBankRevision.bank_id == QbBank.id,
                    QbBankRevision.deleted == 0,
                ),
            )
            .where(
                QbCollectionBank.collection_id == collection_id,
                QbCollectionBank.deleted == 0,
            )
            .order_by(QbCollectionBank.sort_order, QbCollectionBank.id)
        )

    async def create(self, db: AsyncSession, data: dict[str, Any]) -> QbCollectionBank:
        """创建题库合集挂载"""
        mount = QbCollectionBank(**data)
        db.add(mount)
        await db.flush()
        return mount

    async def update(self, db: AsyncSession, pk: int, data: dict[str, Any]) -> int:
        """更新题库合集挂载"""
        return await self.update_model_by_column(db, data, id=pk, deleted=0)

    async def delete(self, db: AsyncSession, pk: int) -> int:
        """删除题库合集挂载"""
        return await self.delete_model(db, pk)

    async def get_effective_bank_revisions(
        self,
        db: AsyncSession,
        collection_ids: Sequence[int],
    ) -> list[dict[str, Any]]:
        """获取合集作用域内每个题库实际生效的版本 ID"""
        if not collection_ids:
            return []
        effective_revision_id = case(
            (QbCollectionBank.follow_latest.is_(True), QbBank.current_revision_id),
            else_=QbCollectionBank.bank_revision_id,
        )
        stmt = (
            select(
                QbBank.id.label('bank_id'),
                QbBankRevision.id.label('bank_revision_id'),
                QbBankRevision.revision_no,
                QbCollectionBank.follow_latest,
            )
            .join(QbBank, and_(QbBank.id == QbCollectionBank.bank_id, QbBank.deleted == 0))
            .join(
                QbBankRevision,
                and_(
                    QbBankRevision.id == effective_revision_id,
                    QbBankRevision.bank_id == QbBank.id,
                    QbBankRevision.deleted == 0,
                    QbBankRevision.status.in_(('published', 'retired')),
                ),
            )
            .where(
                QbCollectionBank.collection_id.in_(collection_ids),
                QbCollectionBank.deleted == 0,
                QbCollectionBank.is_active.is_(True),
                QbBank.visibility == 'public',
                QbBank.status == 'active',
            )
        )
        return [dict(row) for row in (await db.execute(stmt)).mappings().all()]


collection_dao: CRUDCollection = CRUDCollection(QbCollection)
collection_bank_dao: CRUDCollectionBank = CRUDCollectionBank(QbCollectionBank)
