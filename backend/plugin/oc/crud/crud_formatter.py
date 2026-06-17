"""Formatter CRUD"""

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from backend.plugin.oc.model.formatter import FormatterField, FormatterEmbedding, FormatterMapping


class CRUDFormatterField:
    """字段配置数据操作"""

    @staticmethod
    async def get_all(db: AsyncSession) -> list[FormatterField]:
        """获取所有字段配置"""
        stmt = select(FormatterField).order_by(FormatterField.category, FormatterField.field_order)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_by_category(db: AsyncSession, category: str) -> list[FormatterField]:
        """根据分类获取字段配置"""
        stmt = select(FormatterField).where(FormatterField.category == category).order_by(FormatterField.field_order)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_by_id(db: AsyncSession, field_id: int) -> FormatterField | None:
        """根据ID获取字段配置"""
        stmt = select(FormatterField).where(FormatterField.id == field_id)
        result = await db.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def get_by_category_and_field(
        db: AsyncSession, category: str, field_name: str, parent_field_id: int | None = None
    ) -> FormatterField | None:
        """根据分类和字段名获取"""
        stmt = select(FormatterField).where(
            FormatterField.category == category,
            FormatterField.field_name == field_name,
            FormatterField.parent_field_id == parent_field_id,
        )
        result = await db.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def create(db: AsyncSession, **kwargs) -> FormatterField:
        """创建字段配置"""
        field = FormatterField(**kwargs)
        db.add(field)
        await db.flush()
        return field

    @staticmethod
    async def bulk_create(db: AsyncSession, fields: list[dict]) -> list[FormatterField]:
        """批量创建字段配置"""
        objs = [FormatterField(**f) for f in fields]
        db.add_all(objs)
        await db.flush()
        return objs

    @staticmethod
    async def delete_all(db: AsyncSession) -> int:
        """删除所有字段配置"""
        stmt = delete(FormatterField)
        result = await db.execute(stmt)
        return result.rowcount


class CRUDFormatterEmbedding:
    """标签匹配规则数据操作"""

    @staticmethod
    async def get_by_field_id(db: AsyncSession, field_id: int) -> list[FormatterEmbedding]:
        """根据字段ID获取标签匹配规则"""
        stmt = select(FormatterEmbedding).where(FormatterEmbedding.field_id == field_id)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_all(db: AsyncSession) -> list[FormatterEmbedding]:
        """获取所有标签匹配规则"""
        stmt = select(FormatterEmbedding)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def create(db: AsyncSession, **kwargs) -> FormatterEmbedding:
        """创建标签匹配规则"""
        embedding = FormatterEmbedding(**kwargs)
        db.add(embedding)
        await db.flush()
        return embedding

    @staticmethod
    async def bulk_create(db: AsyncSession, embeddings: list[dict]) -> list[FormatterEmbedding]:
        """批量创建标签匹配规则"""
        objs = [FormatterEmbedding(**e) for e in embeddings]
        db.add_all(objs)
        await db.flush()
        return objs

    @staticmethod
    async def delete_all(db: AsyncSession) -> int:
        """删除所有标签匹配规则"""
        stmt = delete(FormatterEmbedding)
        result = await db.execute(stmt)
        return result.rowcount


class CRUDFormatterMapping:
    """下拉选项映射数据操作"""

    @staticmethod
    async def get_by_field_id(db: AsyncSession, field_id: int) -> list[FormatterMapping]:
        """根据字段ID获取映射"""
        stmt = select(FormatterMapping).where(FormatterMapping.field_id == field_id)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_all(db: AsyncSession) -> list[FormatterMapping]:
        """获取所有映射"""
        stmt = select(FormatterMapping)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def create(db: AsyncSession, **kwargs) -> FormatterMapping:
        """创建映射"""
        mapping = FormatterMapping(**kwargs)
        db.add(mapping)
        await db.flush()
        return mapping

    @staticmethod
    async def bulk_create(db: AsyncSession, mappings: list[dict]) -> list[FormatterMapping]:
        """批量创建映射"""
        objs = [FormatterMapping(**m) for m in mappings]
        db.add_all(objs)
        await db.flush()
        return objs

    @staticmethod
    async def delete_all(db: AsyncSession) -> int:
        """删除所有映射"""
        stmt = delete(FormatterMapping)
        result = await db.execute(stmt)
        return result.rowcount


formatter_field_dao: CRUDFormatterField = CRUDFormatterField()
formatter_embedding_dao: CRUDFormatterEmbedding = CRUDFormatterEmbedding()
formatter_mapping_dao: CRUDFormatterMapping = CRUDFormatterMapping()
