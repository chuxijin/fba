#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import hashlib
from collections.abc import Sequence
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy import select, update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.question_bank.model import (
    OptionContent,
    Question,
    QuestionAnalysis,
    QuestionOption,
    QuestionOptionStats,
    QuestionPlacement,
    QuestionStatistics,
)
from backend.app.question_bank.model.bank import QuestionBank
from backend.app.question_bank.model.question import QuestionMaterial
from backend.app.question_bank.schema.question import (
    QuestionCoreBase,
    UpdateQuestionStatisticsParam,
    UpsertQuestionAnalysisItem,
    UpsertQuestionOptionItem,
    UpsertQuestionPlacementItem,
)
from backend.common.enums import DataBaseType
from backend.core.conf import settings


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
                selectinload(Question.options).joinedload(QuestionOption.content_ref),
            )
        )
        result = await db.execute(stmt)
        question = result.unique().scalars().first()
        if question and question.analyses:
            setattr(question, 'analysis', question.analyses[0])
        return question

    async def get_by_ids(
        self, db: AsyncSession, ids: list[int], include_analysis: bool = False
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
            selectinload(Question.options).joinedload(QuestionOption.content_ref),
        ]

        if include_analysis:
            options_list.append(selectinload(Question.analyses))

        stmt = select(Question).where(Question.id.in_(ids)).options(*options_list)

        result = await db.execute(stmt)
        questions_map = {q.id: q for q in result.unique().scalars().all()}
        return [questions_map[qid] for qid in ids if qid in questions_map]

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
        :return:
        """
        stmt = select(Question).options(
            selectinload(Question.placements).joinedload(QuestionPlacement.bank),
            selectinload(Question.placements).joinedload(QuestionPlacement.chapter),
            selectinload(Question.options).joinedload(QuestionOption.content_ref),
        )

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
        查询所有题目

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
        options_list = [
            selectinload(Question.placements).joinedload(QuestionPlacement.bank),
            selectinload(Question.placements).joinedload(QuestionPlacement.chapter),
            selectinload(Question.options).joinedload(QuestionOption.content_ref),
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


# ============ Option CRUD ============


class CRUDOptionContent(CRUDPlus[OptionContent]):
    """Option content dao"""

    @staticmethod
    def _normalize_content(content: str) -> str:
        """规范化选项内容"""
        return content.replace('\r\n', '\n').strip()

    @staticmethod
    def _build_content_hash(content: str) -> str:
        """构建选项内容哈希"""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()

    async def get_by_hash(self, db: AsyncSession, *, content_hash: str) -> OptionContent | None:
        """
        根据哈希获取选项内容

        :param db: 数据库会话
        :param content_hash: 内容哈希
        :return:
        """
        stmt = select(OptionContent).where(OptionContent.content_hash == content_hash)
        result = await db.execute(stmt)
        return result.scalars().first()

    async def get_or_create_by_content(self, db: AsyncSession, *, content: str) -> OptionContent:
        """
        根据内容获取或创建选项

        :param db: 数据库会话
        :param content: 选项内容
        :return:
        """
        normalized_content = self._normalize_content(content)
        content_hash = self._build_content_hash(normalized_content)

        existing = await self.get_by_hash(db, content_hash=content_hash)
        if existing:
            return existing

        option_content = OptionContent(content_hash=content_hash, content=normalized_content)
        db.add(option_content)
        await db.flush()
        return option_content


class CRUDQuestionOption(CRUDPlus[QuestionOption]):
    """Question option dao"""

    async def list_by_question(self, db: AsyncSession, *, question_id: int) -> Sequence[QuestionOption]:
        """
        查询题目的所有选项

        :param db: 数据库会话
        :param question_id: 题目 ID
        :return:
        """
        stmt = (
            select(QuestionOption)
            .where(QuestionOption.question_id == question_id)
            .options(joinedload(QuestionOption.content_ref))
            .order_by(QuestionOption.sort_order.asc(), QuestionOption.option_code.asc())
        )
        result = await db.execute(stmt)
        return result.scalars().all()

    async def replace_by_items(
        self,
        db: AsyncSession,
        *,
        question_id: int,
        items: list[UpsertQuestionOptionItem],
        option_content_crud: CRUDOptionContent,
    ) -> Sequence[QuestionOption]:
        """
        根据标准化选项列表替换题目选项

        :param db: 数据库会话
        :param question_id: 题目 ID
        :param items: 选项列表
        :param option_content_crud: 选项内容 dao
        :return:
        """
        existing_options = await self.list_by_question(db, question_id=question_id)
        existing_map: dict[str, QuestionOption] = {item.option_code: item for item in existing_options}

        incoming_codes: set[str] = set()
        for item in items:
            code = item.option_code.strip().upper()
            incoming_codes.add(code)

            content_ref = await option_content_crud.get_or_create_by_content(db, content=item.content)
            current = existing_map.get(code)
            if current:
                current.content_id = content_ref.id
                current.sort_order = item.sort_order
                current.is_active = item.is_active
            else:
                db.add(
                    QuestionOption(
                        question_id=question_id,
                        option_code=code,
                        content_id=content_ref.id,
                        sort_order=item.sort_order,
                        is_active=item.is_active,
                    )
                )

        for option_code, current in existing_map.items():
            if option_code not in incoming_codes:
                current.is_active = False

        await db.flush()
        return await self.list_by_question(db, question_id=question_id)


class CRUDQuestionOptionStats(CRUDPlus[QuestionOptionStats]):
    """Question option stats dao"""

    async def increment_by_codes(
        self,
        db: AsyncSession,
        *,
        placement_id: int,
        question_id: int,
        option_codes: list[str],
        is_correct: bool,
    ) -> None:
        """
        根据选中的选项编码增加统计

        :param db: 数据库会话
        :param placement_id: 挂载 ID
        :param question_id: 题目 ID
        :param option_codes: 选中的选项编码
        :param is_correct: 本次答题是否正确
        """
        normalized_codes = sorted({str(code).strip().upper() for code in option_codes if str(code).strip()})
        if not normalized_codes:
            return

        option_stmt = select(QuestionOption).where(
            QuestionOption.question_id == question_id,
            QuestionOption.option_code.in_(normalized_codes),
        )
        option_result = await db.execute(option_stmt)
        option_rows = option_result.scalars().all()
        option_map = {item.option_code: item for item in option_rows}
        if not option_map:
            return

        valid_codes = list(option_map.keys())
        stats_stmt = select(QuestionOptionStats).where(
            QuestionOptionStats.placement_id == placement_id,
            QuestionOptionStats.option_code.in_(valid_codes),
        )
        stats_result = await db.execute(stats_stmt)
        stats_rows = stats_result.scalars().all()
        stats_map = {item.option_code: item for item in stats_rows}

        for option_code in valid_codes:
            option_row = option_map[option_code]
            stats_row = stats_map.get(option_code)

            if stats_row:
                stats_row.option_id = option_row.id
                stats_row.selected_count += 1
                if is_correct:
                    stats_row.correct_selected_count += 1
                else:
                    stats_row.wrong_selected_count += 1
                continue

            db.add(
                QuestionOptionStats(
                    placement_id=placement_id,
                    question_id=question_id,
                    option_id=option_row.id,
                    option_code=option_code,
                    selected_count=1,
                    correct_selected_count=1 if is_correct else 0,
                    wrong_selected_count=0 if is_correct else 1,
                )
            )

        await db.flush()


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
        stmt = (
            select(QuestionAnalysis)
            .where(QuestionAnalysis.question_id == question_id, QuestionAnalysis.is_default.is_(True))
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

    async def update_stats(
        self, db: AsyncSession, question_id: int, obj: UpdateQuestionStatisticsParam
    ) -> None:
        """
        更新题目统计（全原子操作，避免并发丢计数）

        :param db: 数据库会话
        :param question_id: 题目 ID
        :param obj: 更新统计参数
        """
        stats = await self.get_or_create(db, question_id)

        # 原子自增：直接使用 SQL 表达式
        values: dict = {}

        if obj.attempt_count is not None:
            values['attempt_count'] = QuestionStatistics.attempt_count + obj.attempt_count
        if obj.correct_count is not None:
            values['correct_count'] = QuestionStatistics.correct_count + obj.correct_count
        if obj.collect_delta is not None:
            values['collect_count'] = QuestionStatistics.collect_count + obj.collect_delta
        if obj.note_delta is not None:
            values['note_count'] = QuestionStatistics.note_count + obj.note_delta
        if hasattr(obj, 'report_delta') and obj.report_delta is not None:
            values['report_count'] = QuestionStatistics.report_count + obj.report_delta

        # 原子平均答题时间：CASE WHEN avg IS NULL THEN new ELSE (avg * (cnt-1) + new) / cnt
        if obj.answer_time is not None:
            new_attempt = values.get('attempt_count', QuestionStatistics.attempt_count)
            values['avg_answer_time'] = sa.case(
                (QuestionStatistics.avg_answer_time.is_(None), obj.answer_time),
                else_=(
                    (QuestionStatistics.avg_answer_time * (new_attempt - 1) + obj.answer_time)
                    / new_attempt
                ),
            )

        # 原子错误选项统计：使用 JSON 函数就地更新避免读-改-写
        if obj.wrong_option is not None:
            option_key = obj.wrong_option
            if DataBaseType.postgresql == settings.DATABASE_TYPE:
                # PG: jsonb_set(COALESCE(col,'{}'), '{key}', (COALESCE((col->key)::int, 0) + 1)::text::jsonb)
                values['wrong_option_stats'] = sa.func.jsonb_set(
                    sa.func.coalesce(QuestionStatistics.wrong_option_stats, sa.text("'{}'::jsonb")),
                    sa.text(f"'{{{option_key}}}'"),
                    sa.type_coerce(
                        sa.cast(
                            sa.func.coalesce(
                                sa.cast(QuestionStatistics.wrong_option_stats[option_key].as_string(), sa.Integer),
                                0,
                            ) + 1,
                            sa.Text,
                        ),
                        sa.JSON,
                    ),
                )
            else:
                # MySQL: JSON_SET(COALESCE(col,'{}'), '$.key', COALESCE(JSON_EXTRACT(col,'$.key'),0)+1)
                values['wrong_option_stats'] = sa.func.json_set(
                    sa.func.coalesce(QuestionStatistics.wrong_option_stats, sa.text("'{}'")),
                    sa.text(f"'$.{option_key}'"),
                    sa.func.coalesce(
                        sa.func.json_extract(QuestionStatistics.wrong_option_stats, sa.text(f"'$.{option_key}'")),
                        0,
                    ) + 1,
                )

        if values:
            stmt = (
                sa_update(QuestionStatistics)
                .where(QuestionStatistics.id == stats.id)
                .values(**values)
            )
            await db.execute(stmt)
            # 刷新实例以获取最新计数
            await db.refresh(stats)

        # 重新计算正确率（需要最新值）
        if obj.attempt_count is not None or obj.correct_count is not None:
            if stats.attempt_count > 0:
                new_rate = Decimal((stats.correct_count / stats.attempt_count) * 100).quantize(Decimal('0.01'))
                stmt_rate = (
                    sa_update(QuestionStatistics)
                    .where(QuestionStatistics.id == stats.id)
                    .values(correct_rate=new_rate)
                )
                await db.execute(stmt_rate)


# ============ 导出实例 ============

question_dao: CRUDQuestion = CRUDQuestion(Question)
option_content_dao: CRUDOptionContent = CRUDOptionContent(OptionContent)
question_option_dao: CRUDQuestionOption = CRUDQuestionOption(QuestionOption)
question_option_stats_dao: CRUDQuestionOptionStats = CRUDQuestionOptionStats(QuestionOptionStats)
question_placement_dao: CRUDQuestionPlacement = CRUDQuestionPlacement(QuestionPlacement)
question_analysis_dao: CRUDQuestionAnalysis = CRUDQuestionAnalysis(QuestionAnalysis)
question_statistics_dao: CRUDQuestionStatistics = CRUDQuestionStatistics(QuestionStatistics)
