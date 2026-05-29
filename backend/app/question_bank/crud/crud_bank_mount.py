#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence

from sqlalchemy import and_, delete, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.question_bank.model import QuestionBank, QuestionBankMount
from backend.app.question_bank.schema.bank_mount import CreateBankMountParam, UpdateBankMountParam


class CRUDBankMount(CRUDPlus[QuestionBankMount]):
    """刷题内容挂载数据库操作类"""

    async def get(self, db: AsyncSession, mount_id: int) -> QuestionBankMount | None:
        """
        获取挂载详情

        :param db: 数据库会话
        :param mount_id: 挂载 ID
        :return:
        """
        return await self.select_model_by_column(db, id=mount_id)

    async def get_by_collection_item(
        self,
        db: AsyncSession,
        *,
        collection_id: int,
        item_id: int,
    ) -> QuestionBankMount | None:
        """
        按合集和内容获取挂载

        :param db: 数据库会话
        :param collection_id: 合集 ID
        :param item_id: 内容 ID
        :return:
        """
        return await self.select_model_by_column(db, collection_id=collection_id, item_id=item_id)

    async def get_all(
        self,
        db: AsyncSession,
        *,
        collection_id: int | None = None,
        item_id: int | None = None,
        status: int | None = None,
    ) -> Sequence[QuestionBankMount]:
        """
        获取挂载列表

        :param db: 数据库会话
        :param collection_id: 合集 ID
        :param item_id: 内容 ID
        :param status: 状态
        :return:
        """
        filters: dict = {}
        if collection_id is not None:
            filters['collection_id'] = collection_id
        if item_id is not None:
            filters['item_id'] = item_id
        if status is not None:
            filters['status'] = status

        return await self.select_models_order(db, 'sort_order', 'asc', **filters)

    async def get_all_mappings(
        self,
        db: AsyncSession,
        *,
        collection_ids: list[int] | None = None,
        item_ids: list[int] | None = None,
        status: int | None = None,
    ) -> list[dict]:
        """
        获取挂载映射列表

        :param db: 数据库会话
        :param collection_ids: 合集 ID 列表
        :param item_ids: 内容 ID 列表
        :param status: 状态
        :return:
        """
        filters = []
        if collection_ids is not None:
            filters.append(self.model.collection_id.in_(collection_ids))
        if item_ids is not None:
            filters.append(self.model.item_id.in_(item_ids))
        if status is not None:
            filters.append(self.model.status == status)

        stmt = select(self.model.__table__)
        if filters:
            stmt = stmt.where(and_(*filters))

        stmt = stmt.order_by(self.model.collection_id.asc(), self.model.sort_order.asc(), self.model.id.asc())
        result = await db.execute(stmt)
        return [dict(row) for row in result.mappings().all()]

    async def get_relation_mappings(
        self,
        db: AsyncSession,
        *,
        bank_ids: list[int],
        status: int = 1,
    ) -> list[dict]:
        """
        获取指定内容范围内的挂载关系

        :param db: 数据库会话
        :param bank_ids: 内容 ID 列表
        :param status: 状态
        :return:
        """
        if not bank_ids:
            return []

        stmt = (
            select(self.model.__table__)
            .where(
                self.model.status == status,
                or_(
                    self.model.collection_id.in_(bank_ids),
                    self.model.item_id.in_(bank_ids),
                ),
            )
            .order_by(self.model.collection_id.asc(), self.model.sort_order.asc(), self.model.id.asc())
        )
        result = await db.execute(stmt)
        return [dict(row) for row in result.mappings().all()]

    async def get_detail_mappings(
        self,
        db: AsyncSession,
        *,
        collection_id: int | None = None,
        item_id: int | None = None,
        status: int | None = None,
    ) -> list[dict]:
        """
        获取挂载详情映射

        :param db: 数据库会话
        :param collection_id: 合集 ID
        :param item_id: 内容 ID
        :param status: 状态
        :return:
        """
        collection_alias = QuestionBank.__table__.alias('collection_bank')
        item_alias = QuestionBank.__table__.alias('item_bank')
        filters = []
        if collection_id is not None:
            filters.append(self.model.collection_id == collection_id)
        if item_id is not None:
            filters.append(self.model.item_id == item_id)
        if status is not None:
            filters.append(self.model.status == status)

        stmt = (
            select(
                self.model.id,
                self.model.collection_id,
                self.model.item_id,
                self.model.sort_order,
                self.model.status,
                self.model.created_by,
                self.model.updated_by,
                self.model.created_time,
                self.model.updated_time,
                collection_alias.c.name.label('collection_name'),
                item_alias.c.name.label('item_name'),
                item_alias.c.bank_type.label('item_bank_type'),
            )
            .join(collection_alias, collection_alias.c.id == self.model.collection_id)
            .join(item_alias, item_alias.c.id == self.model.item_id)
        )
        if filters:
            stmt = stmt.where(and_(*filters))

        stmt = stmt.order_by(self.model.collection_id.asc(), self.model.sort_order.asc(), self.model.id.asc())
        result = await db.execute(stmt)
        return [dict(row) for row in result.mappings().all()]

    async def create(self, db: AsyncSession, obj: CreateBankMountParam, *, created_by: int) -> None:
        """
        创建挂载

        :param db: 数据库会话
        :param obj: 创建挂载参数
        :param created_by: 创建者 ID
        :return:
        """
        dict_obj = obj.model_dump()
        dict_obj['created_by'] = created_by
        db.add(self.model(**dict_obj))
        await db.flush()

    async def update(self, db: AsyncSession, mount_id: int, obj: UpdateBankMountParam, *, updated_by: int) -> int:
        """
        更新挂载

        :param db: 数据库会话
        :param mount_id: 挂载 ID
        :param obj: 更新挂载参数
        :param updated_by: 修改者 ID
        :return:
        """
        values = obj.model_dump(exclude_unset=True)
        values['updated_by'] = updated_by
        stmt = update(self.model).where(self.model.id == mount_id).values(**values)
        result = await db.execute(stmt)
        await db.flush()
        return int(result.rowcount or 0)

    async def delete(self, db: AsyncSession, mount_ids: list[int]) -> int:
        """
        批量删除挂载

        :param db: 数据库会话
        :param mount_ids: 挂载 ID 列表
        :return:
        """
        stmt = delete(self.model).where(self.model.id.in_(mount_ids))
        result = await db.execute(stmt)
        await db.flush()
        return int(result.rowcount or 0)


bank_mount_dao: CRUDBankMount = CRUDBankMount(QuestionBankMount)
