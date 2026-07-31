from collections.abc import Sequence
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.question_bank_v2.model.bank import QbBankItem, QbBankSection
from backend.app.question_bank_v2.model.question import QbQuestion


class CRUDBankSection(CRUDPlus[QbBankSection]):
    """题库版本章节数据库操作类"""

    async def get(self, db: AsyncSession, pk: int, *, revision_id: int | None = None) -> QbBankSection | None:
        """获取题库版本章节"""
        stmt = select(QbBankSection).where(QbBankSection.id == pk, QbBankSection.deleted == 0)
        if revision_id is not None:
            stmt = stmt.where(QbBankSection.bank_revision_id == revision_id)
        result = await db.execute(stmt)
        return result.scalars().first()

    async def get_all(self, db: AsyncSession, revision_id: int) -> Sequence[QbBankSection]:
        """获取题库版本全部章节"""
        stmt = (
            select(QbBankSection)
            .where(QbBankSection.bank_revision_id == revision_id, QbBankSection.deleted == 0)
            .order_by(QbBankSection.depth, QbBankSection.sort_order, QbBankSection.id)
        )
        result = await db.execute(stmt)
        return result.scalars().all()

    async def get_by_code(self, db: AsyncSession, revision_id: int, code: str) -> QbBankSection | None:
        """通过版本内编码获取章节"""
        stmt = select(QbBankSection).where(
            QbBankSection.bank_revision_id == revision_id,
            QbBankSection.code == code,
            QbBankSection.deleted == 0,
        )
        result = await db.execute(stmt)
        return result.scalars().first()

    async def create(self, db: AsyncSession, data: dict[str, Any]) -> QbBankSection:
        """创建题库版本章节"""
        section = QbBankSection(**data)
        db.add(section)
        await db.flush()
        return section

    async def update(self, db: AsyncSession, pk: int, data: dict[str, Any]) -> int:
        """更新题库版本章节"""
        return await self.update_model_by_column(db, data, id=pk, deleted=0)


class CRUDBankItem(CRUDPlus[QbBankItem]):
    """题库版本题目编排数据库操作类"""

    async def get(self, db: AsyncSession, pk: int, *, revision_id: int | None = None) -> QbBankItem | None:
        """获取题库版本题目编排"""
        stmt = select(QbBankItem).where(QbBankItem.id == pk, QbBankItem.deleted == 0)
        if revision_id is not None:
            stmt = stmt.where(QbBankItem.bank_revision_id == revision_id)
        result = await db.execute(stmt)
        return result.scalars().first()

    async def get_all(self, db: AsyncSession, revision_id: int) -> list[dict[str, Any]]:
        """获取题库版本全部题目编排"""
        stmt = (
            select(
                QbBankItem.id,
                QbBankItem.bank_revision_id,
                QbBankItem.item_key,
                QbBankItem.question_id,
                QbBankItem.section_id,
                QbBankItem.exam_year,
                QbBankItem.score,
                QbBankItem.sort_order,
                QbBankItem.is_required,
                QbBankItem.is_active,
                QbBankItem.settings,
                QbQuestion.question_type,
                QbQuestion.stem,
                QbBankItem.created_time,
            )
            .join(
                QbQuestion,
                and_(
                    QbQuestion.id == QbBankItem.question_id,
                    QbQuestion.deleted == 0,
                ),
            )
            .where(QbBankItem.bank_revision_id == revision_id, QbBankItem.deleted == 0)
            .order_by(QbBankItem.section_id.nulls_first(), QbBankItem.sort_order, QbBankItem.id)
        )
        result = await db.execute(stmt)
        return [dict(row) for row in result.mappings().all()]

    def get_list_select(self, *, revision_id: int, section_id: int | None = None) -> Any:
        """构建题库版本题项游标分页查询"""
        stmt = (
            select(
                QbBankItem.id,
                QbBankItem.bank_revision_id,
                QbBankItem.item_key,
                QbBankItem.question_id,
                QbBankItem.section_id,
                QbBankItem.exam_year,
                QbBankItem.score,
                QbBankItem.sort_order,
                QbBankItem.is_required,
                QbBankItem.is_active,
                QbBankItem.settings,
                QbQuestion.question_type,
                QbQuestion.stem,
                QbBankItem.created_time,
            )
            .join(QbQuestion, and_(QbQuestion.id == QbBankItem.question_id, QbQuestion.deleted == 0))
            .where(QbBankItem.bank_revision_id == revision_id, QbBankItem.deleted == 0)
        )
        if section_id is not None:
            stmt = stmt.where(QbBankItem.section_id == section_id)
        return stmt.order_by(
            QbBankItem.section_id.asc().nullsfirst(),
            QbBankItem.sort_order,
            QbBankItem.id,
        )

    async def get_by_item_key(self, db: AsyncSession, revision_id: int, item_key: str) -> QbBankItem | None:
        """通过版本内业务键获取题目编排"""
        stmt = select(QbBankItem).where(
            QbBankItem.bank_revision_id == revision_id,
            QbBankItem.item_key == item_key,
            QbBankItem.deleted == 0,
        )
        result = await db.execute(stmt)
        return result.scalars().first()

    async def get_by_question(self, db: AsyncSession, revision_id: int, question_id: int) -> QbBankItem | None:
        """获取题目在指定题库版本中的编排"""
        stmt = select(QbBankItem).where(
            QbBankItem.bank_revision_id == revision_id,
            QbBankItem.question_id == question_id,
            QbBankItem.deleted == 0,
        )
        result = await db.execute(stmt)
        return result.scalars().first()

    async def create(self, db: AsyncSession, data: dict[str, Any]) -> QbBankItem:
        """创建题库版本题目编排"""
        item = QbBankItem(**data)
        db.add(item)
        await db.flush()
        return item

    async def update(self, db: AsyncSession, pk: int, data: dict[str, Any]) -> int:
        """更新题库版本题目编排"""
        return await self.update_model_by_column(db, data, id=pk, deleted=0)

    async def delete(self, db: AsyncSession, pk: int) -> int:
        """删除题库版本题目编排"""
        return await self.delete_model(db, pk)


bank_section_dao: CRUDBankSection = CRUDBankSection(QbBankSection)
bank_item_dao: CRUDBankItem = CRUDBankItem(QbBankItem)
