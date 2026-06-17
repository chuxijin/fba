#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence
from time import perf_counter
from typing import Any

import sqlalchemy as sa

from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import noload

from backend.app.admin.crud.crud_category import category_dao
from backend.app.question_bank.crud.crud_bank import bank_dao
from backend.app.question_bank.crud.crud_user_bank_progress import user_bank_progress_dao
from backend.app.question_bank.model.bank import QuestionBank
from backend.app.question_bank.model.chapter import QuestionChapter
from backend.app.question_bank.model.question import Question, QuestionPlacement
from backend.app.question_bank.schema.bank import (
    BankProgressSummary,
    ChapterProgressTreeNode,
    GetBankChapterProgressWithTree,
    GetBankDetailWithChapters,
)
from backend.app.question_bank.service.bank_mount_service import COLLECTION_BANK_TYPE, bank_mount_service
from backend.common.exception import errors


class BankProgressService:
    """刷题内容进度服务类"""

    @staticmethod
    def resolve_chapter_source_bank_id(bank: QuestionBank) -> int:
        """解析内容实际使用的篇章来源内容 ID"""
        return bank.chapter_source_bank_id or bank.id

    @staticmethod
    async def get_chapter_count_map(
        db: AsyncSession,
        *,
        bank_id: int,
        chapter_ids: list[int],
    ) -> dict[int, int]:
        """按当前内容统计各篇章题量"""
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
    async def get_chapter_question_type_count_map(
        db: AsyncSession,
        *,
        bank_id: int,
        chapter_ids: list[int],
    ) -> dict[int, dict[str, int]]:
        """按当前内容统计各篇章题型题量"""
        if not chapter_ids:
            return {}

        stmt = (
            select(QuestionPlacement.chapter_id, Question.type, func.count(QuestionPlacement.id))
            .join(Question, Question.id == QuestionPlacement.question_id)
            .where(
                QuestionPlacement.bank_id == bank_id,
                QuestionPlacement.is_active.is_(True),
                QuestionPlacement.chapter_id.in_(chapter_ids),
            )
            .group_by(QuestionPlacement.chapter_id, Question.type)
        )
        rows = (await db.execute(stmt)).all()

        result: dict[int, dict[str, int]] = {}
        for chapter_id, question_type, count in rows:
            if chapter_id is None or not question_type:
                continue
            result.setdefault(chapter_id, {})[question_type] = int(count or 0)

        return result

    @staticmethod
    async def get_bank_question_type_counts(*, db: AsyncSession, bank_id: int) -> dict[str, int]:
        """按当前内容统计题型题量"""
        stmt = (
            select(Question.type, func.count(QuestionPlacement.id))
            .join(Question, Question.id == QuestionPlacement.question_id)
            .where(
                QuestionPlacement.bank_id == bank_id,
                QuestionPlacement.is_active.is_(True),
            )
            .group_by(Question.type)
        )
        rows = (await db.execute(stmt)).all()
        return {question_type: int(count or 0) for question_type, count in rows if question_type}

    @staticmethod
    async def get_bank_question_type_counts_by_bank_ids(
        *,
        db: AsyncSession,
        bank_ids: list[int],
    ) -> dict[str, int]:
        """按多个内容去重统计题型题量"""
        if not bank_ids:
            return {}

        stmt = (
            select(Question.type, func.count(sa.distinct(QuestionPlacement.question_id)))
            .join(Question, Question.id == QuestionPlacement.question_id)
            .where(
                QuestionPlacement.bank_id.in_(bank_ids),
                QuestionPlacement.is_active.is_(True),
            )
            .group_by(Question.type)
        )
        rows = (await db.execute(stmt)).all()
        return {question_type: int(count or 0) for question_type, count in rows if question_type}

    @staticmethod
    async def get_question_count_by_bank_ids(*, db: AsyncSession, bank_ids: list[int]) -> int:
        """按多个内容去重统计题量"""
        if not bank_ids:
            return 0

        stmt = select(func.count(sa.distinct(QuestionPlacement.question_id))).where(
            QuestionPlacement.bank_id.in_(bank_ids),
            QuestionPlacement.is_active.is_(True),
        )
        return int((await db.execute(stmt)).scalar_one() or 0)

    @staticmethod
    async def _get_bank_progress_summary(
        *,
        db: AsyncSession,
        bank_id: int,
        user_id: int,
    ) -> tuple[int, int, int]:
        """
        获取无篇章内容的整体进度

        :param db: 数据库会话
        :param bank_id: 内容 ID
        :param user_id: 用户 ID
        :return:
        """
        question_count_stmt = select(func.count(QuestionPlacement.id)).where(
            QuestionPlacement.bank_id == bank_id,
            QuestionPlacement.is_active.is_(True),
        )
        question_count = int((await db.execute(question_count_stmt)).scalar_one() or 0)

        progress_model = user_bank_progress_dao.model
        progress_stmt = select(
            func.count(sa.distinct(progress_model.question_id)),
            func.count(
                sa.distinct(
                    sa.case(
                        (progress_model.is_correct.is_(True), progress_model.question_id),
                        else_=None,
                    )
                ),
            ),
        ).where(
            progress_model.user_id == user_id,
            progress_model.bank_id == bank_id,
        )
        progress_row = (await db.execute(progress_stmt)).one()
        return question_count, int(progress_row[0] or 0), int(progress_row[1] or 0)

    @staticmethod
    async def _get_bank_progress_summary_by_bank_ids(
        *,
        db: AsyncSession,
        bank_ids: list[int],
        user_id: int,
    ) -> tuple[int, int, int]:
        """按多个内容去重统计整体进度"""
        if not bank_ids:
            return 0, 0, 0

        question_count_stmt = select(func.count(sa.distinct(QuestionPlacement.question_id))).where(
            QuestionPlacement.bank_id.in_(bank_ids),
            QuestionPlacement.is_active.is_(True),
        )
        question_count = int((await db.execute(question_count_stmt)).scalar_one() or 0)

        progress_model = user_bank_progress_dao.model
        progress_stmt = select(
            func.count(sa.distinct(progress_model.question_id)),
            func.count(
                sa.distinct(
                    sa.case(
                        (progress_model.is_correct.is_(True), progress_model.question_id),
                        else_=None,
                    )
                ),
            ),
        ).where(
            progress_model.user_id == user_id,
            progress_model.bank_id.in_(bank_ids),
        )
        progress_row = (await db.execute(progress_stmt)).one()
        return question_count, int(progress_row[0] or 0), int(progress_row[1] or 0)

    @staticmethod
    async def _get_chapter_question_type_progress_map(
        db: AsyncSession,
        *,
        bank_id: int,
        user_id: int,
        chapter_ids: list[int],
    ) -> dict[int, dict[str, dict[str, int]]]:
        """按篇章统计题型作答进度"""
        if not chapter_ids:
            return {}

        progress_model = user_bank_progress_dao.model
        stmt = (
            select(
                progress_model.chapter_id,
                Question.type,
                func.count(sa.distinct(progress_model.question_id)),
                func.count(
                    sa.distinct(
                        sa.case(
                            (progress_model.is_correct.is_(True), progress_model.question_id),
                            else_=None,
                        )
                    ),
                ),
            )
            .select_from(progress_model)
            .join(Question, Question.id == progress_model.question_id)
            .where(
                progress_model.user_id == user_id,
                progress_model.bank_id == bank_id,
                progress_model.chapter_id.in_(chapter_ids),
            )
            .group_by(progress_model.chapter_id, Question.type)
        )
        rows = (await db.execute(stmt)).all()

        result: dict[int, dict[str, dict[str, int]]] = {}
        for chapter_id, question_type, answer_count, correct_count in rows:
            if chapter_id is None or not question_type:
                continue
            result.setdefault(chapter_id, {})[question_type] = {
                'answer_count': int(answer_count or 0),
                'correct_count': int(correct_count or 0),
            }

        return result

    @staticmethod
    async def _get_chapter_answer_correct_maps(
        *,
        db: AsyncSession,
        bank_id: int,
        user_id: int,
        chapter_ids: list[int],
    ) -> tuple[dict[int, int], dict[int, int]]:
        """
        按篇章统计作答和答对数量

        :param db: 数据库会话
        :param bank_id: 内容 ID
        :param user_id: 用户 ID
        :param chapter_ids: 篇章 ID 列表
        :return:
        """
        progress_model = user_bank_progress_dao.model
        progress_stmt = (
            select(
                progress_model.chapter_id,
                func.count(sa.distinct(progress_model.question_id)),
                func.count(
                    sa.distinct(
                        sa.case(
                            (progress_model.is_correct.is_(True), progress_model.question_id),
                            else_=None,
                        )
                    ),
                ),
            )
            .select_from(progress_model)
            .where(
                progress_model.user_id == user_id,
                progress_model.bank_id == bank_id,
                progress_model.chapter_id.in_(chapter_ids),
            )
            .group_by(progress_model.chapter_id)
        )
        rows = (await db.execute(progress_stmt)).all()

        answer_map: dict[int, int] = {}
        correct_map: dict[int, int] = {}
        for chapter_id, answer_count, correct_count in rows:
            if chapter_id is None:
                continue
            answer_map[int(chapter_id)] = int(answer_count or 0)
            correct_map[int(chapter_id)] = int(correct_count or 0)

        return answer_map, correct_map

    @staticmethod
    def _build_chapter_count_map_from_type_count(
        question_type_count_map: dict[int, dict[str, int]],
    ) -> dict[int, int]:
        """
        从篇章题型题量统计篇章题量

        :param question_type_count_map: 篇章题型题量映射
        :return:
        """
        return {
            chapter_id: sum(int(count or 0) for count in type_counts.values())
            for chapter_id, type_counts in question_type_count_map.items()
        }

    @staticmethod
    def _build_chapter_answer_correct_maps_from_type_progress(
        question_type_progress_map: dict[int, dict[str, dict[str, int]]],
    ) -> tuple[dict[int, int], dict[int, int]]:
        """
        从篇章题型进度统计篇章作答和答对数量

        :param question_type_progress_map: 篇章题型进度映射
        :return:
        """
        answer_map: dict[int, int] = {}
        correct_map: dict[int, int] = {}
        for chapter_id, type_progress in question_type_progress_map.items():
            answer_map[chapter_id] = sum(int(progress.get('answer_count') or 0) for progress in type_progress.values())
            correct_map[chapter_id] = sum(
                int(progress.get('correct_count') or 0) for progress in type_progress.values()
            )

        return answer_map, correct_map

    @staticmethod
    async def _get_bank_question_type_progress(
        *,
        db: AsyncSession,
        bank_id: int,
        user_id: int,
    ) -> dict[str, dict[str, int]]:
        """按内容统计题型作答进度"""
        progress_model = user_bank_progress_dao.model
        stmt = (
            select(
                Question.type,
                func.count(sa.distinct(progress_model.question_id)),
                func.count(
                    sa.distinct(
                        sa.case(
                            (progress_model.is_correct.is_(True), progress_model.question_id),
                            else_=None,
                        )
                    ),
                ),
            )
            .select_from(progress_model)
            .join(Question, Question.id == progress_model.question_id)
            .where(
                progress_model.user_id == user_id,
                progress_model.bank_id == bank_id,
            )
            .group_by(Question.type)
        )
        rows = (await db.execute(stmt)).all()
        return {
            question_type: {
                'answer_count': int(answer_count or 0),
                'correct_count': int(correct_count or 0),
            }
            for question_type, answer_count, correct_count in rows
            if question_type
        }

    @staticmethod
    async def _get_bank_question_type_progress_by_bank_ids(
        *,
        db: AsyncSession,
        bank_ids: list[int],
        user_id: int,
    ) -> dict[str, dict[str, int]]:
        """按多个内容统计题型作答进度"""
        if not bank_ids:
            return {}

        progress_model = user_bank_progress_dao.model
        stmt = (
            select(
                Question.type,
                func.count(sa.distinct(progress_model.question_id)),
                func.count(
                    sa.distinct(
                        sa.case(
                            (progress_model.is_correct.is_(True), progress_model.question_id),
                            else_=None,
                        )
                    ),
                ),
            )
            .select_from(progress_model)
            .join(Question, Question.id == progress_model.question_id)
            .where(
                progress_model.user_id == user_id,
                progress_model.bank_id.in_(bank_ids),
            )
            .group_by(Question.type)
        )
        rows = (await db.execute(stmt)).all()
        return {
            question_type: {
                'answer_count': int(answer_count or 0),
                'correct_count': int(correct_count or 0),
            }
            for question_type, answer_count, correct_count in rows
            if question_type
        }

    @staticmethod
    def merge_question_type_counts(target: dict[str, int], source: dict[str, int]) -> None:
        """
        合并题型题量

        :param target: 目标统计
        :param source: 来源统计
        :return:
        """
        for question_type, count in source.items():
            target[question_type] = target.get(question_type, 0) + count

    @staticmethod
    def build_question_type_progress(
        question_type_counts: dict[str, int],
        progress_map: dict[str, dict[str, int]],
    ) -> dict[str, dict[str, int | float]]:
        """
        构造题型进度

        :param question_type_counts: 题型题量
        :param progress_map: 题型作答进度
        :return:
        """
        result: dict[str, dict[str, int | float]] = {}
        for question_type, question_count in question_type_counts.items():
            progress = progress_map.get(question_type, {})
            answer_count = int(progress.get('answer_count') or 0)
            correct_count = int(progress.get('correct_count') or 0)
            result[question_type] = {
                'question_count': int(question_count or 0),
                'answer_count': answer_count,
                'correct_count': correct_count,
                'correct_ratio': round(correct_count / answer_count * 100, 1) if answer_count > 0 else 0,
            }

        return result

    @staticmethod
    def _merge_question_type_progress(target: dict[str, dict[str, Any]], source: dict[str, dict[str, Any]]) -> None:
        """
        合并题型进度

        :param target: 目标进度
        :param source: 来源进度
        :return:
        """
        for question_type, item in source.items():
            current = target.setdefault(
                question_type,
                {
                    'question_count': 0,
                    'answer_count': 0,
                    'correct_count': 0,
                    'correct_ratio': 0,
                },
            )
            current['question_count'] = int(current.get('question_count') or 0) + int(item.get('question_count') or 0)
            current['answer_count'] = int(current.get('answer_count') or 0) + int(item.get('answer_count') or 0)
            current['correct_count'] = int(current.get('correct_count') or 0) + int(item.get('correct_count') or 0)
            answer_count = int(current.get('answer_count') or 0)
            correct_count = int(current.get('correct_count') or 0)
            current['correct_ratio'] = round(correct_count / answer_count * 100, 1) if answer_count > 0 else 0

    @classmethod
    def patch_tree_count(
        cls,
        nodes: list[dict[str, Any]],
        count_map: dict[int, int],
        question_type_count_map: dict[int, dict[str, int]] | None = None,
    ) -> None:
        """
        递归回填篇章树题量和题型题量

        :param nodes: 篇章树节点
        :param count_map: 篇章题量映射
        :param question_type_count_map: 题型题量映射
        :return:
        """
        for node in nodes:
            direct_count = count_map.get(node['id'], 0)
            type_counts = dict((question_type_count_map or {}).get(node['id'], {}))
            if node.get('children'):
                cls.patch_tree_count(node['children'], count_map, question_type_count_map)
                direct_count += sum(child.get('q_count_cache', 0) for child in node['children'])
                for child in node['children']:
                    cls.merge_question_type_counts(type_counts, child.get('question_type_counts') or {})
            node['q_count_cache'] = direct_count
            node['question_type_counts'] = type_counts

    @classmethod
    async def build_collection_detail(
        cls,
        *,
        db: AsyncSession,
        bank: QuestionBank,
    ) -> GetBankDetailWithChapters:
        """
        构造合集详情

        :param db: 数据库会话
        :param bank: 合集内容
        :return:
        """
        item_ids = await bank_mount_service.get_active_descendant_item_ids(db, collection_id=bank.id)
        result = GetBankDetailWithChapters.model_validate(bank)
        result.q_count_cache = await cls.get_question_count_by_bank_ids(db=db, bank_ids=item_ids)
        result.question_type_counts = await cls.get_bank_question_type_counts_by_bank_ids(
            db=db,
            bank_ids=item_ids,
        )
        result.chapters = []
        return result

    @classmethod
    async def _build_collection_chapter_progress(
        cls,
        *,
        db: AsyncSession,
        bank_id: int,
        user_id: int,
    ) -> GetBankChapterProgressWithTree:
        """
        构造合集进度

        :param db: 数据库会话
        :param bank_id: 合集内容 ID
        :param user_id: 用户 ID
        :return:
        """
        item_ids = await bank_mount_service.get_active_descendant_item_ids(db, collection_id=bank_id)
        question_count, answer_count, correct_count = await cls._get_bank_progress_summary_by_bank_ids(
            db=db,
            bank_ids=item_ids,
            user_id=user_id,
        )
        question_type_counts = await cls.get_bank_question_type_counts_by_bank_ids(
            db=db,
            bank_ids=item_ids,
        )
        question_type_progress = await cls._get_bank_question_type_progress_by_bank_ids(
            db=db,
            bank_ids=item_ids,
            user_id=user_id,
        )
        merged_type_progress = cls.build_question_type_progress(question_type_counts, question_type_progress)
        return GetBankChapterProgressWithTree(
            bank_id=bank_id,
            total_question_count=question_count,
            total_answer_count=answer_count,
            total_correct_count=correct_count,
            correct_ratio=round(correct_count / answer_count * 100, 1) if answer_count > 0 else 0,
            question_type_progress=merged_type_progress,
            chapters=[],
        )

    @classmethod
    async def _build_overall_chapter_progress(
        cls,
        *,
        db: AsyncSession,
        bank_id: int,
        user_id: int,
    ) -> GetBankChapterProgressWithTree:
        """
        构造无篇章内容进度

        :param db: 数据库会话
        :param bank_id: 内容 ID
        :param user_id: 用户 ID
        :return:
        """
        question_count, answer_count, correct_count = await cls._get_bank_progress_summary(
            db=db,
            bank_id=bank_id,
            user_id=user_id,
        )
        question_type_counts = await cls.get_bank_question_type_counts(db=db, bank_id=bank_id)
        question_type_progress = await cls._get_bank_question_type_progress(
            db=db,
            bank_id=bank_id,
            user_id=user_id,
        )
        merged_type_progress = cls.build_question_type_progress(question_type_counts, question_type_progress)
        return GetBankChapterProgressWithTree(
            bank_id=bank_id,
            total_question_count=question_count,
            total_answer_count=answer_count,
            total_correct_count=correct_count,
            correct_ratio=round(correct_count / answer_count * 100, 1) if answer_count > 0 else 0,
            question_type_progress=merged_type_progress,
            chapters=[],
        )

    @classmethod
    def _build_chapter_progress_nodes(
        cls,
        *,
        chapter_list: Sequence[QuestionChapter],
        q_count_map: dict[int, int],
        answer_map: dict[int, int],
        correct_map: dict[int, int],
        question_type_count_map: dict[int, dict[str, int]],
        question_type_progress_map: dict[int, dict[str, dict[str, int]]],
    ) -> list[dict[str, Any]]:
        """
        构造篇章进度树

        :param chapter_list: 篇章列表
        :param q_count_map: 篇章题量映射
        :param answer_map: 篇章作答映射
        :param correct_map: 篇章答对映射
        :param question_type_count_map: 篇章题型题量映射
        :param question_type_progress_map: 篇章题型进度映射
        :return:
        """
        chapter_info: dict[int, dict[str, Any]] = {}
        for chapter in chapter_list:
            answer_count = answer_map.get(chapter.id, 0)
            correct_count = correct_map.get(chapter.id, 0)
            chapter_info[chapter.id] = {
                'chapter_id': chapter.id,
                'name': chapter.name,
                'question_type_counts': dict(question_type_count_map.get(chapter.id, {})),
                'question_type_progress': cls.build_question_type_progress(
                    question_type_count_map.get(chapter.id, {}),
                    question_type_progress_map.get(chapter.id, {}),
                ),
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
                continue
            root_nodes.append(info)

        cls._sort_and_rollup_chapter_progress(root_nodes)
        return root_nodes

    @classmethod
    def _build_chapter_progress_tree(
        cls,
        *,
        chapter_list: Sequence[QuestionChapter],
        q_count_map: dict[int, int],
        answer_map: dict[int, int],
        correct_map: dict[int, int],
        question_type_count_map: dict[int, dict[str, int]],
        question_type_progress_map: dict[int, dict[str, dict[str, int]]],
    ) -> list[ChapterProgressTreeNode]:
        """
        构造篇章进度树节点（结构 + 进度合并）

        :param chapter_list: 篇章列表
        :param q_count_map: 篇章题量映射
        :param answer_map: 篇章作答映射
        :param correct_map: 篇章答对映射
        :param question_type_count_map: 篇章题型题量映射
        :param question_type_progress_map: 篇章题型进度映射
        :return:
        """
        raw_nodes: dict[int, dict[str, Any]] = {}
        for chapter in chapter_list:
            answer_count = answer_map.get(chapter.id, 0)
            correct_count = correct_map.get(chapter.id, 0)
            raw_nodes[chapter.id] = {
                'id': chapter.id,
                'name': chapter.name,
                'sort_order': chapter.sort_order,
                'parent_id': chapter.parent_id,
                'q_count_cache': q_count_map.get(chapter.id, 0),
                'question_type_counts': dict(question_type_count_map.get(chapter.id, {})),
                'answer_count': answer_count,
                'correct_count': correct_count,
                'correct_ratio': round(correct_count / answer_count * 100, 1) if answer_count > 0 else 0,
                'question_type_progress': cls.build_question_type_progress(
                    question_type_count_map.get(chapter.id, {}),
                    question_type_progress_map.get(chapter.id, {}),
                ),
                'children': [],
            }

        # 构建树形结构（dict 层面）
        root_dicts: list[dict[str, Any]] = []
        for info in raw_nodes.values():
            parent_id = info.pop('parent_id', None)
            if parent_id and parent_id in raw_nodes:
                raw_nodes[parent_id]['children'].append(info)
            else:
                root_dicts.append(info)

        cls._sort_dict_tree(root_dicts)

        # dict → ChapterProgressTreeNode 递归转换
        def to_node(d: dict[str, Any]) -> ChapterProgressTreeNode:
            return ChapterProgressTreeNode(
                id=d['id'],
                name=d['name'],
                sort_order=d['sort_order'],
                q_count_cache=d['q_count_cache'],
                question_type_counts=d['question_type_counts'],
                answer_count=d['answer_count'],
                correct_count=d['correct_count'],
                correct_ratio=d['correct_ratio'],
                question_type_progress=d['question_type_progress'],
                children=[to_node(c) for c in d.get('children', [])],
            )

        return [to_node(d) for d in root_dicts]

    @classmethod
    def _sort_dict_tree(cls, nodes: list[dict[str, Any]]) -> None:
        """
        排序篇章进度字典树

        :param nodes: 篇章进度字典节点列表
        :return:
        """
        nodes.sort(key=lambda item: item.get('sort_order', 0))
        for node in nodes:
            if node.get('children'):
                cls._sort_dict_tree(node['children'])

    @classmethod
    def _sort_and_rollup_chapter_progress(cls, nodes: list[dict[str, Any]]) -> None:
        """
        排序并向上汇总篇章进度

        :param nodes: 篇章进度节点
        :return:
        """
        nodes.sort(key=lambda item: item.get('_sort', 0))
        for node in nodes:
            node.pop('_sort', None)
            if not node['children']:
                continue

            cls._sort_and_rollup_chapter_progress(node['children'])
            node['question_count'] += sum(child['question_count'] for child in node['children'])
            node['answer_count'] += sum(child['answer_count'] for child in node['children'])
            node['correct_count'] += sum(child['correct_count'] for child in node['children'])
            for child in node['children']:
                cls.merge_question_type_counts(node['question_type_counts'], child.get('question_type_counts') or {})
                cls._merge_question_type_progress(
                    node['question_type_progress'],
                    child.get('question_type_progress') or {},
                )

            if node['answer_count'] > 0:
                node['correct_ratio'] = round(node['correct_count'] / node['answer_count'] * 100, 1)

    @classmethod
    def _merge_root_question_type_progress(cls, nodes: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        """
        汇总根篇章题型进度

        :param nodes: 根篇章进度节点
        :return:
        """
        result: dict[str, dict[str, Any]] = {}
        for node in nodes:
            cls._merge_question_type_progress(result, node.get('question_type_progress') or {})

        return result

    @classmethod
    async def get_chapter_progress(
        cls, *, db: AsyncSession, bank_id: int, user_id: int
    ) -> GetBankChapterProgressWithTree:
        """
        获取用户在指定内容下的篇章做题进度（含完整章节树）

        :param db: 数据库会话
        :param bank_id: 内容 ID
        :param user_id: 用户 ID
        :return:
        """
        # 分段计时埋点（性能诊断用，定位瓶颈后可移除）
        timings: list[tuple[str, float]] = []
        total_start = perf_counter()

        # 一条 SQL 同时取 bank 主信息 + 章节列表（合集分支 ON 恒 false，自动跳过 chapter 扫描）
        chapter_source = sa.func.coalesce(QuestionBank.chapter_source_bank_id, QuestionBank.id)
        stmt = (
            select(QuestionBank, QuestionChapter)
            .outerjoin(
                QuestionChapter,
                sa.and_(
                    QuestionChapter.bank_id == chapter_source,
                    QuestionBank.bank_type != COLLECTION_BANK_TYPE,
                ),
            )
            .where(QuestionBank.id == bank_id)
            .options(noload(QuestionChapter.bank))
            .order_by(QuestionChapter.sort_order.asc().nulls_last())
        )
        t0 = perf_counter()
        rows = (await db.execute(stmt)).all()
        timings.append(('sql1_bank_with_chapters', perf_counter() - t0))

        if not rows:
            raise errors.NotFoundError(msg='刷题内容不存在')

        bank: QuestionBank = rows[0][0]
        chapter_list: list[QuestionChapter] = [row[1] for row in rows if row[1] is not None]

        if bank.bank_type == COLLECTION_BANK_TYPE:
            t0 = perf_counter()
            result = await cls._build_collection_chapter_progress(db=db, bank_id=bank_id, user_id=user_id)
            timings.append(('collection_branch', perf_counter() - t0))
            logger.debug(
                'chapter_progress_timing | bank_id={} user_id={} branch=collection total={:.1f}ms detail={}',
                bank_id,
                user_id,
                (perf_counter() - total_start) * 1000,
                ', '.join(f'{name}={cost * 1000:.1f}ms' for name, cost in timings),
            )
            return result

        if not chapter_list:
            t0 = perf_counter()
            result = await cls._build_overall_chapter_progress(db=db, bank_id=bank_id, user_id=user_id)
            timings.append(('overall_branch', perf_counter() - t0))
            logger.debug(
                'chapter_progress_timing | bank_id={} user_id={} branch=overall total={:.1f}ms detail={}',
                bank_id,
                user_id,
                (perf_counter() - total_start) * 1000,
                ', '.join(f'{name}={cost * 1000:.1f}ms' for name, cost in timings),
            )
            return result

        chapter_ids = [chapter.id for chapter in chapter_list]

        t0 = perf_counter()
        question_type_count_map = await cls.get_chapter_question_type_count_map(
            db=db,
            bank_id=bank_id,
            chapter_ids=chapter_ids,
        )
        timings.append(('sql2_qtype_count_map', perf_counter() - t0))

        q_count_map = cls._build_chapter_count_map_from_type_count(question_type_count_map)

        t0 = perf_counter()
        question_type_progress_map = await cls._get_chapter_question_type_progress_map(
            db=db,
            bank_id=bank_id,
            user_id=user_id,
            chapter_ids=chapter_ids,
        )
        timings.append(('sql3_qtype_progress_map', perf_counter() - t0))

        answer_map, correct_map = cls._build_chapter_answer_correct_maps_from_type_progress(
            question_type_progress_map,
        )

        t0 = perf_counter()
        tree_nodes = cls._build_chapter_progress_tree(
            chapter_list=chapter_list,
            q_count_map=q_count_map,
            answer_map=answer_map,
            correct_map=correct_map,
            question_type_count_map=question_type_count_map,
            question_type_progress_map=question_type_progress_map,
        )
        timings.append(('build_tree', perf_counter() - t0))

        t0 = perf_counter()
        total_question_count = sum(q_count_map.values())
        total_answer_count = sum(answer_map.values())
        total_correct_count = sum(correct_map.values())

        # 从原始数据直接合并题型进度
        merged_type_count: dict[str, int] = {}
        for counts in question_type_count_map.values():
            cls.merge_question_type_counts(merged_type_count, counts)
        merged_type_answer_correct: dict[str, dict[str, int]] = {}
        for progress in question_type_progress_map.values():
            for qtype, item in progress.items():
                cur = merged_type_answer_correct.setdefault(qtype, {'answer_count': 0, 'correct_count': 0})
                cur['answer_count'] += int(item.get('answer_count') or 0)
                cur['correct_count'] += int(item.get('correct_count') or 0)
        merged_type_progress = cls.build_question_type_progress(merged_type_count, merged_type_answer_correct)

        result = GetBankChapterProgressWithTree(
            bank_id=bank_id,
            total_question_count=total_question_count,
            total_answer_count=total_answer_count,
            total_correct_count=total_correct_count,
            correct_ratio=round(total_correct_count / total_answer_count * 100, 1) if total_answer_count > 0 else 0,
            question_type_progress=merged_type_progress,
            chapters=tree_nodes,
        )
        timings.append(('aggregate_and_serialize', perf_counter() - t0))

        logger.debug(
            'chapter_progress_timing | bank_id={} user_id={} branch=normal chapters={} total={:.1f}ms detail={}',
            bank_id,
            user_id,
            len(chapter_list),
            (perf_counter() - total_start) * 1000,
            ', '.join(f'{name}={cost * 1000:.1f}ms' for name, cost in timings),
        )
        return result

    @staticmethod
    async def _resolve_progress_summary_bank_ids(
        *,
        db: AsyncSession,
        bank_ids: list[int] | None,
        cat_id: int | None,
    ) -> tuple[list[int], bool]:
        """
        解析进度摘要内容 ID

        :param db: 数据库会话
        :param bank_ids: 内容 ID 列表
        :param cat_id: 分类 ID
        :return:
        """
        has_collection = False
        if cat_id is not None:
            cat_ids = await category_dao.get_subtree_ids_by_path(
                db,
                cat_id,
                app_code='youanshang',
                type_='product_catalog',
                status=True,
            )
            stmt = select(QuestionBank.id).where(
                QuestionBank.cat_id.in_(cat_ids),
                QuestionBank.status == 1,
                QuestionBank.bank_type != COLLECTION_BANK_TYPE,
            )
            rows = (await db.execute(stmt)).all()
            resolved_bank_ids = [int(row[0]) for row in rows]
        elif bank_ids:
            resolved_bank_ids = [int(bank_id) for bank_id in bank_ids]
            bank_rows = await bank_dao.get_progress_count_mappings_by_ids(db, resolved_bank_ids)
            has_collection = any(int(row.get('bank_type') or 0) == COLLECTION_BANK_TYPE for row in bank_rows)
        else:
            return [], False

        return list(dict.fromkeys(bank_id for bank_id in resolved_bank_ids if bank_id > 0)), has_collection

    @staticmethod
    async def _get_progress_question_count_map(
        *,
        db: AsyncSession,
        bank_ids: list[int],
    ) -> dict[int, int]:
        """
        批量统计内容题量

        :param db: 数据库会话
        :param bank_ids: 内容 ID 列表
        :return:
        """
        bank_rows = await bank_dao.get_progress_count_mappings_by_ids(db, bank_ids)
        return {int(row['id']): int(row.get('q_count_cache') or 0) for row in bank_rows}

    @staticmethod
    async def _get_progress_answer_correct_maps(
        *,
        db: AsyncSession,
        bank_ids: list[int],
        user_id: int,
    ) -> tuple[dict[int, int], dict[int, int]]:
        """
        批量统计内容作答和答对数量

        :param db: 数据库会话
        :param bank_ids: 内容 ID 列表
        :param user_id: 用户 ID
        :return:
        """
        return await user_bank_progress_dao.get_answer_correct_maps(
            db,
            user_id=user_id,
            bank_ids=bank_ids,
        )

    @staticmethod
    async def _get_progress_type_count_map(
        *,
        db: AsyncSession,
        bank_ids: list[int],
    ) -> dict[int, dict[str, int]]:
        """
        批量统计内容题型题量

        :param db: 数据库会话
        :param bank_ids: 内容 ID 列表
        :return:
        """
        type_count_stmt = (
            select(QuestionPlacement.bank_id, Question.type, func.count(QuestionPlacement.id))
            .join(Question, Question.id == QuestionPlacement.question_id)
            .where(
                QuestionPlacement.bank_id.in_(bank_ids),
                QuestionPlacement.is_active.is_(True),
            )
            .group_by(QuestionPlacement.bank_id, Question.type)
        )
        rows = (await db.execute(type_count_stmt)).all()
        result: dict[int, dict[str, int]] = {}
        for bank_id, question_type, count in rows:
            if not question_type:
                continue
            result.setdefault(int(bank_id), {})[question_type] = int(count or 0)

        return result

    @staticmethod
    async def _get_progress_type_progress_map(
        *,
        db: AsyncSession,
        bank_ids: list[int],
        user_id: int,
    ) -> dict[int, dict[str, dict[str, int]]]:
        """
        批量统计内容题型作答进度

        :param db: 数据库会话
        :param bank_ids: 内容 ID 列表
        :param user_id: 用户 ID
        :return:
        """
        progress_model = user_bank_progress_dao.model
        type_progress_stmt = (
            select(
                progress_model.bank_id,
                Question.type,
                func.count(sa.distinct(progress_model.question_id)),
                func.count(
                    sa.distinct(
                        sa.case(
                            (progress_model.is_correct.is_(True), progress_model.question_id),
                            else_=None,
                        )
                    ),
                ),
            )
            .select_from(progress_model)
            .join(Question, Question.id == progress_model.question_id)
            .where(
                progress_model.user_id == user_id,
                progress_model.bank_id.in_(bank_ids),
            )
            .group_by(progress_model.bank_id, Question.type)
        )
        rows = (await db.execute(type_progress_stmt)).all()
        result: dict[int, dict[str, dict[str, int]]] = {}
        for bank_id, question_type, answer_count, correct_count in rows:
            if not question_type:
                continue
            result.setdefault(int(bank_id), {})[question_type] = {
                'answer_count': int(answer_count or 0),
                'correct_count': int(correct_count or 0),
            }

        return result

    @classmethod
    async def _patch_collection_progress_summary_maps(
        cls,
        *,
        db: AsyncSession,
        bank_ids: list[int],
        user_id: int,
        question_count_map: dict[int, int],
        answer_map: dict[int, int],
        correct_map: dict[int, int],
        type_count_map: dict[int, dict[str, int]],
        type_progress_map: dict[int, dict[str, dict[str, int]]],
        has_collection: bool,
    ) -> None:
        """
        回填合集进度摘要

        :param db: 数据库会话
        :param bank_ids: 内容 ID 列表
        :param user_id: 用户 ID
        :param question_count_map: 题量映射
        :param answer_map: 作答映射
        :param correct_map: 答对映射
        :param type_count_map: 题型题量映射
        :param type_progress_map: 题型进度映射
        :return:
        """
        if not has_collection:
            return

        bank_rows = await bank_dao.get_progress_count_mappings_by_ids(db, bank_ids)
        collection_ids = [int(row['id']) for row in bank_rows if int(row.get('bank_type') or 0) == COLLECTION_BANK_TYPE]
        if not collection_ids:
            return

        descendant_map = await bank_mount_service.get_active_descendant_item_ids_map(
            db,
            collection_ids=collection_ids,
        )
        collection_item_rows = [
            (collection_id, item_id) for collection_id, item_ids in descendant_map.items() for item_id in item_ids
        ]
        collection_question_count_map = await cls._get_collection_question_count_map(
            db=db,
            collection_item_rows=collection_item_rows,
        )
        collection_answer_map, collection_correct_map = await cls._get_collection_answer_correct_maps(
            db=db,
            collection_item_rows=collection_item_rows,
            user_id=user_id,
        )

        for collection_id in collection_ids:
            question_count_map[collection_id] = collection_question_count_map.get(collection_id, 0)
            answer_map[collection_id] = collection_answer_map.get(collection_id, 0)
            correct_map[collection_id] = collection_correct_map.get(collection_id, 0)
            type_count_map[collection_id] = {}
            type_progress_map[collection_id] = {}

    @staticmethod
    def _build_collection_item_values(collection_item_rows: list[tuple[int, int]]) -> sa.Values:
        """
        构造合集后代内容关系值表

        :param collection_item_rows: 合集和后代内容关系
        :return:
        """
        return sa.values(
            sa.column('collection_id', sa.BigInteger),
            sa.column('item_id', sa.BigInteger),
            name='collection_items',
        ).data(collection_item_rows)

    @classmethod
    async def _get_collection_question_count_map(
        cls,
        *,
        db: AsyncSession,
        collection_item_rows: list[tuple[int, int]],
    ) -> dict[int, int]:
        """
        批量统计合集后代题量

        :param db: 数据库会话
        :param collection_item_rows: 合集和后代内容关系
        :return:
        """
        if not collection_item_rows:
            return {}

        collection_items = cls._build_collection_item_values(collection_item_rows).alias('collection_items')
        stmt = (
            select(
                collection_items.c.collection_id,
                func.count(sa.distinct(QuestionPlacement.question_id)),
            )
            .select_from(collection_items)
            .join(QuestionPlacement, QuestionPlacement.bank_id == collection_items.c.item_id)
            .where(
                QuestionPlacement.is_active.is_(True),
            )
            .group_by(collection_items.c.collection_id)
        )
        rows = (await db.execute(stmt)).all()
        return {int(collection_id): int(count or 0) for collection_id, count in rows}

    @classmethod
    async def _get_collection_answer_correct_maps(
        cls,
        *,
        db: AsyncSession,
        collection_item_rows: list[tuple[int, int]],
        user_id: int,
    ) -> tuple[dict[int, int], dict[int, int]]:
        """
        批量统计合集后代作答和答对数

        :param db: 数据库会话
        :param collection_item_rows: 合集和后代内容关系
        :param user_id: 用户 ID
        :return:
        """
        if not collection_item_rows:
            return {}, {}

        collection_items = cls._build_collection_item_values(collection_item_rows).alias('collection_items')
        progress_model = user_bank_progress_dao.model
        stmt = (
            select(
                collection_items.c.collection_id,
                func.count(sa.distinct(progress_model.question_id)),
                func.count(
                    sa.distinct(
                        sa.case(
                            (progress_model.is_correct.is_(True), progress_model.question_id),
                            else_=None,
                        )
                    ),
                ),
            )
            .select_from(collection_items)
            .join(progress_model, progress_model.bank_id == collection_items.c.item_id)
            .where(
                progress_model.user_id == user_id,
            )
            .group_by(collection_items.c.collection_id)
        )
        rows = (await db.execute(stmt)).all()
        answer_map = {int(collection_id): int(answer_count or 0) for collection_id, answer_count, _ in rows}
        correct_map = {int(collection_id): int(correct_count or 0) for collection_id, _, correct_count in rows}
        return answer_map, correct_map

    @classmethod
    def _build_progress_summaries(
        cls,
        *,
        bank_ids: list[int],
        question_count_map: dict[int, int],
        answer_map: dict[int, int],
        correct_map: dict[int, int],
        type_count_map: dict[int, dict[str, int]],
        type_progress_map: dict[int, dict[str, dict[str, int]]],
    ) -> list[BankProgressSummary]:
        """
        构造内容进度摘要

        :param bank_ids: 内容 ID 列表
        :param question_count_map: 题量映射
        :param answer_map: 作答映射
        :param correct_map: 答对映射
        :param type_count_map: 题型题量映射
        :param type_progress_map: 题型进度映射
        :return:
        """
        result: list[BankProgressSummary] = []
        for bank_id in bank_ids:
            answer_count = answer_map.get(bank_id, 0)
            correct_count = correct_map.get(bank_id, 0)
            result.append(
                BankProgressSummary(
                    bank_id=bank_id,
                    question_count=question_count_map.get(bank_id, 0),
                    answer_count=answer_count,
                    correct_count=correct_count,
                    correct_ratio=round(correct_count / answer_count * 100, 1) if answer_count > 0 else 0,
                    question_type_progress=cls.build_question_type_progress(
                        type_count_map.get(bank_id, {}),
                        type_progress_map.get(bank_id, {}),
                    ),
                )
            )

        return result

    @classmethod
    async def get_progress_summaries(
        cls,
        *,
        db: AsyncSession,
        bank_ids: list[int] | None = None,
        cat_id: int | None = None,
        user_id: int,
    ) -> list[BankProgressSummary]:
        """
        批量获取内容进度摘要

        :param db: 数据库会话
        :param bank_ids: 内容 ID 列表
        :param cat_id: 分类 ID
        :param user_id: 用户 ID
        :return:
        """
        normalized_bank_ids, has_collection = await cls._resolve_progress_summary_bank_ids(
            db=db,
            bank_ids=bank_ids,
            cat_id=cat_id,
        )
        if not normalized_bank_ids:
            return []

        question_count_map = await cls._get_progress_question_count_map(
            db=db,
            bank_ids=normalized_bank_ids,
        )
        answer_map, correct_map = await cls._get_progress_answer_correct_maps(
            db=db,
            bank_ids=normalized_bank_ids,
            user_id=user_id,
        )
        type_count_map: dict[int, dict[str, int]] = {}
        type_progress_map: dict[int, dict[str, dict[str, int]]] = {}
        await cls._patch_collection_progress_summary_maps(
            db=db,
            bank_ids=normalized_bank_ids,
            user_id=user_id,
            question_count_map=question_count_map,
            answer_map=answer_map,
            correct_map=correct_map,
            type_count_map=type_count_map,
            type_progress_map=type_progress_map,
            has_collection=has_collection,
        )
        return cls._build_progress_summaries(
            bank_ids=normalized_bank_ids,
            question_count_map=question_count_map,
            answer_map=answer_map,
            correct_map=correct_map,
            type_count_map=type_count_map,
            type_progress_map=type_progress_map,
        )


bank_progress_service: BankProgressService = BankProgressService()
