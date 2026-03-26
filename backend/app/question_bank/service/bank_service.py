#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence
from datetime import timedelta
from typing import Any

import sqlalchemy as sa
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.admin.crud.crud_category import category_dao
from backend.app.question_bank.crud.crud_bank import bank_dao
from backend.app.question_bank.crud.crud_chapter import chapter_dao
from backend.app.question_bank.model.bank import QuestionBank
from backend.app.question_bank.model.practice import PracticeRecord, PracticeSession
from backend.app.question_bank.model.question import QuestionPlacement
from backend.app.question_bank.schema.bank import (
    ChapterProgressNode,
    CreateBankParam,
    DeleteBankParam,
    GetBankChapterProgress,
    GetBankDetailWithChapters,
    UpdateBankParam,
)
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
            raise errors.NotFoundError(msg='父题库不存在')
        if current_bank_id is not None and parent_bank.id == current_bank_id:
            raise errors.ForbiddenError(msg='禁止关联自身为父级题库')

        visited_ids: set[int] = set()
        current_parent = parent_bank
        while current_parent.parent_id is not None:
            if current_parent.id in visited_ids:
                raise errors.ForbiddenError(msg='题库父子关系存在循环')
            visited_ids.add(current_parent.id)

            next_parent = await bank_dao.get(db, current_parent.parent_id)
            if not next_parent:
                break
            if current_bank_id is not None and next_parent.id == current_bank_id:
                raise errors.ForbiddenError(msg='禁止将题库挂到自己的子孙题库下')
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
            raise errors.NotFoundError(msg='章节来源题库不存在')

        actual_source_bank_id = source_bank.chapter_source_bank_id or source_bank.id
        if actual_source_bank_id != source_bank.id:
            raise errors.ForbiddenError(msg='章节来源题库必须维护自己的章节，不能继续复用其他题库')

    @staticmethod
    async def _get_chapter_count_map(
        db: AsyncSession,
        *,
        bank_id: int,
        chapter_ids: list[int],
    ) -> dict[int, int]:
        """按当前题库统计各章节题量"""
        if not chapter_ids:
            return {}

        stmt = (
            select(QuestionPlacement.chapter_id, func.count(QuestionPlacement.id))
            .where(
                QuestionPlacement.bank_id == bank_id,
                QuestionPlacement.is_active.is_(True),
                QuestionPlacement.chapter_id.in_(chapter_ids),
            )
            .group_by(QuestionPlacement.chapter_id)
        )
        rows = (await db.execute(stmt)).all()
        return {row[0]: row[1] for row in rows}

    @staticmethod
    def _patch_tree_count(nodes: list[dict[str, Any]], count_map: dict[int, int]) -> None:
        """递归回填章节树题量"""
        for node in nodes:
            node['q_count_cache'] = count_map.get(node['id'], 0)
            if node.get('children'):
                BankService._patch_tree_count(node['children'], count_map)

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

        source_bank_id = BankService._resolve_chapter_source_bank_id(bank)
        chapter_list = await chapter_dao.get_by_bank(db, source_bank_id)
        chapters = get_tree_data(chapter_list, sort_key='sort_order')

        if chapters:
            count_map = await BankService._get_chapter_count_map(
                db,
                bank_id=pk,
                chapter_ids=[chapter.id for chapter in chapter_list],
            )
            BankService._patch_tree_count(chapters, count_map)

        result = GetBankDetailWithChapters.model_validate(bank)
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
        bank = await bank_dao.get(db, bank_id)
        if not bank:
            raise errors.NotFoundError(msg='题库不存在')

        source_bank_id = BankService._resolve_chapter_source_bank_id(bank)
        chapter_list = await chapter_dao.get_by_bank(db, source_bank_id)
        if not chapter_list:
            return GetBankChapterProgress(bank_id=bank_id)

        chapter_ids = [chapter.id for chapter in chapter_list]
        q_count_map = await BankService._get_chapter_count_map(db, bank_id=bank_id, chapter_ids=chapter_ids)

        progress_stmt = (
            select(
                QuestionPlacement.chapter_id,
                func.count(func.distinct(PracticeRecord.question_id)),
                func.sum(sa.case((PracticeRecord.is_correct.is_(True), 1), else_=0)),
            )
            .join(QuestionPlacement, PracticeRecord.placement_id == QuestionPlacement.id)
            .where(
                PracticeRecord.user_id == user_id,
                QuestionPlacement.bank_id == bank_id,
                QuestionPlacement.chapter_id.in_(chapter_ids),
                PracticeRecord.user_answer.isnot(None),
            )
            .group_by(QuestionPlacement.chapter_id)
        )
        progress_rows = (await db.execute(progress_stmt)).all()

        answer_map: dict[int, int] = {}
        correct_map: dict[int, int] = {}
        for row in progress_rows:
            answer_map[row[0]] = row[1]
            correct_map[row[0]] = int(row[2] or 0)

        chapter_info: dict[int, dict[str, Any]] = {}
        for chapter in chapter_list:
            answer_count = answer_map.get(chapter.id, 0)
            correct_count = correct_map.get(chapter.id, 0)
            chapter_info[chapter.id] = {
                'chapter_id': chapter.id,
                'name': chapter.name,
                'question_count': q_count_map.get(chapter.id, 0),
                'answer_count': answer_count,
                'correct_count': correct_count,
                'correct_ratio': round(correct_count / answer_count * 100, 1) if answer_count > 0 else 0,
                'parent_id': chapter.parent_id,
                'sort_order': chapter.sort_order,
                'children': [],
            }

        root_nodes: list[dict[str, Any]] = []
        for info in chapter_info.values():
            parent_id = info.pop('parent_id', None)
            info['_sort'] = info.pop('sort_order', 0)
            if parent_id and parent_id in chapter_info:
                chapter_info[parent_id]['children'].append(info)
            else:
                root_nodes.append(info)

        def sort_tree(nodes: list[dict[str, Any]]) -> None:
            """递归排序章节树"""
            nodes.sort(key=lambda item: item.get('_sort', 0))
            for node in nodes:
                node.pop('_sort', None)
                if node['children']:
                    sort_tree(node['children'])

        sort_tree(root_nodes)

        return GetBankChapterProgress(
            bank_id=bank_id,
            total_question_count=sum(q_count_map.values()),
            total_answer_count=sum(answer_map.values()),
            total_correct_count=sum(correct_map.values()),
            chapters=[ChapterProgressNode(**item) for item in root_nodes],
        )

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
        :param bank_type: 内容类型
        :param parent_id: 父级 ID
        :return:
        """
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

        if bank_type == 3 or (bank_type is None and parent_id is None and not keyword):
            collection_ids = [item['id'] for item in tree_data if item.get('bank_type') == 3]
            if collection_ids:
                child_counts = await bank_dao.count_children_by_parent_ids(db, collection_ids)
                for item in tree_data:
                    if item.get('bank_type') == 3 and item['id'] in child_counts:
                        item['q_count_cache'] = child_counts[item['id']]

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
            raise errors.ConflictError(msg='题库编码已存在')

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
            raise errors.NotFoundError(msg='题库不存在')

        if bank.code != obj.code and await bank_dao.get_by_code(db, obj.code):
            raise errors.ConflictError(msg='题库编码已存在')

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
