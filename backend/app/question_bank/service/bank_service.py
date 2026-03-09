#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence
from datetime import timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.admin.crud.crud_category import category_dao
from backend.app.question_bank.crud.crud_bank import bank_dao
from backend.app.question_bank.crud.crud_chapter import chapter_dao
from backend.app.question_bank.model.bank import QuestionBank
from backend.app.question_bank.model.practice import PracticeSession
from backend.app.question_bank.schema.bank import (
    CreateBankParam,
    DeleteBankParam,
    GetBankDetailWithChapters,
    UpdateBankParam,
)
from backend.common.exception import errors
from backend.utils.build_tree import get_tree_data
from backend.utils.timezone import timezone


class BankService:
    """题库服务类"""

    @staticmethod
    async def get(*, db: AsyncSession, pk: int) -> GetBankDetailWithChapters:
        """
        获取题库详情（含章节树）

        :param db: 数据库会话
        :param pk: 题库 ID
        :return:
        """
        bank = await bank_dao.get(db, pk)
        if not bank:
            raise errors.NotFoundError(msg='题库不存在')

        # 获取章节树
        chapter_list = await chapter_dao.get_by_bank(db, pk)
        chapters = get_tree_data(chapter_list, sort_key='sort_order')

        # 构建返回数据
        result = GetBankDetailWithChapters.model_validate(bank)
        result.chapters = chapters
        return result

    @staticmethod
    async def get_list(
        *,
        db: AsyncSession,
        cat_id: int | None = None,
        status: int | None = None,
        scope: int | None = None,
        keyword: str | None = None,
        bank_type: int | None = None,
        parent_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        获取题库树形列表

        :param db: 数据库会话
        :param cat_id: 分类 ID
        :param status: 题库状态
        :param scope: 可见范围
        :param keyword: 关键字搜索
        :param bank_type: 内容类型 (1=题库, 2=试卷, 3=合集)
        :param parent_id: 父级 ID
        :return:
        """
        # 如果指定了分类 ID，递归获取所有子分类 ID
        cat_ids = None
        if cat_id is not None:
            cat_ids = await category_dao.get_all_children_ids(db, cat_id)

        bank_select = await bank_dao.get_all(
            db,
            cat_ids=cat_ids,
            status=status,
            scope=scope,
            keyword=keyword,
            bank_type=bank_type,
            parent_id=parent_id,
        )
        tree_data = get_tree_data(bank_select, sort_key='id')

        # 对于合集类型，动态计算子题库数量
        if bank_type == 3 or (bank_type is None and parent_id is None and not keyword):
            # 获取所有合集的 ID
            collection_ids = [item['id'] for item in tree_data if item.get('bank_type') == 3]
            if collection_ids:
                # 统计每个合集包含的子题库数量
                child_counts = await bank_dao.count_children_by_parent_ids(db, collection_ids)
                # 更新 q_count_cache 字段
                for item in tree_data:
                    if item.get('bank_type') == 3 and item['id'] in child_counts:
                        item['q_count_cache'] = child_counts[item['id']]
        
        return tree_data

    @staticmethod
    async def get_recommend_banks(*, db: AsyncSession) -> Sequence[QuestionBank]:
        """
        获取推荐题库（全局热门）

        :param db: 数据库会话
        :return:
        """
        # 计算7天前的时间
        seven_days_ago = timezone.now() - timedelta(days=7)

        # 子查询：统计最近7天每个题库的练习次数
        subquery = (
            select(
                PracticeSession.bank_id,
                func.count(PracticeSession.id).label('practice_count')
            )
            .where(PracticeSession.bank_id.isnot(None))
            .where(PracticeSession.start_time >= seven_days_ago)
            .group_by(PracticeSession.bank_id)
            .subquery()
        )

        # 主查询：JOIN 题库表，获取题库详情，按练习次数排序，取前10个
        stmt = (
            select(QuestionBank)
            .join(subquery, QuestionBank.id == subquery.c.bank_id)
            .where(QuestionBank.status == 1)  # 只返回启用的题库
            .order_by(subquery.c.practice_count.desc())
            .limit(10)
        )

        result = await db.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def create(*, db: AsyncSession, obj: CreateBankParam, created_by: int) -> None:
        """
        创建题库

        :param db: 数据库会话
        :param obj: 创建题库参数
        :param created_by: 创建者 ID
        :return:
        """
        bank = await bank_dao.get_by_code(db, obj.code)
        if bank:
            raise errors.ConflictError(msg='题库编码已存在')
        category = await category_dao.get(db, obj.cat_id)
        if not category:
            raise errors.NotFoundError(msg='所属分类不存在')
        await bank_dao.create(db, obj, created_by=created_by)

    @staticmethod
    async def update(*, db: AsyncSession, pk: int, obj: UpdateBankParam, updated_by: int) -> int:
        """
        更新题库

        :param db: 数据库会话
        :param pk: 题库 ID
        :param obj: 更新题库参数
        :param updated_by: 修改者 ID
        :return:
        """
        bank = await bank_dao.get(db, pk)
        if not bank:
            raise errors.NotFoundError(msg='题库不存在')
        if bank.code != obj.code and await bank_dao.get_by_code(db, obj.code):
            raise errors.ConflictError(msg='题库编码已存在')
        category = await category_dao.get(db, obj.cat_id)
        if not category:
            raise errors.NotFoundError(msg='所属分类不存在')
        count = await bank_dao.update(db, pk, obj, updated_by=updated_by)
        return count

    @staticmethod
    async def delete(*, db: AsyncSession, obj: DeleteBankParam) -> int:
        """
        删除题库

        :param db: 数据库会话
        :param obj: 删除题库参数
        :return:
        """
        count = await bank_dao.delete(db, obj.ids)
        return count


bank_service: BankService = BankService()
