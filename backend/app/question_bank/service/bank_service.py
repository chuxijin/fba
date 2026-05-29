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
    BankProgressSummary,
    CreateBankParam,
    DeleteBankParam,
    GetBankChapterProgress,
    GetBankDetailWithChapters,
    UpdateBankParam,
)
from backend.app.question_bank.service.bank_mount_service import COLLECTION_BANK_TYPE, bank_mount_service
from backend.app.question_bank.service.bank_progress_service import bank_progress_service
from backend.app.question_bank.service.study_domain_service import study_domain_service
from backend.common.exception import errors
from backend.utils.build_tree import get_tree_data
from backend.utils.timezone import timezone


class BankService:
    """题库服务类"""

    @staticmethod
    def _resolve_chapter_source_bank_id(bank: QuestionBank) -> int:
        """解析题库实际使用的章节来源题库 ID"""
        return bank.chapter_source_bank_id or bank.id

    @staticmethod
    async def _validate_parent_bank(
        *,
        db: AsyncSession,
        parent_id: int | None,
        current_bank_id: int | None = None,
    ) -> None:
        """
        校验父题库关系是否合法

        :param db: 数据库会话
        :param parent_id: 父题库 ID
        :param current_bank_id: 当前题库 ID
        :return:
        """
        if parent_id is None:
            return

        parent_bank = await bank_dao.get(db, parent_id)
        if not parent_bank:
            raise errors.NotFoundError(msg='父合集不存在')
        if current_bank_id is not None and parent_bank.id == current_bank_id:
            raise errors.ForbiddenError(msg='禁止关联自身为父合集')

        visited_ids: set[int] = set()
        current_parent = parent_bank
        while current_parent.parent_id is not None:
            if current_parent.id in visited_ids:
                raise errors.ForbiddenError(msg='合集父子关系存在循环')
            visited_ids.add(current_parent.id)

            next_parent = await bank_dao.get(db, current_parent.parent_id)
            if not next_parent:
                break
            if current_bank_id is not None and next_parent.id == current_bank_id:
                raise errors.ForbiddenError(msg='禁止将内容挂到自己的子孙合集下')
            current_parent = next_parent

    @staticmethod
    async def _validate_chapter_source_bank(
        *,
        db: AsyncSession,
        source_bank_id: int,
    ) -> None:
        """
        校验章节来源题库是否合法

        :param db: 数据库会话
        :param source_bank_id: 章节来源题库 ID
        :return:
        """
        source_bank = await bank_dao.get(db, source_bank_id)
        if not source_bank:
            raise errors.NotFoundError(msg='章节来源内容不存在')

        actual_source_bank_id = source_bank.chapter_source_bank_id or source_bank.id
        if actual_source_bank_id != source_bank.id:
            raise errors.ForbiddenError(msg='章节来源内容必须维护自己的章节，不能继续复用其他内容')

    @staticmethod
    def _prune_empty_branches(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        递归剪掉自己和后代都没有题目的题库节点, 并写入 effective_q_count

        :param nodes: 树节点列表
        :return:
        """
        kept: list[dict[str, Any]] = []
        for node in nodes:
            children = node.get('children') or []
            if children:
                node['children'] = BankService._prune_empty_branches(children)
                effective = sum((c.get('effective_q_count') or 0) for c in node['children'])
            else:
                effective = node.get('q_count_cache') or 0
            node['effective_q_count'] = effective
            if effective > 0:
                kept.append(node)
        return kept

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
            raise errors.NotFoundError(msg='刷题内容不存在')

        if bank.bank_type == COLLECTION_BANK_TYPE:
            return await bank_progress_service.build_collection_detail(db=db, bank=bank)

        source_bank_id = BankService._resolve_chapter_source_bank_id(bank)
        chapter_list = await chapter_dao.get_by_bank(db, source_bank_id)
        chapters = get_tree_data(chapter_list, sort_key='sort_order')

        if chapters:
            chapter_ids = [chapter.id for chapter in chapter_list]
            count_map = await bank_progress_service.get_chapter_count_map(
                db,
                bank_id=pk,
                chapter_ids=chapter_ids,
            )
            question_type_count_map = await bank_progress_service.get_chapter_question_type_count_map(
                db,
                bank_id=pk,
                chapter_ids=chapter_ids,
            )
            bank_progress_service.patch_tree_count(chapters, count_map, question_type_count_map)

        result = GetBankDetailWithChapters.model_validate(bank)
        result.question_type_counts = await bank_progress_service.get_bank_question_type_counts(db=db, bank_id=pk)
        result.chapters = chapters
        return result

    @staticmethod
    async def get_chapter_progress(*, db: AsyncSession, bank_id: int, user_id: int) -> GetBankChapterProgress:
        """
        获取用户在指定题库下的章节做题进度

        :param db: 数据库会话
        :param bank_id: 题库 ID
        :param user_id: 用户 ID
        :return:
        """
        return await bank_progress_service.get_chapter_progress(db=db, bank_id=bank_id, user_id=user_id)

    @staticmethod
    async def get_progress_summaries(
        *,
        db: AsyncSession,
        bank_ids: list[int] | None = None,
        cat_id: int | None = None,
        user_id: int,
    ) -> list[BankProgressSummary]:
        """
        批量获取题库进度摘要

        :param db: 数据库会话
        :param bank_ids: 题库 ID 列表
        :param cat_id: 分类 ID（自动展开子孙分类下的所有题库）
        :param user_id: 用户 ID
        :return:
        """
        return await bank_progress_service.get_progress_summaries(
            db=db,
            bank_ids=bank_ids,
            cat_id=cat_id,
            user_id=user_id,
        )

    @staticmethod
    async def get_list(
        *,
        db: AsyncSession,
        cat_id: int | None = None,
        status: int | None = None,
        keyword: str | None = None,
        bank_type: int | None = None,
        parent_id: int | None = None,
        study_domain: str | None = None,
        exclude_empty: bool = True,
    ) -> list[dict[str, Any]]:
        """
        获取题库树形列表

        :param db: 数据库会话
        :param cat_id: 分类 ID
        :param status: 题库状态
        :param keyword: 关键字搜索
        :param bank_type: 内容类型
        :param parent_id: 父级 ID
        :param study_domain: 学习领域编码
        :return:
        """
        cat_ids = None
        if cat_id is not None:
            cat_ids = await category_dao.get_all_children_ids(db, cat_id)
        if study_domain is not None:
            domain_cat_ids = await study_domain_service.get_product_catalog_category_ids(
                db=db,
                code=study_domain,
            )
            if not domain_cat_ids:
                return []

            if cat_ids is None:
                cat_ids = list(domain_cat_ids)
            else:
                cat_ids = list(set(cat_ids) & domain_cat_ids)
                if not cat_ids:
                    return []

        can_use_mount_tree = keyword is None and bank_type is None
        bank_select = await bank_dao.get_all_mappings(
            db,
            cat_ids=cat_ids,
            status=status,
            keyword=keyword,
            bank_type=bank_type,
            parent_id=None if can_use_mount_tree else parent_id,
        )
        tree_data = None
        if can_use_mount_tree:
            tree_data = await bank_mount_service.get_mount_tree(
                db=db,
                bank_select=bank_select,
                status=status,
                parent_id=parent_id,
            )

        if tree_data is None:
            if can_use_mount_tree and parent_id is not None:
                bank_select = await bank_dao.get_all_mappings(
                    db,
                    cat_ids=cat_ids,
                    status=status,
                    keyword=keyword,
                    bank_type=bank_type,
                    parent_id=parent_id,
                )
            tree_data = get_tree_data(bank_select, sort_key='sort_order')

        if bank_type == 3 or (bank_type is None and parent_id is None and not keyword):
            collection_ids = [item['id'] for item in tree_data if item.get('bank_type') == 3]
            if collection_ids:
                child_counts = await bank_dao.count_children_by_parent_ids(db, collection_ids)
                for item in tree_data:
                    if item.get('bank_type') == 3 and item['id'] in child_counts:
                        item['q_count_cache'] = child_counts[item['id']]

        if exclude_empty:
            tree_data = BankService._prune_empty_branches(tree_data)

        return tree_data

    @staticmethod
    async def get_recommend_banks(*, db: AsyncSession) -> Sequence[QuestionBank]:
        """
        获取推荐题库

        :param db: 数据库会话
        :return:
        """
        seven_days_ago = timezone.now() - timedelta(days=7)

        subquery = (
            select(
                PracticeSession.bank_id,
                func.count(PracticeSession.id).label('practice_count'),
            )
            .where(PracticeSession.bank_id.isnot(None))
            .where(PracticeSession.start_time >= seven_days_ago)
            .group_by(PracticeSession.bank_id)
            .subquery()
        )

        stmt = (
            select(QuestionBank)
            .join(subquery, QuestionBank.id == subquery.c.bank_id)
            .where(QuestionBank.status == 1)
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
            raise errors.ConflictError(msg='内容编码已存在')

        category = await category_dao.get(db, obj.cat_id)
        if not category:
            raise errors.NotFoundError(msg='所属分类不存在')

        await BankService._validate_parent_bank(db=db, parent_id=obj.parent_id)

        if obj.chapter_source_bank_id is not None:
            await BankService._validate_chapter_source_bank(db=db, source_bank_id=obj.chapter_source_bank_id)

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
            raise errors.NotFoundError(msg='刷题内容不存在')

        if bank.code != obj.code and await bank_dao.get_by_code(db, obj.code):
            raise errors.ConflictError(msg='内容编码已存在')

        category = await category_dao.get(db, obj.cat_id)
        if not category:
            raise errors.NotFoundError(msg='所属分类不存在')

        await BankService._validate_parent_bank(db=db, parent_id=obj.parent_id, current_bank_id=pk)

        target_source_bank_id = obj.chapter_source_bank_id or pk
        await BankService._validate_chapter_source_bank(db=db, source_bank_id=target_source_bank_id)

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
