#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.question_bank.model import QuestionBank
from backend.app.question_bank.schema.bank import CreateBankParam, UpdateBankParam


class CRUDBank(CRUDPlus[QuestionBank]):
    """题库数据库操作类"""

    async def get(self, db: AsyncSession, bank_id: int) -> QuestionBank | None:
        """
        获取题库详情

        :param db: 数据库会话
        :param bank_id: 题库 ID
        :return:
        """
        return await self.select_model_by_column(db, id=bank_id)

    async def get_by_code(self, db: AsyncSession, code: str) -> QuestionBank | None:
        """
        通过编码获取题库

        :param db: 数据库会话
        :param code: 题库编码
        :return:
        """
        return await self.select_model_by_column(db, code=code)

    async def get_all(
        self,
        db: AsyncSession,
        cat_id: int | None = None,
        cat_ids: list[int] | None = None,
        status: int | None = None,
        keyword: str | None = None,
        bank_type: int | None = None,
        parent_id: int | None = None,
    ) -> Sequence[QuestionBank]:
        """
        获取所有题库

        :param db: 数据库会话
        :param cat_id: 分类 ID（精确匹配）
        :param cat_ids: 分类 ID 列表（包含子分类，优先级高于 cat_id）
        :param status: 题库状态
        :param keyword: 关键字搜索
        :param bank_type: 内容类型
        :param parent_id: 父级 ID
        :return:
        """
        filters: dict = {}

        if cat_ids is not None:
            filters['cat_id__in'] = cat_ids
        elif cat_id is not None:
            filters['cat_id'] = cat_id
        if status is not None:
            filters['status'] = status
        if keyword is not None:
            filters['name__like'] = f'%{keyword}%'
        if bank_type is not None:
            filters['bank_type'] = bank_type
        if parent_id is not None:
            filters['parent_id'] = parent_id

        return await self.select_models_order(db, 'created_time', 'desc', **filters)

    async def get_all_mappings(
        self,
        db: AsyncSession,
        cat_id: int | None = None,
        cat_ids: list[int] | None = None,
        status: int | None = None,
        keyword: str | None = None,
        bank_type: int | None = None,
        parent_id: int | None = None,
    ) -> list[dict]:
        """
        获取所有题库映射，跳过 ORM 实例化提升性能

        :param db: 数据库会话
        :param cat_id: 分类 ID（精确匹配）
        :param cat_ids: 分类 ID 列表（包含子分类，优先级高于 cat_id）
        :param status: 题库状态
        :param keyword: 关键字搜索
        :param bank_type: 内容类型
        :param parent_id: 父级 ID
        :return:
        """
        from sqlalchemy import and_

        filters = []
        if cat_ids is not None:
            filters.append(self.model.cat_id.in_(cat_ids))
        elif cat_id is not None:
            filters.append(self.model.cat_id == cat_id)
        if status is not None:
            filters.append(self.model.status == status)
        if keyword is not None:
            filters.append(self.model.name.like(f'%{keyword}%'))
        if bank_type is not None:
            filters.append(self.model.bank_type == bank_type)
        if parent_id is not None:
            filters.append(self.model.parent_id == parent_id)

        stmt = select(self.model.__table__)
        if filters:
            stmt = stmt.where(and_(*filters))
            
        stmt = stmt.order_by(self.model.created_time.desc())

        result = await db.execute(stmt)
        return [dict(row) for row in result.mappings().all()]

    async def create(self, db: AsyncSession, obj: CreateBankParam, *, created_by: int) -> None:
        """
        创建题库

        :param db: 数据库会话
        :param obj: 创建题库参数
        :param created_by: 创建者 ID
        :return:
        """
        dict_obj = obj.model_dump()
        dict_obj['created_by'] = created_by
        new_bank = self.model(**dict_obj)
        db.add(new_bank)
        await db.flush()

        if new_bank.chapter_source_bank_id is None:
            new_bank.chapter_source_bank_id = new_bank.id
            await db.flush()

    async def update(self, db: AsyncSession, bank_id: int, obj: UpdateBankParam, *, updated_by: int) -> int:
        """
        更新题库

        :param db: 数据库会话
        :param bank_id: 题库 ID
        :param obj: 更新题库参数
        :param updated_by: 修改者 ID
        :return:
        """
        dict_obj = obj.model_dump()
        if dict_obj.get('chapter_source_bank_id') is None:
            dict_obj['chapter_source_bank_id'] = bank_id
        dict_obj['updated_by'] = updated_by
        return await self.update_model(db, bank_id, dict_obj)

    async def delete(self, db: AsyncSession, bank_ids: list[int]) -> int:
        """
        批量删除题库

        :param db: 数据库会话
        :param bank_ids: 题库 ID 列表
        :return:
        """
        return await self.delete_model_by_column(db, allow_multiple=True, id__in=bank_ids)

    async def count_children_by_parent_ids(self, db: AsyncSession, parent_ids: list[int]) -> dict[int, int]:
        """
        统计每个父级题库的子题库数量

        :param db: 数据库会话
        :param parent_ids: 父级题库 ID 列表
        :return:
        """
        stmt = (
            select(
                QuestionBank.parent_id,
                func.count(QuestionBank.id).label('child_count'),
            )
            .where(QuestionBank.parent_id.in_(parent_ids))
            .where(QuestionBank.status == 1)
            .group_by(QuestionBank.parent_id)
        )

        result = await db.execute(stmt)
        rows = result.all()
        return {row.parent_id: row.child_count for row in rows}


bank_dao: CRUDBank = CRUDBank(QuestionBank)
