#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence
from datetime import timedelta
from typing import Any

import sqlalchemy as sa

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.admin.crud.crud_category import category_dao
from backend.app.access.constants import CommonStatus
from backend.app.access.crud.crud_entitlement import entitlement_dao
from backend.app.question_bank.crud.crud_bank import bank_dao
from backend.app.question_bank.crud.crud_chapter import chapter_dao
from backend.app.question_bank.model.bank import QuestionBank
from backend.app.question_bank.model.practice import PracticeRecord, PracticeSession
from backend.app.question_bank.model.question import Question, QuestionPlacement
from backend.app.question_bank.schema.bank import (
    BankProgressSummary,
    ChapterProgressNode,
    CreateBankParam,
    DeleteBankParam,
    GetBankChapterProgress,
    GetBankDetailWithChapters,
    UpdateBankParam,
)
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
    async def _validate_access_entitlement_code(
        *,
        db: AsyncSession,
        access_entitlement_code: str | None,
    ) -> None:
        """
        校验题库访问权益编码

        :param db: 数据库会话
        :param access_entitlement_code: 权益编码
        :return:
        """
        if access_entitlement_code is None:
            return

        entitlement_code = access_entitlement_code.strip()
        if not entitlement_code:
            return

        entitlement = await entitlement_dao.get_by_code(db, entitlement_code)
        if not entitlement:
            raise errors.NotFoundError(msg=f'权益编码不存在: {entitlement_code}')
        if entitlement.status != CommonStatus.ACTIVE:
            raise errors.RequestError(msg=f'权益编码未启用: {entitlement_code}')

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
    async def _get_chapter_question_type_count_map(
        db: AsyncSession,
        *,
        bank_id: int,
        chapter_ids: list[int],
    ) -> dict[int, dict[str, int]]:
        """按当前题库统计各章节题型题量"""
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
    async def _get_bank_question_type_counts(*, db: AsyncSession, bank_id: int) -> dict[str, int]:
        """按当前题库统计题型题量"""
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
    async def _get_bank_progress_summary(
        *,
        db: AsyncSession,
        bank_id: int,
        user_id: int,
    ) -> tuple[int, int, int]:
        """
        获取无章节题库的整体进度

        :param db: 数据库会话
        :param bank_id: 题库 ID
        :param user_id: 用户 ID
        :return:
        """
        question_count_stmt = (
            select(func.count(QuestionPlacement.id))
            .where(
                QuestionPlacement.bank_id == bank_id,
                QuestionPlacement.is_active.is_(True),
            )
        )
        question_count = int((await db.execute(question_count_stmt)).scalar_one() or 0)

        progress_stmt = (
            select(
                func.count(PracticeRecord.id),
                func.count(
                    sa.case(
                        (PracticeRecord.is_correct.is_(True), PracticeRecord.id),
                        else_=None,
                    )
                ),
            )
            .join(QuestionPlacement, PracticeRecord.placement_id == QuestionPlacement.id)
            .where(
                PracticeRecord.user_id == user_id,
                QuestionPlacement.bank_id == bank_id,
                PracticeRecord.user_answer.isnot(None),
            )
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
        """按章节统计题型作答进度"""
        if not chapter_ids:
            return {}

        stmt = (
            select(
                QuestionPlacement.chapter_id,
                Question.type,
                func.count(PracticeRecord.id),
                func.count(
                    sa.case(
                        (PracticeRecord.is_correct.is_(True), PracticeRecord.id),
                        else_=None,
                    )
                ),
            )
            .join(QuestionPlacement, PracticeRecord.placement_id == QuestionPlacement.id)
            .join(Question, Question.id == QuestionPlacement.question_id)
            .where(
                PracticeRecord.user_id == user_id,
                QuestionPlacement.bank_id == bank_id,
                QuestionPlacement.chapter_id.in_(chapter_ids),
                PracticeRecord.user_answer.isnot(None),
            )
            .group_by(QuestionPlacement.chapter_id, Question.type)
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
    async def _get_bank_question_type_progress(
        *,
        db: AsyncSession,
        bank_id: int,
        user_id: int,
    ) -> dict[str, dict[str, int]]:
        """按题库统计题型作答进度"""
        stmt = (
            select(
                Question.type,
                func.count(PracticeRecord.id),
                func.count(
                    sa.case(
                        (PracticeRecord.is_correct.is_(True), PracticeRecord.id),
                        else_=None,
                    )
                ),
            )
            .join(QuestionPlacement, PracticeRecord.placement_id == QuestionPlacement.id)
            .join(Question, Question.id == QuestionPlacement.question_id)
            .where(
                PracticeRecord.user_id == user_id,
                QuestionPlacement.bank_id == bank_id,
                PracticeRecord.user_answer.isnot(None),
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
    def _merge_question_type_counts(target: dict[str, int], source: dict[str, int]) -> None:
        """
        合并题型题量

        :param target: 目标统计
        :param source: 来源统计
        :return:
        """
        for question_type, count in source.items():
            target[question_type] = target.get(question_type, 0) + count

    @staticmethod
    def _build_question_type_progress(
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

    @staticmethod
    def _patch_tree_count(
        nodes: list[dict[str, Any]],
        count_map: dict[int, int],
        question_type_count_map: dict[int, dict[str, int]] | None = None,
    ) -> None:
        """递归回填章节树题量和题型题量"""
        for node in nodes:
            direct_count = count_map.get(node['id'], 0)
            type_counts = dict((question_type_count_map or {}).get(node['id'], {}))
            if node.get('children'):
                BankService._patch_tree_count(node['children'], count_map, question_type_count_map)
                direct_count += sum(child.get('q_count_cache', 0) for child in node['children'])
                for child in node['children']:
                    BankService._merge_question_type_counts(type_counts, child.get('question_type_counts') or {})
            node['q_count_cache'] = direct_count
            node['question_type_counts'] = type_counts

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
            raise errors.NotFoundError(msg='题库不存在')

        source_bank_id = BankService._resolve_chapter_source_bank_id(bank)
        chapter_list = await chapter_dao.get_by_bank(db, source_bank_id)
        chapters = get_tree_data(chapter_list, sort_key='sort_order')

        if chapters:
            chapter_ids = [chapter.id for chapter in chapter_list]
            count_map = await BankService._get_chapter_count_map(
                db,
                bank_id=pk,
                chapter_ids=chapter_ids,
            )
            question_type_count_map = await BankService._get_chapter_question_type_count_map(
                db,
                bank_id=pk,
                chapter_ids=chapter_ids,
            )
            BankService._patch_tree_count(chapters, count_map, question_type_count_map)

        result = GetBankDetailWithChapters.model_validate(bank)
        result.question_type_counts = await BankService._get_bank_question_type_counts(db=db, bank_id=pk)
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
            question_count, answer_count, correct_count = await BankService._get_bank_progress_summary(
                db=db,
                bank_id=bank_id,
                user_id=user_id,
            )
            question_type_counts = await BankService._get_bank_question_type_counts(db=db, bank_id=bank_id)
            question_type_progress = await BankService._get_bank_question_type_progress(
                db=db,
                bank_id=bank_id,
                user_id=user_id,
            )
            return GetBankChapterProgress(
                bank_id=bank_id,
                total_question_count=question_count,
                total_answer_count=answer_count,
                total_correct_count=correct_count,
                question_type_progress=BankService._build_question_type_progress(
                    question_type_counts,
                    question_type_progress,
                ),
            )

        chapter_ids = [chapter.id for chapter in chapter_list]
        q_count_map = await BankService._get_chapter_count_map(db, bank_id=bank_id, chapter_ids=chapter_ids)
        question_type_count_map = await BankService._get_chapter_question_type_count_map(
            db=db,
            bank_id=bank_id,
            chapter_ids=chapter_ids,
        )
        question_type_progress_map = await BankService._get_chapter_question_type_progress_map(
            db=db,
            bank_id=bank_id,
            user_id=user_id,
            chapter_ids=chapter_ids,
        )

        progress_stmt = (
            select(
                QuestionPlacement.chapter_id,
                func.count(PracticeRecord.id),
                func.count(
                    sa.case(
                        (PracticeRecord.is_correct.is_(True), PracticeRecord.id),
                        else_=None,
                    )
                ),
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
                'question_type_counts': dict(question_type_count_map.get(chapter.id, {})),
                'question_type_progress': BankService._build_question_type_progress(
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
            else:
                root_nodes.append(info)

        def sort_tree(nodes: list[dict[str, Any]]) -> None:
            """递归排序章节树"""
            nodes.sort(key=lambda item: item.get('_sort', 0))
            for node in nodes:
                node.pop('_sort', None)
                if node['children']:
                    sort_tree(node['children'])
                    node['question_count'] += sum(child['question_count'] for child in node['children'])
                    node['answer_count'] += sum(child['answer_count'] for child in node['children'])
                    node['correct_count'] += sum(child['correct_count'] for child in node['children'])
                    for child in node['children']:
                        BankService._merge_question_type_counts(
                            node['question_type_counts'],
                            child.get('question_type_counts') or {},
                        )
                        BankService._merge_question_type_progress(
                            node['question_type_progress'],
                            child.get('question_type_progress') or {},
                        )
                    if node['answer_count'] > 0:
                        node['correct_ratio'] = round(node['correct_count'] / node['answer_count'] * 100, 1)

        sort_tree(root_nodes)
        total_question_type_progress: dict[str, dict[str, Any]] = {}
        for node in root_nodes:
            BankService._merge_question_type_progress(
                total_question_type_progress,
                node.get('question_type_progress') or {},
            )

        return GetBankChapterProgress(
            bank_id=bank_id,
            total_question_count=sum(q_count_map.values()),
            total_answer_count=sum(answer_map.values()),
            total_correct_count=sum(correct_map.values()),
            question_type_progress=total_question_type_progress,
            chapters=[ChapterProgressNode(**item) for item in root_nodes],
        )

    @staticmethod
    async def get_progress_summaries(
        *,
        db: AsyncSession,
        bank_ids: list[int],
        user_id: int,
    ) -> list[BankProgressSummary]:
        """
        批量获取题库进度摘要

        :param db: 数据库会话
        :param bank_ids: 题库 ID 列表
        :param user_id: 用户 ID
        :return:
        """
        normalized_bank_ids = list(dict.fromkeys(int(bank_id) for bank_id in bank_ids if int(bank_id) > 0))
        if not normalized_bank_ids:
            return []

        question_count_stmt = (
            select(QuestionPlacement.bank_id, func.count(QuestionPlacement.id))
            .where(
                QuestionPlacement.bank_id.in_(normalized_bank_ids),
                QuestionPlacement.is_active.is_(True),
            )
            .group_by(QuestionPlacement.bank_id)
        )
        question_count_rows = (await db.execute(question_count_stmt)).all()
        question_count_map = {int(bank_id): int(count or 0) for bank_id, count in question_count_rows}

        progress_stmt = (
            select(
                QuestionPlacement.bank_id,
                func.count(PracticeRecord.id),
                func.count(
                    sa.case(
                        (PracticeRecord.is_correct.is_(True), PracticeRecord.id),
                        else_=None,
                    )
                ),
            )
            .join(QuestionPlacement, PracticeRecord.placement_id == QuestionPlacement.id)
            .where(
                PracticeRecord.user_id == user_id,
                QuestionPlacement.bank_id.in_(normalized_bank_ids),
                PracticeRecord.user_answer.isnot(None),
            )
            .group_by(QuestionPlacement.bank_id)
        )
        progress_rows = (await db.execute(progress_stmt)).all()
        answer_map = {int(bank_id): int(answer_count or 0) for bank_id, answer_count, _ in progress_rows}
        correct_map = {int(bank_id): int(correct_count or 0) for bank_id, _, correct_count in progress_rows}

        type_count_stmt = (
            select(QuestionPlacement.bank_id, Question.type, func.count(QuestionPlacement.id))
            .join(Question, Question.id == QuestionPlacement.question_id)
            .where(
                QuestionPlacement.bank_id.in_(normalized_bank_ids),
                QuestionPlacement.is_active.is_(True),
            )
            .group_by(QuestionPlacement.bank_id, Question.type)
        )
        type_count_rows = (await db.execute(type_count_stmt)).all()
        type_count_map: dict[int, dict[str, int]] = {}
        for bank_id, question_type, count in type_count_rows:
            if not question_type:
                continue
            type_count_map.setdefault(int(bank_id), {})[question_type] = int(count or 0)

        type_progress_stmt = (
            select(
                QuestionPlacement.bank_id,
                Question.type,
                func.count(PracticeRecord.id),
                func.count(
                    sa.case(
                        (PracticeRecord.is_correct.is_(True), PracticeRecord.id),
                        else_=None,
                    )
                ),
            )
            .join(QuestionPlacement, PracticeRecord.placement_id == QuestionPlacement.id)
            .join(Question, Question.id == QuestionPlacement.question_id)
            .where(
                PracticeRecord.user_id == user_id,
                QuestionPlacement.bank_id.in_(normalized_bank_ids),
                PracticeRecord.user_answer.isnot(None),
            )
            .group_by(QuestionPlacement.bank_id, Question.type)
        )
        type_progress_rows = (await db.execute(type_progress_stmt)).all()
        type_progress_map: dict[int, dict[str, dict[str, int]]] = {}
        for bank_id, question_type, answer_count, correct_count in type_progress_rows:
            if not question_type:
                continue
            type_progress_map.setdefault(int(bank_id), {})[question_type] = {
                'answer_count': int(answer_count or 0),
                'correct_count': int(correct_count or 0),
            }

        result: list[BankProgressSummary] = []
        for bank_id in normalized_bank_ids:
            answer_count = answer_map.get(bank_id, 0)
            correct_count = correct_map.get(bank_id, 0)
            result.append(BankProgressSummary(
                bank_id=bank_id,
                question_count=question_count_map.get(bank_id, 0),
                answer_count=answer_count,
                correct_count=correct_count,
                correct_ratio=round(correct_count / answer_count * 100, 1) if answer_count > 0 else 0,
                question_type_progress=BankService._build_question_type_progress(
                    type_count_map.get(bank_id, {}),
                    type_progress_map.get(bank_id, {}),
                ),
            ))

        return result

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
            raise errors.ConflictError(msg='题库编码已存在')

        category = await category_dao.get(db, obj.cat_id)
        if not category:
            raise errors.NotFoundError(msg='所属分类不存在')

        await BankService._validate_parent_bank(db=db, parent_id=obj.parent_id)

        if obj.chapter_source_bank_id is not None:
            await BankService._validate_chapter_source_bank(db=db, source_bank_id=obj.chapter_source_bank_id)

        await BankService._validate_access_entitlement_code(
            db=db,
            access_entitlement_code=obj.access_entitlement_code,
        )

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

        await BankService._validate_access_entitlement_code(
            db=db,
            access_entitlement_code=obj.access_entitlement_code,
        )

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
