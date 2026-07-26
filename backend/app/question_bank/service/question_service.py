#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import hashlib
import json
import logging

from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal
from math import ceil
from typing import Any

from sqlalchemy import String, cast, func, or_, select, update
from sqlalchemy.dialects.postgresql import JSONB as PGJSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.admin.crud.crud_category import category_dao
from backend.app.question_bank.crud.crud_bank import bank_dao
from backend.app.question_bank.crud.crud_chapter import chapter_dao
from backend.app.question_bank.crud.crud_question import (
    question_analysis_dao,
    question_dao,
    question_placement_dao,
    question_statistics_dao,
)
from backend.app.question_bank.model import (
    Question,
    QuestionAnalysis,
    QuestionBank,
    QuestionChapter,
    QuestionPlacement,
    QuestionStatistics,
)
from backend.app.question_bank.schema.question import (
    CreateQuestionParam,
    DeleteQuestionParam,
    UpdateQuestionParam,
    UpdateQuestionStatisticsParam,
    UpsertQuestionOptionItem,
    UpsertQuestionPlacementItem,
)
from backend.app.question_bank.cache.question_cache import collections_cache, solution_content_cache
from backend.app.question_bank.service.knowledge_point_service import knowledge_point_service
from backend.common.exception import errors
from backend.utils.answer_parser import extract_option_codes, split_answer_text
from backend.utils.timezone import timezone

log = logging.getLogger(__name__)


class QuestionService:
    """Question service."""

    @staticmethod
    async def _verify_chapter_in_bank_context(*, db: AsyncSession, bank_id: int, chapter_id: int) -> None:
        """
        校验章节是否属于题库当前章节来源

        :param db: 数据库会话
        :param bank_id: 题库 ID
        :param chapter_id: 章节 ID
        :return:
        """
        bank = await bank_dao.get(db, bank_id)
        if not bank:
            raise errors.NotFoundError(msg=f'题库 ID {bank_id} 不存在')

        chapter = await chapter_dao.get(db, chapter_id)
        if not chapter:
            raise errors.NotFoundError(msg=f'章节 ID {chapter_id} 不存在')

        source_bank_id = bank.chapter_source_bank_id or bank.id
        if chapter.bank_id != source_bank_id:
            raise errors.ForbiddenError(msg=f'章节 ID {chapter_id} 不属于题库 ID {bank_id} 的章节来源')

    # ------------------------------------------------------------------
    #  工具方法
    # ------------------------------------------------------------------

    @staticmethod
    def _pick_placement(
        *, question: Question, bank_id: int | None = None, chapter_id: int | None = None
    ) -> QuestionPlacement | None:
        """
        根据题库/章节上下文选择挂载记录

        :param question: 题目对象
        :param bank_id: 题库 ID
        :param chapter_id: 章节 ID
        :return:
        """
        placements = question.placements or []
        if not placements:
            return None

        active_placements = [item for item in placements if item.is_active]
        candidates = active_placements or placements
        sorted_candidates = sorted(candidates, key=lambda item: (item.sort_order, item.id))

        if chapter_id is not None:
            for placement in sorted_candidates:
                if placement.chapter_id == chapter_id and (bank_id is None or placement.bank_id == bank_id):
                    return placement

        if bank_id is not None:
            for placement in sorted_candidates:
                if placement.bank_id == bank_id:
                    return placement

        return sorted_candidates[0]

    _extract_option_codes = staticmethod(extract_option_codes)
    _split_answer_text = staticmethod(split_answer_text)

    @staticmethod
    def _pick_default_analysis(analyses: Sequence[QuestionAnalysis] | None) -> QuestionAnalysis | None:
        if not analyses:
            return None
        defaults = [item for item in analyses if getattr(item, 'is_default', False)]
        candidates = defaults or list(analyses)
        return min(candidates, key=lambda item: item.id)

    @staticmethod
    def normalize_options(
        options: list[dict[str, Any]] | list[UpsertQuestionOptionItem] | None,
        *,
        active_only: bool = False,
    ) -> list[dict[str, Any]]:
        """
        规范化题目选项

        :param options: 选项列表
        :param active_only: 是否只返回启用选项
        :return:
        """
        normalized_options: list[dict[str, Any]] = []
        for index, item in enumerate(options or []):
            if isinstance(item, UpsertQuestionOptionItem):
                raw_option = item.model_dump()
            elif isinstance(item, dict):
                raw_option = item
            else:
                continue

            option_code = str(raw_option.get('option_code') or raw_option.get('code') or '').strip().upper()
            content = str(raw_option.get('content') or '').strip()
            if not option_code or not content:
                continue

            is_active = raw_option.get('is_active')
            if is_active is None:
                is_active = True
            if active_only and not bool(is_active):
                continue

            sort_order = raw_option.get('sort_order')
            if isinstance(sort_order, bool) or not isinstance(sort_order, int):
                sort_order = index

            normalized_options.append({
                'option_code': option_code,
                'content': content,
                'sort_order': sort_order,
                'is_active': bool(is_active),
            })

        return sorted(normalized_options, key=lambda option: (option['sort_order'], option['option_code']))

    @staticmethod
    def build_options_data(*, question: Question) -> dict | None:
        """从题目 JSONB 选项构建 options_data"""
        sorted_rows = QuestionService.normalize_options(question.options, active_only=True)
        if not sorted_rows:
            return None

        options_data: dict[str, dict[str, str]] = {}
        for row in sorted_rows:
            option_code = row['option_code']
            options_data[option_code] = {
                'code': option_code,
                'content': row['content'],
            }

        return options_data

    @staticmethod
    def build_solution_payload(
        *,
        question: Question,
        analysis: QuestionAnalysis,
        is_correct: bool | None = None,
    ) -> dict[str, Any]:
        """
        基于已加载题目对象构建解析返回数据

        :param question: 题目对象
        :param analysis: 默认解析
        :param is_correct: 是否答对
        :return:
        """
        stats = question.statistics
        answer_data = analysis.answer_data or {}
        return {
            'correct_answer': answer_data.get('correct', ''),
            'analysis': analysis.content or '',
            'is_correct': is_correct,
            'correct_rate': stats.correct_rate if stats else Decimal('0'),
            'option_select_stats': stats.option_select_stats if stats else {},
        }

    @staticmethod
    def build_solution_content_payload(*, analysis: QuestionAnalysis) -> dict[str, Any]:
        """构建可长期缓存的答案解析内容"""
        answer_data = analysis.answer_data or {}
        return {
            'correct_answer': answer_data.get('correct', ''),
            'analysis': analysis.content or '',
        }

    @staticmethod
    def parse_selected_option_codes(*, question_type: str, user_answer: str | list[str]) -> list[str]:
        """从用户答案解析选中的选项编码"""
        if question_type in ['single', 'judgement']:
            codes = QuestionService._extract_option_codes(user_answer)
            return codes[:1]

        if question_type != 'multiple':
            return []

        codes = QuestionService._extract_option_codes(user_answer)
        if not codes:
            return []
        return sorted(set(codes))

    @staticmethod
    def _parse_kp_id(value: Any) -> int | None:
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value if value > 0 else None
        if isinstance(value, str):
            text = value.strip()
            if text.isdigit():
                parsed = int(text)
                return parsed if parsed > 0 else None
            return None
        return None

    @staticmethod
    def _parse_kp_name(value: Any) -> str | None:
        if isinstance(value, str):
            text = value.strip()
            return text or None
        return None

    @classmethod
    def _normalize_knowledge_point_terms(cls, items: list[Any] | None) -> tuple[list[int], list[str]]:
        kp_ids: set[int] = set()
        kp_names: set[str] = set()

        for item in items or []:
            if isinstance(item, dict):
                obj_id = cls._parse_kp_id(item.get('id') or item.get('category_id') or item.get('cat_id'))
                if obj_id is not None:
                    kp_ids.add(obj_id)

                obj_name = cls._parse_kp_name(item.get('name') or item.get('label') or item.get('title'))
                if obj_name:
                    kp_names.add(obj_name)
                continue

            scalar_id = cls._parse_kp_id(item)
            if scalar_id is not None:
                kp_ids.add(scalar_id)
                continue

            scalar_name = cls._parse_kp_name(item)
            if scalar_name:
                kp_names.add(scalar_name)

        return sorted(kp_ids), sorted(kp_names)

    @staticmethod
    def _extract_kp_codes(data: dict[str, Any]) -> list[str]:
        """
        从序列化题目字典中提取知识点编码列表

        :param data: serialize_question 输出的字典
        :return: 知识点编码列表（保持原始顺序，去重）
        """
        raw = data.get('knowledge_point')
        if not raw or not isinstance(raw, list):
            return []
        codes: list[str] = []
        seen: set[str] = set()
        for item in raw:
            if isinstance(item, str) and item.strip():
                code = item.strip()
                if code not in seen:
                    seen.add(code)
                    codes.append(code)
        return codes

    @staticmethod
    async def _fill_kp_display_batch(
        db: AsyncSession,
        items: list[dict[str, Any]],
    ) -> None:
        """
        批量为题目字典列表填充 knowledge_point_display

        :param db: 数据库会话
        :param items: serialize_question 输出的字典列表
        """
        if not items:
            return
        all_codes: set[str] = set()
        for item in items:
            all_codes.update(QuestionService._extract_kp_codes(item))
        if not all_codes:
            return
        code_map = await knowledge_point_service.resolve_codes_to_names(db, list(all_codes))
        for item in items:
            kp_codes = QuestionService._extract_kp_codes(item)
            if kp_codes:
                item['knowledge_point_display'] = [code_map.get(code, code) for code in kp_codes]

    @staticmethod
    def serialize_question(
        *,
        question: Question,
        bank_id: int | None = None,
        chapter_id: int | None = None,
        include_analysis: bool = False,
        include_materials: bool = False,
    ) -> dict[str, Any]:
        """
        序列化题目为响应字典

        :param question: 题目对象
        :param bank_id: 题库 ID
        :param chapter_id: 章节 ID
        :param include_analysis: 是否包含解析
        :param include_materials: 是否包含材料
        :return:
        """
        placement = QuestionService._pick_placement(question=question, bank_id=bank_id, chapter_id=chapter_id)

        # 挂载级别字段
        resolved_bank_id = placement.bank_id if placement else None
        resolved_chapter_id = placement.chapter_id if placement else None
        resolved_sort_order = placement.sort_order if placement else 0
        resolved_is_active = placement.is_active if placement else True
        resolved_score = placement.score if placement else None
        resolved_review_status = placement.review_status if placement else 10

        bank_name = None
        if placement and placement.bank:
            bank_name = placement.bank.name

        chapter_name = None
        if placement and placement.chapter:
            chapter_name = placement.chapter.name

        question_dict: dict[str, Any] = {
            'id': question.id,
            'type': question.type,
            'stem': question.stem,
            'options_data': QuestionService.build_options_data(question=question),
            'difficulty': question.difficulty,
            'default_score': question.default_score,
            'knowledge_point': question.knowledge_point,
            'content_status': question.content_status,
            'created_time': question.created_time,
            'updated_time': question.updated_time,
            # 来自 Placement 的扁平化字段
            'bank_id': resolved_bank_id,
            'chapter_id': resolved_chapter_id,
            'sort_order': resolved_sort_order,
            'is_active': resolved_is_active,
            'score': resolved_score,
            'review_status': resolved_review_status,
            'bank_name': bank_name,
            'chapter_name': chapter_name,
        }

        if include_analysis:
            current_analysis = QuestionService._pick_default_analysis(question.analyses)
            question_dict['answer_data'] = current_analysis.answer_data if current_analysis else None
            question_dict['analysis_content'] = current_analysis.content if current_analysis else None
            question_dict['analyses'] = question.analyses or []

        if include_materials:
            materials = question.materials or []
            question_dict['materials'] = [{'id': m.id, 'content': m.content} for m in materials]
            question_dict['material_ids'] = [m.id for m in materials]

        return question_dict

    # ------------------------------------------------------------------
    #  CRUD
    # ------------------------------------------------------------------

    @staticmethod
    async def get(*, db: AsyncSession, pk: int) -> dict[str, Any]:
        """
        获取题目详情（返回标准化 detail DTO 字典，包含 options/placements/analyses/material_ids）

        :param db: 数据库会话
        :param pk: 题目 ID
        :return:
        """
        question = await question_dao.get_with_relations(db, pk)
        if not question:
            raise errors.NotFoundError(msg='Question not found')

        data = QuestionService.serialize_question(
            question=question,
            include_analysis=False,
            include_materials=True,
        )

        # 解析知识点 code → 显示名称
        kp_codes = QuestionService._extract_kp_codes(data)
        if kp_codes:
            code_map = await knowledge_point_service.resolve_codes_to_names(db, kp_codes)
            data['knowledge_point_display'] = [code_map.get(code, code) for code in kp_codes]

        # 详情接口对齐 GetQuestionDetail schema：补齐 options / placements
        data['options'] = QuestionService.normalize_options(question.options)

        placement_rows = question.placements or []
        sorted_placements = sorted(
            placement_rows,
            key=lambda item: (item.bank_id, item.chapter_id or 0, item.sort_order, item.id),
        )
        data['placements'] = [
            {
                'id': item.id,
                'question_id': item.question_id,
                'bank_id': item.bank_id,
                'chapter_id': item.chapter_id,
                'sort_order': item.sort_order,
                'is_active': item.is_active,
                'score': item.score,
                'review_status': item.review_status,
                'scene_mask': item.scene_mask,
                'bank_name': item.bank.name if item.bank else None,
                'chapter_name': item.chapter.name if item.chapter else None,
            }
            for item in sorted_placements
        ]

        return data

    @staticmethod
    async def get_list(
        *,
        db: AsyncSession,
        ids: list[int] | None = None,
        bank_id: int | None = None,
        chapter_id: int | None = None,
        type: str | None = None,
        difficulty: str | None = None,
        content_status: int | None = None,
        is_active: bool | None = None,
        review_status: int | None = None,
        keyword: str | None = None,
        page: int | None = None,
        size: int | None = None,
        include_analysis: bool = False,
    ) -> Sequence[dict[str, Any]] | dict[str, Any]:
        """
        获取题目列表

        :param db: 数据库会话
        :param ids: 题目 ID 列表
        :param bank_id: 题库 ID
        :param chapter_id: 章节 ID
        :param type: 题型
        :param difficulty: 难度
        :param content_status: 内容状态
        :param is_active: 是否启用（挂载级别）
        :param review_status: 审核状态（挂载级别）
        :param keyword: 题干关键字
        :param page: 页码
        :param size: 每页数量
        :param include_analysis: 是否包含解析
        :return:
        """
        if ids:
            questions = await question_dao.get_by_ids(db, ids, include_analysis=include_analysis)
            items = [
                QuestionService.serialize_question(
                    question=q,
                    bank_id=bank_id,
                    chapter_id=chapter_id,
                    include_analysis=include_analysis,
                    include_materials=False,
                )
                for q in questions
            ]
            await QuestionService._fill_kp_display_batch(db, items)
            return items

        if page is not None and size is not None:
            question_select = await question_dao.get_select(
                bank_id=bank_id,
                chapter_id=chapter_id,
                type=type,
                difficulty=difficulty,
                content_status=content_status,
                is_active=is_active,
                review_status=review_status,
                keyword=keyword,
            )

            count_stmt = select(func.count()).select_from(question_select.subquery())
            total = await db.scalar(count_stmt) or 0

            offset = (page - 1) * size
            stmt = question_select.limit(size).offset(offset)
            result = await db.execute(stmt)
            questions = result.unique().scalars().all()

            questions_dict = [
                QuestionService.serialize_question(
                    question=q,
                    bank_id=bank_id,
                    chapter_id=chapter_id,
                    include_analysis=include_analysis,
                    include_materials=False,
                )
                for q in questions
            ]
            await QuestionService._fill_kp_display_batch(db, questions_dict)

            total_pages = ceil(total / size) if size > 0 else 0
            return {
                'items': questions_dict,
                'total': total,
                'page': page,
                'size': size,
                'total_pages': total_pages,
                'links': {'first': '', 'last': '', 'self': '', 'next': None, 'prev': None},
            }

        questions = await question_dao.get_all(
            db,
            bank_id=bank_id,
            chapter_id=chapter_id,
            type=type,
            difficulty=difficulty,
            content_status=content_status,
            is_active=is_active,
            review_status=review_status,
            keyword=keyword,
            include_analysis=include_analysis,
            include_materials=True,
        )
        items = [
            QuestionService.serialize_question(
                question=q,
                bank_id=bank_id,
                chapter_id=chapter_id,
                include_analysis=include_analysis,
                include_materials=True,
            )
            for q in questions
        ]
        await QuestionService._fill_kp_display_batch(db, items)
        return items

    @staticmethod
    def parse_int_csv(value: str | None) -> list[int]:
        """解析逗号分隔的整数字符串"""
        if not value:
            return []
        result: list[int] = []
        for item in value.split(','):
            token = item.strip()
            if not token or not token.isdigit():
                continue
            parsed = int(token)
            if parsed > 0:
                result.append(parsed)
        return sorted(set(result))

    @staticmethod
    def parse_text_csv(value: str | None) -> list[str]:
        """解析逗号分隔的文本字符串"""
        if not value:
            return []
        values = [item.strip() for item in value.split(',') if item and item.strip()]
        return sorted(set(values))

    @staticmethod
    async def get_dynamic_collections(
        *,
        db: AsyncSession,
        cat_id: int | None = None,
        region: str | None = None,
        knowledge_ids: list[int] | None = None,
        knowledge_names: list[str] | None = None,
        stem_keyword: str | None = None,
        option_keyword: str | None = None,
        analysis_keyword: str | None = None,
        year_start: int | None = None,
        year_end: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        根据筛选条件动态聚合题目合集（按试卷维度聚合），结果缓存 60 秒。

        核心关系：
        Question --(question_id)--> QuestionPlacement --(bank_id)--> QuestionBank
        """
        # 缓存
        cache_payload = {
            'cat_id': cat_id,
            'region': (region or '').strip() or None,
            'knowledge_ids': knowledge_ids,
            'knowledge_names': knowledge_names,
            'stem_keyword': (stem_keyword or '').strip() or None,
            'option_keyword': (option_keyword or '').strip() or None,
            'analysis_keyword': (analysis_keyword or '').strip() or None,
            'year_start': year_start,
            'year_end': year_end,
        }
        cache_hash = hashlib.sha256(
            json.dumps(cache_payload, ensure_ascii=False, sort_keys=True).encode('utf-8')
        ).hexdigest()

        cached = await collections_cache.get(cache_hash)
        if cached is not None:
            return cached

        cat_ids = await category_dao.get_all_children_ids(db, cat_id) if cat_id is not None else None

        stmt = (
            select(
                QuestionBank.id.label('id'),
                QuestionBank.cat_id.label('cat_id'),
                QuestionBank.name.label('name'),
                QuestionBank.code.label('code'),
                QuestionBank.desc.label('desc'),
                QuestionBank.bank_type.label('bank_type'),
                QuestionBank.difficulty.label('difficulty'),
                QuestionBank.parent_id.label('parent_id'),
                QuestionBank.q_count_cache.label('q_count_cache'),
                func.count(func.distinct(Question.id)).label('matched_q_count'),
            )
            .select_from(QuestionPlacement)
            .join(Question, Question.id == QuestionPlacement.question_id)
            .join(QuestionBank, QuestionBank.id == QuestionPlacement.bank_id)
            .where(
                QuestionPlacement.is_active.is_(True),
                Question.content_status == 10,
                QuestionBank.status == 1,
                QuestionBank.bank_type == 2,
            )
        )

        if cat_ids:
            stmt = stmt.where(QuestionBank.cat_id.in_(cat_ids))

        region_text = (region or '').strip()
        if region_text:
            stmt = stmt.where(
                or_(
                    QuestionBank.name.ilike(f'%{region_text}%'),
                    QuestionBank.code.ilike(f'%{region_text}%'),
                    QuestionBank.desc.ilike(f'%{region_text}%'),
                )
            )

        stem_text = (stem_keyword or '').strip()
        if stem_text:
            stmt = stmt.where(Question.stem.ilike(f'%{stem_text}%'))

        option_text = (option_keyword or '').strip()
        if option_text:
            stmt = stmt.where(cast(Question.options, String).ilike(f'%{option_text}%'))

        analysis_text = (analysis_keyword or '').strip()
        if analysis_text:
            analysis_exists = (
                select(1)
                .select_from(QuestionAnalysis)
                .where(
                    QuestionAnalysis.question_id == Question.id,
                    QuestionAnalysis.status == 10,
                    QuestionAnalysis.content.ilike(f'%{analysis_text}%'),
                )
                .exists()
            )
            stmt = stmt.where(analysis_exists)

        if year_start is not None:
            start_at = datetime(year_start, 1, 1, tzinfo=timezone.tz_info)
            stmt = stmt.where(Question.created_time >= start_at)
        if year_end is not None:
            end_at = datetime(year_end + 1, 1, 1, tzinfo=timezone.tz_info)
            stmt = stmt.where(Question.created_time < end_at)

        normalized_ids = [kp_id for kp_id in (knowledge_ids or []) if isinstance(kp_id, int) and kp_id > 0]
        normalized_names = [name.strip() for name in (knowledge_names or []) if name and name.strip()]

        if normalized_ids or normalized_names:
            kp_column = cast(Question.knowledge_point, PGJSONB)
            conditions = []
            for kp_id in normalized_ids:
                conditions.extend((
                    kp_column.contains([kp_id]),
                    kp_column.contains([{'id': kp_id}]),
                    kp_column.contains([{'category_id': kp_id}]),
                    kp_column.contains([{'cat_id': kp_id}]),
                ))

            for kp_name in normalized_names:
                conditions.extend((
                    kp_column.contains([kp_name]),
                    kp_column.contains([{'name': kp_name}]),
                    kp_column.contains([{'label': kp_name}]),
                    kp_column.contains([{'title': kp_name}]),
                ))

            stmt = stmt.where(or_(*conditions))

        stmt = stmt.group_by(
            QuestionBank.id,
            QuestionBank.cat_id,
            QuestionBank.name,
            QuestionBank.code,
            QuestionBank.desc,
            QuestionBank.bank_type,
            QuestionBank.difficulty,
            QuestionBank.parent_id,
            QuestionBank.q_count_cache,
        ).order_by(
            QuestionBank.name.desc(),
            func.count(func.distinct(Question.id)).desc(),
            QuestionBank.id.desc(),
        )

        rows = (await db.execute(stmt)).mappings().all()
        data = [dict(row) for row in rows]

        await collections_cache.set(cache_hash, value=data)

        return data

    @staticmethod
    async def create(*, db: AsyncSession, obj: CreateQuestionParam, user_id: int) -> Question:
        """
        创建题目
        :param db: 数据库会话
        :param obj: 创建题目参数
        :param user_id: 用户 ID
        :return:
        """
        # 1. 验证挂载引用的题库/章节存在
        for pl in obj.placements:
            bank = await bank_dao.get(db, pl.bank_id)
            if not bank:
                raise errors.NotFoundError(msg=f'题库 ID {pl.bank_id} 不存在')
            if pl.chapter_id:
                await QuestionService._verify_chapter_in_bank_context(
                    db=db,
                    bank_id=pl.bank_id,
                    chapter_id=pl.chapter_id,
                )

        # 2. 创建主表
        question = await question_dao.create(db, obj.core, user_id)

        # 3. 写选项
        question.options = QuestionService.normalize_options(obj.options)
        await db.flush()

        # 4. 写挂载
        await question_placement_dao.replace_for_question(
            db,
            question_id=question.id,
            items=obj.placements,
            user_id=user_id,
        )

        # 5. 写解析
        await question_analysis_dao.replace_versions(
            db,
            question_id=question.id,
            items=obj.analyses,
            user_id=user_id,
        )

        # 6. 写材料关联
        if obj.material_ids:
            await question_dao.set_material_ids(db, question.id, obj.material_ids)

        # 7. 更新 bank/chapter q_count_cache（每个挂载 +1）
        await QuestionService._update_placement_caches(db=db, placements=obj.placements, delta=1)

        log.info('Question created: id=%d type=%s user=%d', question.id, obj.core.type, user_id)
        return question

    @staticmethod
    async def update(*, db: AsyncSession, pk: int, obj: UpdateQuestionParam, user_id: int) -> int:
        """
        更新题目（嵌套 schema，每个子段可选，传入即全量替换）

        :param db: 数据库会话
        :param pk: 题目 ID
        :param obj: 更新题目参数
        :param user_id: 用户 ID
        :return:
        """
        question = await question_dao.get(db, pk)
        if not question:
            raise errors.NotFoundError(msg='Question not found')

        count = 0

        # 1. 更新主表
        if obj.core is not None:
            count = await question_dao.update(db, pk, obj.core, user_id)

        # 2. 更新选项（全量替换）
        if obj.options is not None:
            question.options = QuestionService.normalize_options(obj.options)
            await db.flush()
            count = max(count, 1)

        # 3. 更新挂载（全量替换）
        if obj.placements is not None:
            for pl in obj.placements:
                bank = await bank_dao.get(db, pl.bank_id)
                if not bank:
                    raise errors.NotFoundError(msg=f'题库 ID {pl.bank_id} 不存在')
                if pl.chapter_id:
                    await QuestionService._verify_chapter_in_bank_context(
                        db=db,
                        bank_id=pl.bank_id,
                        chapter_id=pl.chapter_id,
                    )

            # 先记录旧挂载用于计算 cache delta
            old_placements = await question_placement_dao.list_by_question_ids(db, question_ids=[pk])
            await question_placement_dao.replace_for_question(
                db,
                question_id=pk,
                items=obj.placements,
                user_id=user_id,
            )
            # 旧挂载 -1，新挂载 +1
            await QuestionService._update_placement_caches_from_old(
                db=db,
                old_placements=old_placements,
                new_placements=obj.placements,
            )
            count = max(count, 1)

        # 4. 更新解析（全量替换）
        if obj.analyses is not None:
            await question_analysis_dao.replace_versions(
                db,
                question_id=pk,
                items=obj.analyses,
                user_id=user_id,
            )
            count = max(count, 1)

        # 5. 更新材料关联（全量替换）
        if obj.material_ids is not None:
            await question_dao.set_material_ids(db, pk, obj.material_ids)
            count = max(count, 1)

        log.info('Question updated: id=%d user=%d', pk, user_id)
        if count > 0:
            await solution_content_cache.invalidate(pk)
        return count

    @staticmethod
    async def delete(*, db: AsyncSession, obj: DeleteQuestionParam) -> int:
        """
        删除题目（先更新缓存再级联删除）

        :param db: 数据库会话
        :param obj: 删除题目参数
        :return:
        """
        # 先查询将被删除的挂载，用于扣减缓存
        if obj.ids:
            placements = await question_placement_dao.list_by_question_ids(db, question_ids=obj.ids)
            bank_delta: dict[int, int] = {}
            chapter_delta: dict[int, int] = {}
            for p in placements:
                bank_delta[p.bank_id] = bank_delta.get(p.bank_id, 0) + 1
                if p.chapter_id:
                    chapter_delta[p.chapter_id] = chapter_delta.get(p.chapter_id, 0) + 1

            for bid, delta in bank_delta.items():
                await QuestionService._update_bank_q_count_cache_recursive(db=db, bank_id=bid, delta=-delta)
            for cid, delta in chapter_delta.items():
                await db.execute(
                    update(QuestionChapter)
                    .where(QuestionChapter.id == cid)
                    .values(q_count_cache=QuestionChapter.q_count_cache - delta)
                )

        count = await question_dao.delete(db, obj.ids)
        if count > 0:
            for question_id in obj.ids:
                await solution_content_cache.invalidate(question_id)
        log.info('Questions deleted: ids=%s count=%d', obj.ids, count)
        return count

    # ------------------------------------------------------------------
    #  题目解析
    # ------------------------------------------------------------------

    @staticmethod
    async def get_analysis(*, db: AsyncSession, question_id: int, increment_view: bool = True) -> QuestionAnalysis:
        """
        获取题目解析

        :param db: 数据库会话
        :param question_id: 题目 ID
        :param increment_view: 是否增加查看次数
        :return:
        """
        question = await question_dao.get(db, question_id)
        if not question:
            raise errors.NotFoundError(msg='Question not found')

        analysis = await question_analysis_dao.get_by_question_id(db, question_id)
        if not analysis:
            raise errors.NotFoundError(msg='Question analysis not found')

        if increment_view:
            await question_analysis_dao.increment_view_count(db, question_id)

        return analysis

    @staticmethod
    async def get_solution(*, db: AsyncSession, question_id: int, user_answer: str | None = None) -> dict[str, Any]:
        """
        获取题目答案和解析（练题模式专用）

        :param db: 数据库会话
        :param question_id: 题目 ID
        :param user_answer: 用户答案
        :return:
        """
        # 答案和解析内容按 question_id 长缓存；实时统计不进入长缓存。
        content_payload: dict[str, Any] | None = None
        question_type: str | None = None
        answer_data: Any = None

        cached_obj = await solution_content_cache.get(question_id)
        if cached_obj:
            content_payload = cached_obj.get('content')
            question_type = cached_obj.get('question_type')
            answer_data = cached_obj.get('answer_data')

        if content_payload is None:
            stmt = (
                select(Question)
                .where(Question.id == question_id)
                .options(
                    selectinload(Question.analyses),
                )
            )
            result = await db.execute(stmt)
            question = result.scalars().first()
            if not question:
                raise errors.NotFoundError(msg='Question not found')

            analysis = QuestionService._pick_default_analysis(question.analyses)
            if not analysis:
                raise errors.NotFoundError(msg='Question analysis not found')

            content_payload = QuestionService.build_solution_content_payload(analysis=analysis)
            question_type = question.type
            answer_data = analysis.answer_data

            await solution_content_cache.set(
                question_id,
                value={
                    'content': content_payload,
                    'question_type': question_type,
                    'answer_data': answer_data,
                },
            )

        statistics = await question_statistics_dao.get_by_question_id(db, question_id)
        payload = {
            **content_payload,
            'is_correct': None,
            'correct_rate': statistics.correct_rate if statistics else Decimal('0'),
            'option_select_stats': statistics.option_select_stats if statistics else {},
        }
        if user_answer is not None and question_type and answer_data is not None:
            try:
                parsed_answer = json.loads(user_answer)
            except (json.JSONDecodeError, TypeError):
                parsed_answer = user_answer
            payload['is_correct'] = QuestionService.check_answer(question_type, parsed_answer, answer_data)

        return payload

    @staticmethod
    async def mark_analysis_helpful(*, db: AsyncSession, question_id: int, is_helpful: bool) -> None:
        """
        标记解析是否有帮助
        :param db: 数据库会话
        :param question_id: 题目 ID
        :param is_helpful: 是否有帮助
        """
        analysis = await question_analysis_dao.get_by_question_id(db, question_id)
        if not analysis:
            raise errors.NotFoundError(msg='Question analysis not found')

        await question_analysis_dao.increment_helpful_count(db, question_id, is_helpful)

    # ------------------------------------------------------------------
    #  判题
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_pair_mapping(value: Any) -> dict[str, str] | None:
        """
        归一化匹配题答案

        :param value: 原始答案
        :return:
        """
        if isinstance(value, dict):
            if isinstance(value.get('pairs'), list):
                return QuestionService._normalize_pair_mapping(value['pairs'])
            return {
                str(left).strip(): str(right).strip()
                for left, right in value.items()
                if str(left).strip() and str(right).strip()
            }

        if not isinstance(value, list):
            return None

        mapping: dict[str, str] = {}
        for item in value:
            if isinstance(item, dict):
                left = item.get('left') or item.get('source') or item.get('from') or item.get('left_id')
                right = item.get('right') or item.get('target') or item.get('to') or item.get('right_id')
            elif isinstance(item, (list, tuple)) and len(item) >= 2:
                left = item[0]
                right = item[1]
            else:
                continue

            left_key = str(left).strip()
            right_key = str(right).strip()
            if not left_key or not right_key:
                continue
            mapping[left_key] = right_key

        return mapping

    @staticmethod
    def _normalize_anchor_answer(value: Any) -> str | list[str] | dict[str, str] | None:
        """
        归一化锚点答案

        :param value: 原始答案
        :return:
        """
        if value is None:
            return None

        if isinstance(value, (str, int)):
            normalized = str(value).strip()
            return normalized or None

        if isinstance(value, list):
            normalized_list = [str(item).strip() for item in value if str(item).strip()]
            return sorted(normalized_list)

        if isinstance(value, dict):
            normalized_dict: dict[str, str] = {}
            for key, item in value.items():
                normalized_key = str(key).strip()
                normalized_value = str(item).strip()
                if normalized_key and normalized_value:
                    normalized_dict[normalized_key] = normalized_value
            return normalized_dict

        return None

    @staticmethod
    def check_answer(question_type: str, user_answer: Any, correct_data: dict) -> bool:
        """
        判断答案是否正确

        :param question_type: 题型
        :param user_answer: 用户答案
        :param correct_data: 正确答案数据
        :return:
        """
        correct_answer = correct_data.get('correct')

        if question_type in ['single', 'judgement']:
            return str(user_answer).strip().upper() == str(correct_answer).strip().upper()

        if question_type == 'multiple':
            if not isinstance(user_answer, list):
                return False
            user_set = {str(ans).strip().upper() for ans in user_answer}
            correct_set = {str(ans).strip().upper() for ans in correct_answer}
            return user_set == correct_set

        if question_type == 'fill':
            if not isinstance(user_answer, list):
                return False
            if len(user_answer) != len(correct_answer):
                return False
            return all(str(u).strip() == str(c).strip() for u, c in zip(user_answer, correct_answer))

        if question_type == 'shortAnswer':
            keywords = correct_data.get('keywords', [])
            if not keywords:
                return True
            user_text = str(user_answer).lower()
            matched = sum(1 for keyword in keywords if keyword.lower() in user_text)
            return matched >= len(keywords) * 0.6

        if question_type in ['matching', 'connection']:
            user_mapping = QuestionService._normalize_pair_mapping(user_answer)
            correct_mapping = QuestionService._normalize_pair_mapping(correct_answer)
            if user_mapping is None or correct_mapping is None:
                return False
            return user_mapping == correct_mapping

        if question_type in ['numberLocate', 'evidenceLocate', 'regionLocate', 'anchorLocate']:
            user_anchor_answer = QuestionService._normalize_anchor_answer(user_answer)
            correct_anchor_answer = QuestionService._normalize_anchor_answer(correct_answer)
            if user_anchor_answer is None or correct_anchor_answer is None:
                return False
            return user_anchor_answer == correct_anchor_answer

        return False

    # ------------------------------------------------------------------
    #  题目统计
    # ------------------------------------------------------------------

    @staticmethod
    async def get_statistics(*, db: AsyncSession, question_id: int) -> QuestionStatistics:
        """
        获取题目统计

        :param db: 数据库会话
        :param question_id: 题目 ID
        :return:
        """
        question = await question_dao.get(db, question_id)
        if not question:
            raise errors.NotFoundError(msg='题目不存在')

        return await question_statistics_dao.get_or_create(db, question_id)

    @staticmethod
    async def update_statistics(*, db: AsyncSession, question_id: int, obj: UpdateQuestionStatisticsParam) -> None:
        """
        更新题目统计

        :param db: 数据库会话
        :param question_id: 题目 ID
        :param obj: 更新统计参数
        """
        question = await question_dao.get(db, question_id)
        if not question:
            raise errors.NotFoundError(msg='Question not found')

        await question_statistics_dao.update_stats(db, question_id, obj)

    # ------------------------------------------------------------------
    #  内部工具
    # ------------------------------------------------------------------

    @staticmethod
    async def _get_or_create_chapter(
        *,
        db: AsyncSession,
        bank_id: int,
        level1_name: str | None,
        level2_name: str | None,
        chapter_cache: dict[str, int],
        level3_name: str | None = None,
    ) -> int | None:
        """
        获取或创建章节（支持三级）

        :param db: 数据库会话
        :param bank_id: 题库 ID
        :param level1_name: 一级章节名称
        :param level2_name: 二级章节名称
        :param level3_name: 三级章节名称
        :param chapter_cache: 章节缓存
        :return:
        """
        from backend.app.question_bank.schema.chapter import CreateChapterParam

        if not level1_name:
            return None

        bank = await bank_dao.get(db, bank_id)
        if not bank:
            raise errors.NotFoundError(msg=f'题库 ID {bank_id} 不存在')

        source_bank_id = bank.chapter_source_bank_id or bank.id

        levels: list[tuple[str | None, int]] = [
            (level1_name, 1),
            (level2_name, 2),
            (level3_name, 3),
        ]
        parent_id: int | None = None
        key_parts: list[str] = [str(source_bank_id)]

        for name, level in levels:
            if not name:
                break
            key_parts.append(name)
            cache_key = ':'.join(key_parts)
            if cache_key not in chapter_cache:
                chapter = await chapter_dao.get_by_name(
                    db=db,
                    bank_id=source_bank_id,
                    name=name,
                    parent_id=parent_id,
                )
                if not chapter:
                    sort_order = await QuestionService._get_next_chapter_sort_order(
                        db=db,
                        bank_id=source_bank_id,
                        parent_id=parent_id,
                    )
                    param = CreateChapterParam(
                        bank_id=source_bank_id,
                        name=name,
                        level=level,
                        parent_id=parent_id,
                        sort_order=sort_order,
                    )
                    await chapter_dao.create(db, param)
                    await db.flush()
                    chapter = await chapter_dao.get_by_name(
                        db=db,
                        bank_id=source_bank_id,
                        name=name,
                        parent_id=parent_id,
                    )
                chapter_cache[cache_key] = chapter.id
            parent_id = chapter_cache[cache_key]

        return parent_id

    @staticmethod
    async def _get_next_chapter_sort_order(
        *,
        db: AsyncSession,
        bank_id: int,
        parent_id: int | None,
    ) -> int:
        """
        获取同级章节下一个排序值

        :param db: 数据库会话
        :param bank_id: 题库 ID
        :param parent_id: 父级章节 ID
        :return:
        """
        stmt = select(func.coalesce(func.max(QuestionChapter.sort_order), 0)).where(
            QuestionChapter.bank_id == bank_id,
        )
        if parent_id is None:
            stmt = stmt.where(QuestionChapter.parent_id.is_(None))
        else:
            stmt = stmt.where(QuestionChapter.parent_id == parent_id)

        max_sort_order = (await db.execute(stmt)).scalar() or 0
        return int(max_sort_order) + 10

    @staticmethod
    async def _update_placement_caches(
        db: AsyncSession,
        *,
        placements: list[UpsertQuestionPlacementItem],
        delta: int,
    ) -> None:
        """
        根据挂载列表更新 bank/chapter q_count_cache

        :param db: 数据库会话
        :param placements: 挂载列表
        :param delta: 变化量（+1 创建 / -1 删除）
        """
        bank_delta: dict[int, int] = {}
        chapter_delta: dict[int, int] = {}
        for pl in placements:
            bank_delta[pl.bank_id] = bank_delta.get(pl.bank_id, 0) + delta
            if pl.chapter_id:
                chapter_delta[pl.chapter_id] = chapter_delta.get(pl.chapter_id, 0) + delta

        for bid, d in bank_delta.items():
            await QuestionService._update_bank_q_count_cache_recursive(db=db, bank_id=bid, delta=d)
        for cid, d in chapter_delta.items():
            await db.execute(
                update(QuestionChapter)
                .where(QuestionChapter.id == cid)
                .values(q_count_cache=QuestionChapter.q_count_cache + d)
            )

    @staticmethod
    async def _update_placement_caches_from_old(
        db: AsyncSession,
        *,
        old_placements: Sequence[QuestionPlacement],
        new_placements: list[UpsertQuestionPlacementItem],
    ) -> None:
        """
        根据旧/新挂载差异更新 bank/chapter q_count_cache

        :param db: 数据库会话
        :param old_placements: 旧挂载 ORM 列表
        :param new_placements: 新挂载 schema 列表
        """
        # 旧挂载的 bank/chapter 各 -1
        old_bank_delta: dict[int, int] = {}
        old_chapter_delta: dict[int, int] = {}
        for p in old_placements:
            old_bank_delta[p.bank_id] = old_bank_delta.get(p.bank_id, 0) - 1
            if p.chapter_id:
                old_chapter_delta[p.chapter_id] = old_chapter_delta.get(p.chapter_id, 0) - 1

        # 新挂载的 bank/chapter 各 +1
        new_bank_delta: dict[int, int] = {}
        new_chapter_delta: dict[int, int] = {}
        for pl in new_placements:
            new_bank_delta[pl.bank_id] = new_bank_delta.get(pl.bank_id, 0) + 1
            if pl.chapter_id:
                new_chapter_delta[pl.chapter_id] = new_chapter_delta.get(pl.chapter_id, 0) + 1

        # 合并 delta
        all_bank_ids = set(old_bank_delta) | set(new_bank_delta)
        for bid in all_bank_ids:
            delta = old_bank_delta.get(bid, 0) + new_bank_delta.get(bid, 0)
            if delta != 0:
                await QuestionService._update_bank_q_count_cache_recursive(db=db, bank_id=bid, delta=delta)

        all_chapter_ids = set(old_chapter_delta) | set(new_chapter_delta)
        for cid in all_chapter_ids:
            delta = old_chapter_delta.get(cid, 0) + new_chapter_delta.get(cid, 0)
            if delta != 0:
                await db.execute(
                    update(QuestionChapter)
                    .where(QuestionChapter.id == cid)
                    .values(q_count_cache=QuestionChapter.q_count_cache + delta)
                )

    @staticmethod
    async def _update_bank_q_count_cache_recursive(*, db: AsyncSession, bank_id: int, delta: int) -> None:
        """
        递归更新题库及其所有父级题库的 q_count_cache

        :param db: 数据库会话
        :param bank_id: 题库 ID
        :param delta: 变化量
        """
        current_id = bank_id

        while current_id:
            await db.execute(
                update(QuestionBank)
                .where(QuestionBank.id == current_id)
                .values(q_count_cache=QuestionBank.q_count_cache + delta)
            )

            result = await db.execute(select(QuestionBank.parent_id).where(QuestionBank.id == current_id))
            parent_id = result.scalar()
            current_id = parent_id


question_service: QuestionService = QuestionService()
