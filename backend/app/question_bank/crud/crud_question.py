#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import logging
import math

from collections.abc import Sequence
from decimal import Decimal
from typing import Any

import sqlalchemy as sa

from sqlalchemy import bindparam, func, select
from sqlalchemy import update as sa_update
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.question_bank.model.practice import SessionQuestion

logger = logging.getLogger(__name__)

from backend.app.question_bank.model import (
    Question,
    QuestionAnalysis,
    QuestionPlacement,
    QuestionStatistics,
)
from backend.app.question_bank.model.bank import QuestionBank
from backend.app.question_bank.model.question import QuestionMaterial, question_material_relation
from backend.app.question_bank.schema.question import (
    QuestionCoreBase,
    UpdateQuestionStatisticsParam,
    UpsertQuestionAnalysisItem,
    UpsertQuestionPlacementItem,
)
from backend.common.enums import DataBaseType
from backend.core.conf import settings
from backend.utils.timezone import timezone

# ============ 难度计算常量与算法 ============

MIN_VALID_ATTEMPTS = 50
INVALID_TIME_THRESHOLD = Decimal('3')
SIGMOID_K = 8.0


def compute_difficulty(
    valid_attempts: int,
    valid_correct: int,
    valid_avg_time: Decimal | None,
    median_time: Decimal | None,
) -> Decimal | None:
    """
    基于正确率 + 时间压力计算难度 (1.0-5.0)

    :param valid_attempts: 有效答题次数
    :param valid_correct: 有效答对次数
    :param valid_avg_time: 有效平均答题时间
    :param median_time: 该题有效答题时间中位数（自适应基准）
    :return: 难度值或 None（数据不足时）
    """
    if valid_attempts < MIN_VALID_ATTEMPTS:
        return None

    p = valid_correct / valid_attempts
    base = 1.0 + 4.0 / (1.0 + math.exp(-SIGMOID_K * (0.5 - p)))

    if median_time and median_time > 0 and valid_avg_time and valid_avg_time > 0:
        tf = float(max(Decimal('0.5'), min(Decimal('2.0'), valid_avg_time / median_time)))
    else:
        tf = 1.0

    result = base * (0.7 + 0.3 * tf)
    return Decimal(str(round(max(1.0, min(5.0, result)), 1)))


# ============ Question CRUD ============


class CRUDQuestion(CRUDPlus[Question]):
    """Question dao"""

    async def get(self, db: AsyncSession, question_id: int) -> Question | None:
        """
        获取题目详情

        :param db: 数据库会话
        :param question_id: 题目 ID
        :return:
        """
        return await self.select_model(db, question_id)

    async def get_with_relations(self, db: AsyncSession, question_id: int) -> Question | None:
        """
        获取题目详情（含关联数据）

        :param db: 数据库会话
        :param question_id: 题目 ID
        :return:
        """
        stmt = (
            select(Question)
            .where(Question.id == question_id)
            .options(
                selectinload(Question.analyses),
                selectinload(Question.materials),
                selectinload(Question.placements).joinedload(QuestionPlacement.bank),
                selectinload(Question.placements).joinedload(QuestionPlacement.chapter),
            )
        )
        result = await db.execute(stmt)
        question = result.unique().scalars().first()
        if question and question.analyses:
            setattr(question, 'analysis', question.analyses[0])
        return question

    async def get_by_ids(
        self, db: AsyncSession, ids: list[int], include_analysis: bool = False, include_materials: bool = False
    ) -> Sequence[Question]:
        """
        批量查询题目并保持原始顺序

        :param db: 数据库会话
        :param ids: 题目 ID 列表
        :param include_analysis: 是否加载解析
        :return:
        """
        if not ids:
            return []

        options_list = [
            selectinload(Question.placements).joinedload(QuestionPlacement.bank),
            selectinload(Question.placements).joinedload(QuestionPlacement.chapter),
        ]

        if include_analysis:
            options_list.append(selectinload(Question.analyses))
        if include_materials:
            options_list.append(selectinload(Question.materials))

        stmt = select(Question).where(Question.id.in_(ids)).options(*options_list)

        result = await db.execute(stmt)
        questions_map = {q.id: q for q in result.unique().scalars().all()}
        return [questions_map[qid] for qid in ids if qid in questions_map]

    async def get_by_material_id(self, db: AsyncSession, material_id: int) -> Sequence[Question]:
        """
        获取材料关联题目

        :param db: 数据库会话
        :param material_id: 材料 ID
        :return:
        """
        stmt = (
            select(Question)
            .join(question_material_relation, question_material_relation.c.question_id == Question.id)
            .where(question_material_relation.c.material_id == material_id)
            .order_by(question_material_relation.c.sort_order.asc(), Question.id.asc())
        )
        result = await db.execute(stmt)
        return result.scalars().all()

    async def get_select(
        self,
        bank_id: int | None = None,
        chapter_id: int | None = None,
        type: str | None = None,
        difficulty: str | None = None,
        content_status: int | None = None,
        is_active: bool | None = None,
        review_status: int | None = None,
        scene_mask: int | None = None,
        keyword: str | None = None,
        include_analysis: bool = False,
        include_materials: bool = False,
    ):
        """
        构建题目查询语句

        :param bank_id: 题库 ID（通过挂载筛选）
        :param chapter_id: 章节 ID（通过挂载筛选）
        :param type: 题型
        :param difficulty: 难度
        :param content_status: 内容状态
        :param is_active: 是否启用（挂载级别）
        :param review_status: 审核状态（挂载级别）
        :param scene_mask: 场景位标记（位与过滤）
        :param keyword: 题干关键字
        :param include_analysis: 是否包含解析
        :param include_materials: 是否包含材料
        :return:
        """
        options_list = [
            selectinload(Question.placements).joinedload(QuestionPlacement.bank),
            selectinload(Question.placements).joinedload(QuestionPlacement.chapter),
        ]

        if include_analysis:
            options_list.append(selectinload(Question.analyses))
        if include_materials:
            options_list.append(selectinload(Question.materials))

        stmt = select(Question).options(*options_list)

        has_placement_filter = (
            bank_id is not None
            or chapter_id is not None
            or is_active is not None
            or review_status is not None
            or scene_mask is not None
        )
        if has_placement_filter:
            stmt = stmt.join(QuestionPlacement, QuestionPlacement.question_id == Question.id)

        if bank_id is not None:
            stmt = stmt.where(QuestionPlacement.bank_id == bank_id)
        if chapter_id is not None:
            stmt = stmt.where(QuestionPlacement.chapter_id == chapter_id)
        if is_active is not None:
            stmt = stmt.where(QuestionPlacement.is_active == is_active)
        if review_status is not None:
            stmt = stmt.where(QuestionPlacement.review_status == review_status)
        if scene_mask is not None:
            # 位与过滤：COALESCE(placement.scene_mask, bank.scene_mask) 包含请求的 bits
            stmt = stmt.join(QuestionBank, QuestionBank.id == QuestionPlacement.bank_id)
            effective_scene = sa.func.coalesce(QuestionPlacement.scene_mask, QuestionBank.scene_mask)
            stmt = stmt.where(effective_scene.op('&')(scene_mask) == scene_mask)
        if type is not None:
            stmt = stmt.where(Question.type == type)
        if difficulty is not None:
            stmt = stmt.where(Question.difficulty == difficulty)
        if content_status is not None:
            stmt = stmt.where(Question.content_status == content_status)
        if keyword is not None:
            stmt = stmt.where(Question.stem.like(f'%{keyword}%'))

        if has_placement_filter:
            stmt = stmt.order_by(QuestionPlacement.sort_order.asc(), Question.created_time.desc())
        else:
            stmt = stmt.order_by(Question.created_time.desc())

        return stmt

    async def get_all(
        self,
        db: AsyncSession,
        bank_id: int | None = None,
        chapter_id: int | None = None,
        type: str | None = None,
        difficulty: str | None = None,
        content_status: int | None = None,
        is_active: bool | None = None,
        review_status: int | None = None,
        scene_mask: int | None = None,
        keyword: str | None = None,
        include_analysis: bool = False,
        include_materials: bool = False,
    ) -> Sequence[Question]:
        """
        查询所有题目（复用 get_select 构建查询语句）

        :param db: 数据库会话
        :param bank_id: 题库 ID
        :param chapter_id: 章节 ID
        :param type: 题型
        :param difficulty: 难度
        :param content_status: 内容状态
        :param is_active: 是否启用（挂载级别）
        :param review_status: 审核状态（挂载级别）
        :param scene_mask: 场景位标记（位与过滤）
        :param keyword: 题干关键字
        :param include_analysis: 是否包含解析
        :param include_materials: 是否包含材料
        :return:
        """
        stmt = await self.get_select(
            bank_id=bank_id,
            chapter_id=chapter_id,
            type=type,
            difficulty=difficulty,
            content_status=content_status,
            is_active=is_active,
            review_status=review_status,
            scene_mask=scene_mask,
            keyword=keyword,
            include_analysis=include_analysis,
            include_materials=include_materials,
        )

        result = await db.execute(stmt)
        questions = result.unique().scalars().all()

        if include_analysis:
            for q in questions:
                if q.analyses:
                    setattr(q, 'analysis', q.analyses[0])

        return questions

    async def create(self, db: AsyncSession, core: QuestionCoreBase, user_id: int) -> Question:
        """
        创建题目（仅主表字段）

        :param db: 数据库会话
        :param core: 题目本体参数
        :param user_id: 用户 ID
        :return:
        """
        question = Question(
            type=core.type,
            stem=core.stem,
            difficulty=core.difficulty,
            default_score=core.default_score,
            knowledge_point=core.knowledge_point,
            content_status=core.content_status,
            created_by=user_id,
        )
        db.add(question)
        await db.flush()
        return question

    async def update(self, db: AsyncSession, question_id: int, core: QuestionCoreBase, user_id: int) -> int:
        """
        更新题目（仅主表字段）

        :param db: 数据库会话
        :param question_id: 题目 ID
        :param core: 题目本体参数
        :param user_id: 用户 ID
        :return:
        """
        update_dict: dict = {
            'type': core.type,
            'stem': core.stem,
            'difficulty': core.difficulty,
            'default_score': core.default_score,
            'knowledge_point': core.knowledge_point,
            'content_status': core.content_status,
            'updated_by': user_id,
        }
        return await self.update_model(db, question_id, update_dict)

    async def set_material_ids(self, db: AsyncSession, question_id: int, material_ids: list[int]) -> None:
        """
        全量替换题目的材料关联

        :param db: 数据库会话
        :param question_id: 题目 ID
        :param material_ids: 材料 ID 列表
        """
        question = await self.get(db, question_id)
        if not question:
            return

        if material_ids:
            stmt = select(QuestionMaterial).where(QuestionMaterial.id.in_(material_ids))
            result = await db.execute(stmt)
            materials = list(result.scalars().all())
        else:
            materials = []

        question.materials = materials
        await db.flush()

    async def delete(self, db: AsyncSession, question_ids: list[int]) -> int:
        """
        批量删除题目

        :param db: 数据库会话
        :param question_ids: 题目 ID 列表
        :return:
        """
        return await self.delete_model_by_column(db, allow_multiple=True, id__in=question_ids)


class CRUDQuestionPlacement(CRUDPlus[QuestionPlacement]):
    """Question placement dao"""

    async def get_by_question_and_bank(
        self, db: AsyncSession, *, question_id: int, bank_id: int
    ) -> QuestionPlacement | None:
        """
        根据题目和题库获取挂载记录

        :param db: 数据库会话
        :param question_id: 题目 ID
        :param bank_id: 题库 ID
        :return:
        """
        stmt = select(QuestionPlacement).where(
            QuestionPlacement.question_id == question_id,
            QuestionPlacement.bank_id == bank_id,
        )
        result = await db.execute(stmt)
        return result.scalars().first()

    async def list_by_question_ids(
        self,
        db: AsyncSession,
        *,
        question_ids: list[int],
        bank_id: int | None = None,
        chapter_id: int | None = None,
    ) -> Sequence[QuestionPlacement]:
        """
        批量查询挂载记录

        :param db: 数据库会话
        :param question_ids: 题目 ID 列表
        :param bank_id: 题库 ID
        :param chapter_id: 章节 ID
        :return:
        """
        if not question_ids:
            return []

        stmt = select(QuestionPlacement).where(QuestionPlacement.question_id.in_(question_ids))
        if bank_id is not None:
            stmt = stmt.where(QuestionPlacement.bank_id == bank_id)
        if chapter_id is not None:
            stmt = stmt.where(QuestionPlacement.chapter_id == chapter_id)

        result = await db.execute(stmt)
        return result.scalars().all()

    async def upsert(
        self,
        db: AsyncSession,
        *,
        question_id: int,
        bank_id: int,
        chapter_id: int | None,
        sort_order: int,
        is_active: bool,
        score: Decimal | None,
        review_status: int,
        scene_mask: int | None,
        user_id: int,
    ) -> QuestionPlacement:
        """
        创建或更新挂载记录

        :param db: 数据库会话
        :param question_id: 题目 ID
        :param bank_id: 题库 ID
        :param chapter_id: 章节 ID
        :param sort_order: 排序
        :param is_active: 是否启用
        :param score: 挂载分值
        :param review_status: 审核状态
        :param scene_mask: 场景位标记
        :param user_id: 用户 ID
        :return:
        """
        placement = await self.get_by_question_and_bank(db, question_id=question_id, bank_id=bank_id)
        if placement:
            placement.chapter_id = chapter_id
            placement.sort_order = sort_order
            placement.is_active = is_active
            placement.score = score
            placement.review_status = review_status
            placement.scene_mask = scene_mask
            placement.updated_by = user_id
            await db.flush()
            return placement

        placement = QuestionPlacement(
            question_id=question_id,
            bank_id=bank_id,
            chapter_id=chapter_id,
            sort_order=sort_order,
            is_active=is_active,
            score=score,
            review_status=review_status,
            scene_mask=scene_mask,
            created_by=user_id,
        )
        db.add(placement)
        await db.flush()
        return placement

    async def replace_for_question(
        self,
        db: AsyncSession,
        *,
        question_id: int,
        items: list[UpsertQuestionPlacementItem],
        user_id: int,
    ) -> list[QuestionPlacement]:
        """
        全量替换题目的挂载列表（删除未提交项）

        :param db: 数据库会话
        :param question_id: 题目 ID
        :param items: 挂载列表
        :param user_id: 用户 ID
        :return:
        """
        # 拿到当前所有挂载
        stmt = select(QuestionPlacement).where(QuestionPlacement.question_id == question_id)
        result = await db.execute(stmt)
        existing_map: dict[int, QuestionPlacement] = {p.bank_id: p for p in result.scalars().all()}

        incoming_bank_ids: set[int] = set()
        kept: list[QuestionPlacement] = []

        for item in items:
            incoming_bank_ids.add(item.bank_id)
            placement = await self.upsert(
                db,
                question_id=question_id,
                bank_id=item.bank_id,
                chapter_id=item.chapter_id,
                sort_order=item.sort_order,
                is_active=item.is_active,
                score=item.score,
                review_status=item.review_status,
                scene_mask=item.scene_mask,
                user_id=user_id,
            )
            kept.append(placement)

        # 删除不在提交列表中的旧挂载
        for bank_id, old_placement in existing_map.items():
            if bank_id not in incoming_bank_ids:
                await db.delete(old_placement)

        await db.flush()
        return kept


# ============ Analysis CRUD ============


class CRUDQuestionAnalysis(CRUDPlus[QuestionAnalysis]):
    """题目解析 dao（多版本）"""

    async def get_by_question_id(self, db: AsyncSession, question_id: int) -> QuestionAnalysis | None:
        """
        根据题目 ID 获取默认解析

        :param db: 数据库会话
        :param question_id: 题目 ID
        :return:
        """
        stmt = select(QuestionAnalysis).where(
            QuestionAnalysis.question_id == question_id, QuestionAnalysis.is_default.is_(True)
        )
        result = await db.execute(stmt)
        row = result.scalars().first()
        if row:
            return row

        # 降级：无默认则取第一条
        stmt_fallback = (
            select(QuestionAnalysis)
            .where(QuestionAnalysis.question_id == question_id)
            .order_by(QuestionAnalysis.id.asc())
            .limit(1)
        )
        result_fallback = await db.execute(stmt_fallback)
        return result_fallback.scalars().first()

    async def list_by_question(self, db: AsyncSession, question_id: int) -> Sequence[QuestionAnalysis]:
        """
        获取题目的所有解析版本

        :param db: 数据库会话
        :param question_id: 题目 ID
        :return:
        """
        stmt = (
            select(QuestionAnalysis)
            .where(QuestionAnalysis.question_id == question_id)
            .order_by(QuestionAnalysis.is_default.desc(), QuestionAnalysis.id.asc())
        )
        result = await db.execute(stmt)
        return result.scalars().all()

    async def upsert_version(
        self,
        db: AsyncSession,
        *,
        question_id: int,
        type: str,
        version_no: int,
        is_default: bool,
        answer_data: dict,
        content: str,
        status: int,
        user_id: int,
    ) -> QuestionAnalysis:
        """
        创建或更新解析版本（按 question_id + type + version_no 唯一）

        :param db: 数据库会话
        :param question_id: 题目 ID
        :param type: 解析类型
        :param version_no: 版本号
        :param is_default: 是否默认展示
        :param answer_data: 答案数据
        :param content: 解析内容
        :param status: 状态
        :param user_id: 用户 ID
        :return:
        """
        stmt = select(QuestionAnalysis).where(
            QuestionAnalysis.question_id == question_id,
            QuestionAnalysis.type == type,
            QuestionAnalysis.version_no == version_no,
        )
        result = await db.execute(stmt)
        existing = result.scalars().first()

        if existing:
            existing.is_default = is_default
            existing.answer_data = answer_data
            existing.content = content
            existing.status = status
            existing.updated_by = user_id
            await db.flush()
            return existing

        analysis = QuestionAnalysis(
            question_id=question_id,
            type=type,
            version_no=version_no,
            is_default=is_default,
            answer_data=answer_data,
            content=content,
            status=status,
            created_by=user_id,
        )
        db.add(analysis)
        await db.flush()
        return analysis

    async def set_default(self, db: AsyncSession, analysis_id: int) -> None:
        """
        设置指定解析为默认（同题目其他解析取消默认）

        :param db: 数据库会话
        :param analysis_id: 解析 ID
        """
        analysis = await self.select_model(db, analysis_id)
        if not analysis:
            return

        # 先取消同题目所有默认
        stmt = (
            sa_update(QuestionAnalysis)
            .where(QuestionAnalysis.question_id == analysis.question_id)
            .values(is_default=False)
        )
        await db.execute(stmt)

        # 再设当前为默认
        analysis.is_default = True
        await db.flush()

    async def replace_versions(
        self,
        db: AsyncSession,
        *,
        question_id: int,
        items: list[UpsertQuestionAnalysisItem],
        user_id: int,
    ) -> list[QuestionAnalysis]:
        """
        全量替换题目的解析列表（删除未提交的旧版本）

        :param db: 数据库会话
        :param question_id: 题目 ID
        :param items: 解析列表
        :param user_id: 用户 ID
        :return:
        """
        stmt = select(QuestionAnalysis).where(QuestionAnalysis.question_id == question_id)
        result = await db.execute(stmt)
        existing_map: dict[tuple[str, int], QuestionAnalysis] = {
            (a.type, a.version_no): a for a in result.scalars().all()
        }

        incoming_keys: set[tuple[str, int]] = set()
        kept: list[QuestionAnalysis] = []

        # 确保只有一个 is_default=True
        has_default = any(item.is_default for item in items)

        for idx, item in enumerate(items):
            key = (item.type, item.version_no)
            incoming_keys.add(key)
            # 第一条自动设为默认（如果没有显式指定）
            is_default = item.is_default if has_default else (idx == 0)

            analysis = await self.upsert_version(
                db,
                question_id=question_id,
                type=item.type,
                version_no=item.version_no,
                is_default=is_default,
                answer_data=item.answer_data,
                content=item.content,
                status=item.status,
                user_id=user_id,
            )
            kept.append(analysis)

        # 删除不在提交列表中的旧版本
        for old_key, old_analysis in existing_map.items():
            if old_key not in incoming_keys:
                await db.delete(old_analysis)

        await db.flush()
        return kept

    async def increment_view_count(self, db: AsyncSession, question_id: int) -> None:
        """
        增加默认解析的查看次数（原子更新）

        :param db: 数据库会话
        :param question_id: 题目 ID
        """
        analysis = await self.get_by_question_id(db, question_id)
        if analysis:
            stmt = (
                sa_update(QuestionAnalysis)
                .where(QuestionAnalysis.id == analysis.id)
                .values(view_count=QuestionAnalysis.view_count + 1)
            )
            await db.execute(stmt)

    async def increment_helpful_count(self, db: AsyncSession, question_id: int, is_helpful: bool) -> None:
        """
        增加有帮助/无帮助次数（原子更新）

        :param db: 数据库会话
        :param question_id: 题目 ID
        :param is_helpful: 是否有帮助
        """
        analysis = await self.get_by_question_id(db, question_id)
        if not analysis:
            return

        if is_helpful:
            stmt = (
                sa_update(QuestionAnalysis)
                .where(QuestionAnalysis.id == analysis.id)
                .values(helpful_count=QuestionAnalysis.helpful_count + 1)
            )
        else:
            stmt = (
                sa_update(QuestionAnalysis)
                .where(QuestionAnalysis.id == analysis.id)
                .values(unhelpful_count=QuestionAnalysis.unhelpful_count + 1)
            )
        await db.execute(stmt)


# ============ 题目统计 CRUD ============


class CRUDQuestionStatistics(CRUDPlus[QuestionStatistics]):
    """题目统计 dao"""

    async def get_by_question_id(self, db: AsyncSession, question_id: int) -> QuestionStatistics | None:
        """
        根据题目 ID 获取统计

        :param db: 数据库会话
        :param question_id: 题目 ID
        :return:
        """
        stmt = select(QuestionStatistics).where(QuestionStatistics.question_id == question_id)
        result = await db.execute(stmt)
        return result.scalars().first()

    async def get_or_create(self, db: AsyncSession, question_id: int) -> QuestionStatistics:
        """
        获取或创建统计记录

        :param db: 数据库会话
        :param question_id: 题目 ID
        :return:
        """
        stats = await self.get_by_question_id(db, question_id)
        if not stats:
            stats = QuestionStatistics(question_id=question_id)
            db.add(stats)
            await db.flush()
        return stats

    async def update_stats(self, db: AsyncSession, question_id: int, obj: UpdateQuestionStatisticsParam) -> None:
        """
        更新题目统计（全原子操作，避免并发丢计数）

        :param db: 数据库会话
        :param question_id: 题目 ID
        :param obj: 更新统计参数
        """
        if DataBaseType.postgresql == settings.DATABASE_TYPE:
            current_time = timezone.now()
            insert_stmt = postgresql.insert(QuestionStatistics).values({
                'question_id': question_id,
                'created_time': current_time,
                'last_updated': current_time.replace(tzinfo=None),
            })
            insert_stmt = insert_stmt.on_conflict_do_nothing(index_elements=[QuestionStatistics.question_id])
            await db.execute(insert_stmt)
        else:
            await self.get_or_create(db, question_id)

        values: dict = {}
        attempt_delta = obj.attempt_count or 0
        correct_delta = obj.correct_count or 0

        if obj.attempt_count is not None:
            values['attempt_count'] = QuestionStatistics.attempt_count + attempt_delta
        if obj.correct_count is not None:
            values['correct_count'] = QuestionStatistics.correct_count + correct_delta
        if obj.collect_delta is not None:
            values['collect_count'] = QuestionStatistics.collect_count + obj.collect_delta
        if obj.note_delta is not None:
            values['note_count'] = QuestionStatistics.note_count + obj.note_delta
        if hasattr(obj, 'report_delta') and obj.report_delta is not None:
            values['report_count'] = QuestionStatistics.report_count + obj.report_delta

        if obj.answer_time is not None and attempt_delta > 0:
            new_attempt = QuestionStatistics.attempt_count + attempt_delta
            values['avg_answer_time'] = sa.case(
                (
                    sa.or_(
                        QuestionStatistics.avg_answer_time.is_(None),
                        QuestionStatistics.attempt_count <= 0,
                    ),
                    obj.answer_time,
                ),
                else_=((QuestionStatistics.avg_answer_time * QuestionStatistics.attempt_count) + obj.answer_time)
                / new_attempt,
            )

            # 有效数据追踪（过滤秒杀）
            is_valid = obj.answer_time >= INVALID_TIME_THRESHOLD
            if is_valid:
                values['valid_attempt_count'] = QuestionStatistics.valid_attempt_count + attempt_delta
                if correct_delta > 0:
                    values['valid_correct_count'] = QuestionStatistics.valid_correct_count + correct_delta
                new_valid_attempt = QuestionStatistics.valid_attempt_count + attempt_delta
                values['valid_avg_answer_time'] = sa.case(
                    (
                        sa.or_(
                            QuestionStatistics.valid_avg_answer_time.is_(None),
                            QuestionStatistics.valid_attempt_count <= 0,
                        ),
                        obj.answer_time,
                    ),
                    else_=(
                        (QuestionStatistics.valid_avg_answer_time * QuestionStatistics.valid_attempt_count)
                        + obj.answer_time
                    )
                    / new_valid_attempt,
                )

        if obj.option_select is not None and len(obj.option_select) > 0:
            if DataBaseType.postgresql == settings.DATABASE_TYPE:
                current_stats_expr = QuestionStatistics.option_select_stats
                safe_base = sa.case(
                    (sa.func.jsonb_typeof(current_stats_expr) == 'object', current_stats_expr),
                    else_=sa.cast(sa.literal('{}'), postgresql.JSONB),
                )
                base_val = sa.func.coalesce(safe_base, sa.cast(sa.literal('{}'), postgresql.JSONB))

                for option_key in obj.option_select:
                    current_count = sa.cast(
                        sa.func.coalesce(base_val.op('->>')(option_key), '0'),
                        sa.Integer,
                    )
                    new_count = current_count + 1
                    path = sa.cast(postgresql.array([sa.literal(option_key)]), postgresql.ARRAY(sa.String))
                    new_value = sa.func.to_jsonb(new_count)
                    base_val = sa.func.jsonb_set(base_val, path, new_value, True)

                values['option_select_stats'] = base_val
            else:
                current_stats_expr = QuestionStatistics.option_select_stats
                base_val = sa.func.coalesce(current_stats_expr, sa.text("'{}'"))

                for option_key in obj.option_select:
                    current_count = sa.func.coalesce(
                        sa.func.json_extract(base_val, sa.text(f"'$.{option_key}'")),
                        0,
                    )
                    new_count = current_count + 1
                    base_val = sa.func.json_set(base_val, sa.text(f"'$.{option_key}'"), new_count)
                values['option_select_stats'] = base_val

        if attempt_delta > 0 or correct_delta > 0:
            new_attempt_expr = QuestionStatistics.attempt_count + attempt_delta
            new_correct_expr = QuestionStatistics.correct_count + correct_delta
            values['correct_rate'] = sa.case(
                (
                    new_attempt_expr > 0,
                    sa.cast(
                        sa.func.round(
                            sa.cast(new_correct_expr, sa.Numeric(18, 4))
                            * Decimal('100')
                            / sa.cast(new_attempt_expr, sa.Numeric(18, 4)),
                            2,
                        ),
                        sa.Numeric(5, 2),
                    ),
                ),
                else_=Decimal('0'),
            )

        if not values:
            return

        values['last_updated'] = timezone.now().replace(tzinfo=None)

        stmt = sa_update(QuestionStatistics).where(QuestionStatistics.question_id == question_id).values(**values)
        await db.execute(stmt)

    async def batch_update_stats(self, db: AsyncSession, items: list[dict[str, Any]]) -> None:
        """
        批量更新题目统计

        :param db: 数据库会话
        :param items: 统计增量列表
        :return:
        """
        if not items:
            return

        if DataBaseType.postgresql != settings.DATABASE_TYPE:
            for item in items:
                option_select = list(item.get('option_select') or [])
                option_select_counts = item.get('option_select_counts')
                if isinstance(option_select_counts, dict):
                    for option_key, count in option_select_counts.items():
                        option_select.extend([str(option_key)] * int(count or 0))

                answer_time = item.get('answer_time')
                answer_time_total = item.get('answer_time_total')
                attempt_count = int(item.get('attempt_count') or 0)
                if answer_time is None and answer_time_total is not None and attempt_count > 0:
                    answer_time = Decimal(str(answer_time_total)) / Decimal(attempt_count)

                await self.update_stats(
                    db=db,
                    question_id=int(item['question_id']),
                    obj=UpdateQuestionStatisticsParam(
                        attempt_count=attempt_count or None,
                        correct_count=int(item.get('correct_count') or 0) or None,
                        answer_time=answer_time,
                        option_select=option_select or None,
                        collect_delta=item.get('collect_delta'),
                        note_delta=item.get('note_delta'),
                    ),
                )
            return

        aggregated: dict[int, dict[str, Any]] = {}
        for item in items:
            question_id = int(item['question_id'])
            aggregated_item = aggregated.get(question_id)
            if aggregated_item is None:
                aggregated_item = {
                    'question_id': question_id,
                    'attempt_count': 0,
                    'correct_count': 0,
                    'answer_time_total': Decimal('0'),
                    'collect_delta': 0,
                    'note_delta': 0,
                    'report_delta': 0,
                    'option_select_counts': {},
                    'valid_attempt_count': 0,
                    'valid_correct_count': 0,
                    'valid_answer_time_total': Decimal('0'),
                }
                aggregated[question_id] = aggregated_item

            aggregated_item['attempt_count'] += int(item.get('attempt_count') or 0)
            aggregated_item['correct_count'] += int(item.get('correct_count') or 0)
            aggregated_item['collect_delta'] += int(item.get('collect_delta') or 0)
            aggregated_item['note_delta'] += int(item.get('note_delta') or 0)
            aggregated_item['report_delta'] += int(item.get('report_delta') or 0)

            answer_time_total = item.get('answer_time_total')
            answer_time = item.get('answer_time')
            if answer_time_total is not None:
                aggregated_item['answer_time_total'] += Decimal(str(answer_time_total))
            elif answer_time is not None:
                aggregated_item['answer_time_total'] += Decimal(str(answer_time))

            option_select = item.get('option_select')
            if option_select:
                for option_key in option_select:
                    normalized_key = str(option_key)
                    current_count = aggregated_item['option_select_counts'].get(normalized_key, 0)
                    aggregated_item['option_select_counts'][normalized_key] = current_count + 1

            option_select_counts = item.get('option_select_counts')
            if isinstance(option_select_counts, dict):
                for option_key, count in option_select_counts.items():
                    normalized_key = str(option_key)
                    current_count = aggregated_item['option_select_counts'].get(normalized_key, 0)
                    aggregated_item['option_select_counts'][normalized_key] = current_count + int(count or 0)

            # 有效数据聚合（由调用方过滤 answer_time < 3s）
            valid_attempt = int(item.get('valid_attempt_count') or 0)
            valid_correct = int(item.get('valid_correct_count') or 0)
            aggregated_item['valid_attempt_count'] += valid_attempt
            aggregated_item['valid_correct_count'] += valid_correct

            valid_answer_time_total = item.get('valid_answer_time_total')
            if valid_answer_time_total is not None:
                aggregated_item['valid_answer_time_total'] += Decimal(str(valid_answer_time_total))

        question_ids = list(aggregated.keys())
        insert_time = timezone.now()
        stats_update_time = insert_time.replace(tzinfo=None)
        insert_stmt = postgresql.insert(QuestionStatistics).values([
            {
                'question_id': question_id,
                'created_time': insert_time,
                'last_updated': stats_update_time,
            }
            for question_id in question_ids
        ])
        insert_stmt = insert_stmt.on_conflict_do_nothing(index_elements=[QuestionStatistics.question_id])
        await db.execute(insert_stmt)

        lock_stmt = select(QuestionStatistics).where(QuestionStatistics.question_id.in_(question_ids)).with_for_update()
        rows = (await db.execute(lock_stmt)).scalars().all()
        stats_map = {row.question_id: row for row in rows}
        current_time = timezone.now().replace(tzinfo=None)
        payloads: list[dict[str, Any]] = []

        for question_id, aggregated_item in aggregated.items():
            stats = stats_map.get(question_id)
            if stats is None:
                continue

            current_attempt = int(stats.attempt_count or 0)
            current_correct = int(stats.correct_count or 0)
            current_collect = int(stats.collect_count or 0)
            current_note = int(stats.note_count or 0)
            current_report = int(stats.report_count or 0)

            new_attempt = current_attempt + aggregated_item['attempt_count']
            new_correct = current_correct + aggregated_item['correct_count']
            new_collect = current_collect + aggregated_item['collect_delta']
            new_note = current_note + aggregated_item['note_delta']
            new_report = current_report + aggregated_item['report_delta']

            new_avg_answer_time = stats.avg_answer_time
            if aggregated_item['attempt_count'] > 0:
                if current_attempt <= 0 or stats.avg_answer_time is None:
                    new_avg_answer_time = (
                        aggregated_item['answer_time_total'] / Decimal(aggregated_item['attempt_count'])
                    ).quantize(Decimal('0.01'))
                else:
                    current_avg = Decimal(str(stats.avg_answer_time))
                    total_answer_time = current_avg * Decimal(current_attempt) + aggregated_item['answer_time_total']
                    new_avg_answer_time = (total_answer_time / Decimal(new_attempt)).quantize(Decimal('0.01'))

            current_option_stats = stats.option_select_stats
            if not isinstance(current_option_stats, dict):
                current_option_stats = {}
            new_option_stats = dict(current_option_stats)
            for option_key, count in aggregated_item['option_select_counts'].items():
                current_count = int(new_option_stats.get(option_key, 0) or 0)
                new_option_stats[option_key] = current_count + count

            new_correct_rate = Decimal('0')
            if new_attempt > 0:
                new_correct_rate = (Decimal(new_correct) * Decimal('100') / Decimal(new_attempt)).quantize(
                    Decimal('0.01')
                )

            # 有效统计滚动均值
            current_valid_attempt = int(stats.valid_attempt_count or 0)
            new_valid_attempt = current_valid_attempt + aggregated_item['valid_attempt_count']
            new_valid_correct = int(stats.valid_correct_count or 0) + aggregated_item['valid_correct_count']
            new_valid_avg_answer_time = stats.valid_avg_answer_time

            if aggregated_item['valid_attempt_count'] > 0:
                if current_valid_attempt <= 0 or stats.valid_avg_answer_time is None:
                    new_valid_avg_answer_time = (
                        aggregated_item['valid_answer_time_total'] / Decimal(aggregated_item['valid_attempt_count'])
                    ).quantize(Decimal('0.01'))
                else:
                    current_valid_avg = Decimal(str(stats.valid_avg_answer_time))
                    total_valid_time = (
                        current_valid_avg * Decimal(current_valid_attempt) + aggregated_item['valid_answer_time_total']
                    )
                    new_valid_avg_answer_time = (total_valid_time / Decimal(new_valid_attempt)).quantize(
                        Decimal('0.01')
                    )

            # 中位数 + 难度计算
            median_time = await self.get_median_answer_time(db, question_id)
            computed_difficulty = compute_difficulty(
                valid_attempts=new_valid_attempt,
                valid_correct=new_valid_correct,
                valid_avg_time=new_valid_avg_answer_time,
                median_time=median_time,
            )

            payloads.append({
                'filter_question_id': question_id,
                'set_attempt_count': new_attempt,
                'set_correct_count': new_correct,
                'set_correct_rate': new_correct_rate,
                'set_avg_answer_time': new_avg_answer_time,
                'set_option_select_stats': new_option_stats or None,
                'set_collect_count': new_collect,
                'set_note_count': new_note,
                'set_report_count': new_report,
                'set_last_updated': current_time,
                'set_valid_attempt_count': new_valid_attempt,
                'set_valid_correct_count': new_valid_correct,
                'set_valid_avg_answer_time': new_valid_avg_answer_time,
                'set_computed_difficulty': computed_difficulty,
            })

        if not payloads:
            return

        update_stmt = (
            sa_update(QuestionStatistics.__table__)
            .where(QuestionStatistics.question_id == bindparam('filter_question_id'))
            .values(
                attempt_count=bindparam('set_attempt_count'),
                correct_count=bindparam('set_correct_count'),
                correct_rate=bindparam('set_correct_rate'),
                avg_answer_time=bindparam('set_avg_answer_time'),
                option_select_stats=bindparam('set_option_select_stats', type_=postgresql.JSONB),
                collect_count=bindparam('set_collect_count'),
                note_count=bindparam('set_note_count'),
                report_count=bindparam('set_report_count'),
                last_updated=bindparam('set_last_updated'),
                valid_attempt_count=bindparam('set_valid_attempt_count'),
                valid_correct_count=bindparam('set_valid_correct_count'),
                valid_avg_answer_time=bindparam('set_valid_avg_answer_time'),
            )
            .execution_options(synchronize_session=False)
        )
        await db.execute(update_stmt, payloads)

        # 写回 Question.difficulty
        difficulty_payloads = [
            {'filter_question_id': p['filter_question_id'], 'set_difficulty': p['set_computed_difficulty']}
            for p in payloads
            if p['set_computed_difficulty'] is not None
        ]
        if difficulty_payloads:
            difficulty_stmt = (
                sa_update(Question.__table__)
                .where(Question.id == bindparam('filter_question_id'))
                .values(difficulty=bindparam('set_difficulty'))
                .execution_options(synchronize_session=False)
            )
            await db.execute(difficulty_stmt, difficulty_payloads)

        await db.flush()

    async def get_median_answer_time(self, db: AsyncSession, question_id: int) -> Decimal | None:
        """
        查询该题有效答题时间的中位数

        :param db: 数据库会话
        :param question_id: 题目 ID
        :return: 中位数或 None
        """
        stmt = select(func.percentile_cont(0.5).within_group(SessionQuestion.answer_time)).where(
            SessionQuestion.question_id == question_id,
            SessionQuestion.user_answer.isnot(None),
            SessionQuestion.is_correct.isnot(None),
            SessionQuestion.answer_time >= INVALID_TIME_THRESHOLD,
        )
        result = (await db.execute(stmt)).scalar()
        if result is None:
            return None
        return Decimal(str(result)).quantize(Decimal('0.01'))

    async def update_difficulty(self, db: AsyncSession, question_id: int) -> None:
        """
        重算单题难度并写回 Question.difficulty

        :param db: 数据库会话
        :param question_id: 题目 ID
        """
        stats = await self.get_by_question_id(db, question_id)
        if not stats:
            return

        median_time = await self.get_median_answer_time(db, question_id)
        difficulty = compute_difficulty(
            valid_attempts=int(stats.valid_attempt_count or 0),
            valid_correct=int(stats.valid_correct_count or 0),
            valid_avg_time=stats.valid_avg_answer_time,
            median_time=median_time,
        )

        stmt = sa_update(Question).where(Question.id == question_id).values(difficulty=difficulty)
        await db.execute(stmt)


# ============ 导出实例 ============

question_dao: CRUDQuestion = CRUDQuestion(Question)
question_placement_dao: CRUDQuestionPlacement = CRUDQuestionPlacement(QuestionPlacement)
question_analysis_dao: CRUDQuestionAnalysis = CRUDQuestionAnalysis(QuestionAnalysis)
question_statistics_dao: CRUDQuestionStatistics = CRUDQuestionStatistics(QuestionStatistics)
