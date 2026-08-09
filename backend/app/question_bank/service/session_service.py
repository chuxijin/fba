#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import hashlib
import json
import logging
import random
import uuid

from decimal import Decimal
from time import perf_counter
from typing import Any

from loguru import logger
from sqlalchemy import cast, or_, select
from sqlalchemy.dialects.postgresql import JSONB as PGJSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, load_only, selectinload

from backend.app.access.engine.snapshot import snapshot_service
from backend.app.growth.crud import experience_rule_dao
from backend.app.growth.service import experience_service
from backend.app.question_bank.crud.crud_practice_session import practice_session_dao
from backend.app.question_bank.crud.crud_question import (
    INVALID_TIME_THRESHOLD,
    question_statistics_dao,
)
from backend.app.question_bank.crud.crud_session_question import session_question_dao
from backend.app.question_bank.crud.crud_user_bank_progress import user_bank_progress_dao
from backend.app.question_bank.crud.crud_user_practice_stats import user_practice_stats_dao
from backend.app.question_bank.crud.crud_wrong_question import wrong_question_dao
from backend.app.question_bank.model import (
    PracticeSession,
    Question,
    QuestionAnalysis,
    QuestionBank,
    QuestionChapter,
    QuestionPlacement,
    SessionQuestion,
    WrongQuestionBook,
)
from backend.app.question_bank.schema.practice import (
    AnswerCardItem,
    BatchUpsertSessionQuestionsParam,
    CreatePracticeSessionParam,
    CreateSessionFromIdsParam,
    SessionReport,
    SubmitPracticeSessionParam,
    SubmitPracticeSessionResult,
)
from backend.app.question_bank.schema.question import QuestionCollectParam
from backend.app.question_bank.service.ai_evaluation_service import (
    SUBJECTIVE_QUESTION_TYPES,
    practice_ai_evaluation_service,
)
from backend.app.question_bank.service.bank_mount_service import COLLECTION_BANK_TYPE, bank_mount_service
from backend.app.question_bank.service.category_filter_service import category_filter_service
from backend.app.question_bank.service.check_in_service import check_in_service
from backend.app.question_bank.service.knowledge_point_service import knowledge_point_service
from backend.app.question_bank.service.question_selector_service import question_selector_service
from backend.app.question_bank.service.question_service import question_service
from backend.common.exception import errors
from backend.utils.timezone import timezone

log = logging.getLogger(__name__)


class SessionService:
    """练习会话服务类（唯一刷题写入入口）"""

    PRACTICE_MODE_EXAM = 'exam'
    PRACTICE_MODE_PRACTICE = 'practice'
    PRACTICE_MODE_MEMORIZE = 'memorize'

    @staticmethod
    def _clean_session_name(value: Any) -> str | None:
        """
        清理练习名称片段

        :param value: 原始值
        :return:
        """
        text = str(value or '').strip()
        if not text:
            return None
        return ' '.join(text.split())

    @staticmethod
    def _truncate_session_name(value: str, max_length: int = 255) -> str:
        """
        截断练习名称

        :param value: 练习名称
        :param max_length: 最大长度
        :return:
        """
        if len(value) <= max_length:
            return value
        return f'{value[: max_length - 1]}…'

    @classmethod
    def _build_knowledge_point_name(cls, source_snapshot: dict[str, Any] | None) -> str | None:
        """
        生成知识点名称片段

        :param source_snapshot: 来源快照
        :return:
        """
        kp_names = source_snapshot.get('knowledge_point_names') if source_snapshot else None
        if not isinstance(kp_names, list) or not kp_names:
            return None

        names = [cls._clean_session_name(item) for item in kp_names]
        names = [item for item in names if item]
        if not names:
            return None
        if len(names) == 1:
            return names[0]
        return f'{names[0]}等{len(names)}个考点'

    @staticmethod
    def _resolve_practice_mode(
        *,
        session_type: str,
        exam_config: dict[str, Any] | None,
        source_snapshot: dict[str, Any] | None,
    ) -> str:
        """
        解析练习模式

        :param session_type: 会话类型
        :param exam_config: 考试配置
        :param source_snapshot: 来源快照
        :return:
        """
        config_mode = (exam_config or {}).get('practice_mode')
        snapshot_mode = (source_snapshot or {}).get('practice_mode')
        mode = str(config_mode or snapshot_mode or '').strip()
        if mode in {'exercise', 'brush'}:
            return SessionService.PRACTICE_MODE_PRACTICE
        if mode in {
            SessionService.PRACTICE_MODE_EXAM,
            SessionService.PRACTICE_MODE_PRACTICE,
            SessionService.PRACTICE_MODE_MEMORIZE,
        }:
            return mode
        if session_type == 'exam':
            return SessionService.PRACTICE_MODE_EXAM
        return SessionService.PRACTICE_MODE_PRACTICE

    @classmethod
    def _normalize_exam_config(cls, session_type: str, exam_config: dict[str, Any] | None) -> dict[str, Any] | None:
        """
        规范考试配置

        :param session_type: 会话类型
        :param exam_config: 考试配置
        :return:
        """
        if session_type != 'exam':
            return exam_config

        normalized = dict(exam_config or {})
        normalized.setdefault('practice_mode', 'exam')

        time_limit_minutes = cls._parse_positive_int(normalized.get('time_limit'))
        if time_limit_minutes <= 0:
            normalized.pop('time_limit', None)
            return normalized

        normalized['time_limit'] = max(1, min(300, time_limit_minutes))
        return normalized

    @staticmethod
    def _parse_positive_int(value: Any) -> int:
        """
        解析正整数

        :param value: 原始值
        :return:
        """
        if isinstance(value, bool):
            return 0
        if isinstance(value, int):
            return value if value > 0 else 0
        if isinstance(value, float):
            return int(value) if value > 0 and value.is_integer() else 0
        if isinstance(value, str) and value.strip().isdigit():
            return int(value.strip())
        return 0

    @classmethod
    def _build_contextual_practice_name(
        cls,
        *,
        provided_name: str | None,
        session_type: str,
        bank: QuestionBank | None,
        chapter: QuestionChapter | None,
        exam_config: dict[str, Any] | None,
        source_snapshot: dict[str, Any] | None,
        total_count: int,
    ) -> str | None:
        """
        生成上下文完整的练习名称

        :param provided_name: 前端传入名称
        :param session_type: 会话类型
        :param bank: 题库
        :param chapter: 篇章
        :param exam_config: 考试配置
        :param source_snapshot: 来源快照
        :param total_count: 题量
        :return:
        """
        clean_provided = cls._clean_session_name(provided_name)
        bank_name = cls._clean_session_name(getattr(bank, 'name', None))
        chapter_name = cls._clean_session_name(getattr(chapter, 'name', None))
        kp_name = cls._build_knowledge_point_name(source_snapshot)

        if session_type == 'random' and kp_name:
            context_name = kp_name
        elif bank_name and chapter_name and chapter_name not in bank_name:
            context_name = f'{bank_name} · {chapter_name}'
        elif bank_name:
            context_name = bank_name
        elif chapter_name:
            context_name = chapter_name
        elif kp_name:
            context_name = kp_name
        else:
            context_name = clean_provided

        mode = cls._resolve_practice_mode(
            session_type=session_type,
            exam_config=exam_config,
            source_snapshot=source_snapshot,
        )

        if session_type == 'wrong':
            base = f'{context_name} · 错题重练' if context_name else '错题重练'
            return cls._truncate_session_name(f'{base} · {total_count}题')
        if session_type == 'favorite':
            base = f'{context_name} · 收藏练习' if context_name else '收藏练习'
            return cls._truncate_session_name(f'{base} · {total_count}题')
        if session_type == 'note':
            base = f'{context_name} · 笔记练习' if context_name else '笔记练习'
            return cls._truncate_session_name(f'{base} · {total_count}题')
        if session_type == 'random':
            base = context_name or clean_provided or '随机练习'
            return cls._truncate_session_name(f'{base} · 随机练习 · {total_count}题')
        if mode == 'exam':
            base = context_name or clean_provided or '练习'
            return cls._truncate_session_name(f'模拟考试 · {base}')
        if mode == 'memorize':
            base = context_name or clean_provided or '练习'
            return cls._truncate_session_name(f'{base} · 背题')

        if context_name:
            return cls._truncate_session_name(context_name)
        return clean_provided

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
    def _build_knowledge_point_conditions(*, kp_ids: list[int], kp_names: list[str]) -> list[Any]:
        """
        构建知识点查询条件

        :param kp_ids: 知识点 ID 列表
        :param kp_names: 知识点名称列表
        :return:
        """
        kp_column = cast(Question.knowledge_point, PGJSONB)
        conditions: list[Any] = []

        for kp_id in kp_ids:
            conditions.append(kp_column.contains([kp_id]))
            conditions.append(kp_column.contains([{'id': kp_id}]))

        for kp_name in kp_names:
            conditions.append(kp_column.contains([kp_name]))
            conditions.append(kp_column.contains([{'name': kp_name}]))
            conditions.append(kp_column.contains([{'label': kp_name}]))
            conditions.append(kp_column.contains([{'title': kp_name}]))

        return conditions

    @classmethod
    def _build_session_source_snapshot(cls, obj: CreatePracticeSessionParam) -> dict[str, Any]:
        """
        构建会话来源快照

        :param obj: 创建会话参数
        :return:
        """
        kp_ids, kp_names = cls._normalize_knowledge_point_terms(obj.knowledge_point)
        source_scope = 'personal' if obj.session_type in {'wrong', 'favorite', 'note'} else 'placement'
        exam_config = obj.exam_config or {}
        practice_mode = exam_config.get('practice_mode')
        time_limit = exam_config.get('time_limit')
        question_types: list[str] | None = None
        if obj.question_types:
            question_types = sorted(set(obj.question_types))

        return {
            'session_type': obj.session_type,
            'source_scope': source_scope,
            'bank_id': obj.bank_id,
            'chapter_id': obj.chapter_id,
            'cat_id': obj.cat_id,
            'region': (obj.region or '').strip() or None,
            'year_start': obj.year_start,
            'year_end': obj.year_end,
            'knowledge_point_ids': kp_ids,
            'knowledge_point_names': kp_names,
            'question_types': question_types,
            'limit': obj.limit,
            'shuffle': obj.shuffle,
            'practice_mode': practice_mode,
            'time_limit': time_limit,
        }

    @staticmethod
    def _build_session_source_key(source_snapshot: dict[str, Any]) -> str:
        """
        计算会话来源签名

        :param source_snapshot: 来源快照
        :return:
        """
        payload = json.dumps(source_snapshot, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(payload.encode('utf-8')).hexdigest()

    @classmethod
    def build_session_source_key(cls, obj: CreatePracticeSessionParam) -> str:
        """
        基于创建会话参数生成来源签名

        :param obj: 创建会话参数
        :return:
        """
        source_snapshot = cls._build_session_source_snapshot(obj)
        return cls._build_session_source_key(source_snapshot)

    @classmethod
    def _build_collect_param(
        cls,
        *,
        obj: CreatePracticeSessionParam,
        source_type: str,
    ) -> QuestionCollectParam:
        """将练习会话筛题参数映射为统一筛题参数。"""
        return QuestionCollectParam(
            source_type=source_type,
            bank_id=obj.bank_id,
            chapter_id=obj.chapter_id,
            year_start=obj.year_start,
            year_end=obj.year_end,
            region=obj.region,
            cat_id=obj.cat_id,
            knowledge_point=obj.knowledge_point,
            question_types=obj.question_types,
            content_status=10,
            is_active=True if source_type == 'placement' else None,
            limit=obj.limit if not obj.shuffle else None,
        )

    @staticmethod
    def _dedup_placements_by_question(placements: list[QuestionPlacement]) -> list[QuestionPlacement]:
        """
        按 question_id 去重（保留首个命中 placement）

        说明：
        - 同一题可能挂载在多个试卷/章节，创建同一会话时应只保留一题；
        - 保留顺序受上游排序/打乱影响（即“当前顺序下第一个命中”）。
        """
        seen_question_ids: set[int] = set()
        unique_placements: list[QuestionPlacement] = []
        for placement in placements:
            if placement.question_id in seen_question_ids:
                continue
            seen_question_ids.add(placement.question_id)
            unique_placements.append(placement)
        return unique_placements

    @staticmethod
    def _pick_placement_by_context(
        *,
        placements: list[QuestionPlacement],
        bank_id: int | None = None,
        bank_ids: list[int] | None = None,
        chapter_id: int | None = None,
        chapter_scope_ids: list[int] | None = None,
    ) -> QuestionPlacement | None:
        """
        按题库/章节上下文选择挂载

        :param placements: 候选挂载列表
        :param bank_id: 题库 ID
        :param bank_ids: 题库 ID 列表
        :param chapter_id: 章节 ID
        :param chapter_scope_ids: 章节及子章节 ID 列表
        :return:
        """
        if not placements:
            return None

        sorted_candidates = sorted(placements, key=lambda item: (item.sort_order, item.id))

        if bank_ids:
            bank_id_set = set(bank_ids)
            if chapter_id is not None:
                for placement in sorted_candidates:
                    if placement.bank_id in bank_id_set and placement.chapter_id == chapter_id:
                        return placement
                if chapter_scope_ids:
                    chapter_scope_set = set(chapter_scope_ids)
                    for placement in sorted_candidates:
                        if placement.bank_id in bank_id_set and placement.chapter_id in chapter_scope_set:
                            return placement
                return None

            for placement in sorted_candidates:
                if placement.bank_id in bank_id_set:
                    return placement
            return None

        if bank_id is not None and chapter_id is not None:
            for placement in sorted_candidates:
                if placement.bank_id == bank_id and placement.chapter_id == chapter_id:
                    return placement
            if chapter_scope_ids:
                chapter_scope_set = set(chapter_scope_ids)
                for placement in sorted_candidates:
                    if placement.bank_id == bank_id and placement.chapter_id in chapter_scope_set:
                        return placement
            return None

        if bank_id is not None:
            for placement in sorted_candidates:
                if placement.bank_id == bank_id:
                    return placement
            return None

        if chapter_id is not None:
            for placement in sorted_candidates:
                if placement.chapter_id == chapter_id:
                    return placement
            if chapter_scope_ids:
                chapter_scope_set = set(chapter_scope_ids)
                for placement in sorted_candidates:
                    if placement.chapter_id in chapter_scope_set:
                        return placement
            return None

        return sorted_candidates[0]

    @staticmethod
    async def _resolve_placement_bank_scope(
        *,
        db: AsyncSession,
        bank_id: int | None,
    ) -> list[int] | None:
        """
        解析实际筛题题库范围

        :param db: 数据库会话
        :param bank_id: 题库 ID
        :return:
        """
        if bank_id is None:
            return None

        stmt = select(QuestionBank.id, QuestionBank.bank_type).where(
            QuestionBank.id == bank_id,
            QuestionBank.status == 1,
        )
        row = (await db.execute(stmt)).first()
        if not row:
            raise errors.NotFoundError(msg='刷题内容不存在或已下架')
        if int(row.bank_type or 0) != COLLECTION_BANK_TYPE:
            return [bank_id]

        return await bank_mount_service.get_active_descendant_item_ids(
            db,
            collection_id=bank_id,
        )

    # ------------------------------------------------------------------
    #  Session 生命周期
    # ------------------------------------------------------------------

    @classmethod
    async def create_session(
        cls,
        *,
        db: AsyncSession,
        user_id: int,
        obj: CreatePracticeSessionParam,
        source_key: str | None = None,
        source_snapshot: dict[str, Any] | None = None,
    ) -> PracticeSession:
        """
        创建练习会话

        流程：解析参数 → 查询挂载 → 建会话 → 批量写 SessionQuestion → 返回

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param obj: 创建会话参数
        :return:
        """
        cs_timings: list[tuple[str, float]] = []
        cs_total_start = perf_counter()

        t0 = perf_counter()
        # AsyncSession 不能被多个 asyncio task 并发使用。
        bank_scope_ids = await cls._resolve_placement_bank_scope(db=db, bank_id=obj.bank_id)
        chapter_scope_ids = await question_selector_service.resolve_chapter_scope_ids(
            db=db,
            chapter_id=obj.chapter_id,
        )
        cs_timings.append(('cs_resolve_bank_and_chapter_scope', perf_counter() - t0))

        collect_param = cls._build_collect_param(obj=obj, source_type='placement')
        if obj.bank_id is not None:
            collect_param.cat_id = None
        if bank_scope_ids and obj.bank_id is not None and obj.bank_id not in bank_scope_ids:
            collect_param.bank_ids = bank_scope_ids

        t0 = perf_counter()
        collect_result = await question_selector_service.collect_question_ids(
            db=db,
            params=collect_param,
            user_id=user_id,
        )
        cs_timings.append(('cs_collect_question_ids', perf_counter() - t0))

        t0 = perf_counter()
        placements, prefetched_question_type_map = await cls._query_placements_by_question_ids(
            db=db,
            question_ids=collect_result.question_ids,
            bank_id=obj.bank_id,
            bank_ids=bank_scope_ids,
            chapter_id=obj.chapter_id,
            chapter_scope_ids=chapter_scope_ids,
            with_question_type=True,
        )
        cs_timings.append(('cs_query_placements', perf_counter() - t0))

        t0 = perf_counter()
        new_session = await cls._create_session_snapshot(
            db=db,
            user_id=user_id,
            session_type=obj.session_type,
            placements=placements,
            practice_name=obj.practice_name,
            bank_id=obj.bank_id,
            chapter_id=obj.chapter_id,
            exam_config=obj.exam_config,
            source_key=source_key,
            source_snapshot=source_snapshot,
            shuffle=obj.shuffle,
            limit=obj.limit,
            prefetched_question_type_map=prefetched_question_type_map,
        )
        cs_timings.append(('cs_create_snapshot', perf_counter() - t0))

        logger.debug(
            'create_session_inner_timing | user_id={} bank_id={} chapter_id={} q_count={} placement_count={} total={:.1f}ms detail={}',
            user_id,
            obj.bank_id,
            obj.chapter_id,
            len(collect_result.question_ids),
            len(placements),
            (perf_counter() - cs_total_start) * 1000,
            ', '.join(f'{name}={cost * 1000:.1f}ms' for name, cost in cs_timings),
        )
        return new_session

    @classmethod
    async def create_session_from_ids(
        cls,
        *,
        db: AsyncSession,
        user_id: int,
        obj: CreateSessionFromIdsParam,
        source_key: str | None = None,
        source_snapshot: dict[str, Any] | None = None,
    ) -> PracticeSession:
        """
        从题目 ID 列表创建练习会话

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param obj: 包含 question_ids、session_type、practice_name
        :return:
        """
        # ---- 1. 根据 question_ids 查询 placement ----
        bank_scope_ids = await cls._resolve_placement_bank_scope(db=db, bank_id=obj.bank_id)
        placements = await cls._query_placements_by_question_ids(
            db=db,
            question_ids=obj.question_ids,
            bank_id=obj.bank_id,
            bank_ids=bank_scope_ids,
            chapter_id=obj.chapter_id,
            chapter_scope_ids=await question_selector_service.resolve_chapter_scope_ids(
                db=db,
                chapter_id=obj.chapter_id,
            ),
        )
        return await cls._create_session_snapshot(
            db=db,
            user_id=user_id,
            session_type=obj.session_type,
            placements=placements,
            practice_name=obj.practice_name,
            bank_id=obj.bank_id,
            chapter_id=obj.chapter_id,
            source_key=source_key,
            source_snapshot=source_snapshot,
        )

    @staticmethod
    async def _get_question_type_map(*, db: AsyncSession, question_ids: list[int]) -> dict[int, str]:
        """
        获取题目类型映射

        :param db: 数据库会话
        :param question_ids: 题目 ID 列表
        :return:
        """
        if not question_ids:
            return {}

        stmt = select(Question.id, Question.type).where(Question.id.in_(question_ids))
        rows = (await db.execute(stmt)).all()
        return {row[0]: row[1] for row in rows}

    @classmethod
    async def _query_placements_by_question_ids(
        cls,
        *,
        db: AsyncSession,
        question_ids: list[int],
        bank_id: int | None = None,
        bank_ids: list[int] | None = None,
        chapter_id: int | None = None,
        chapter_scope_ids: list[int] | None = None,
        with_question_type: bool = False,
    ) -> list[QuestionPlacement] | tuple[list[QuestionPlacement], dict[int, str]]:
        """
        根据题目 ID 列表反查挂载

        :param db: 数据库会话
        :param question_ids: 题目 ID 列表
        :param bank_id: 题库 ID
        :param bank_ids: 题库 ID 列表
        :param chapter_id: 篇章 ID
        :param chapter_scope_ids: 篇章及子篇章 ID 列表
        :param with_question_type: True 时一起返回 question_type_map, 省一次独立查询
        :return:
        """
        if not question_ids:
            if with_question_type:
                return [], {}
            return []

        stmt = (
            select(QuestionPlacement)
            .where(
                QuestionPlacement.question_id.in_(question_ids),
                QuestionPlacement.is_active.is_(True),
            )
            .options(
                joinedload(QuestionPlacement.bank),
                joinedload(QuestionPlacement.chapter),
            )
            .order_by(QuestionPlacement.sort_order, QuestionPlacement.id)
        )
        result = await db.execute(stmt)
        all_placements = list(result.unique().scalars().all())

        placement_map: dict[int, list[QuestionPlacement]] = {}
        for placement in all_placements:
            placement_map.setdefault(placement.question_id, []).append(placement)

        placements: list[QuestionPlacement] = []
        for question_id in question_ids:
            matched_placement = cls._pick_placement_by_context(
                placements=placement_map.get(question_id, []),
                bank_id=bank_id,
                bank_ids=bank_ids,
                chapter_id=chapter_id,
                chapter_scope_ids=chapter_scope_ids,
            )
            if matched_placement is not None:
                placements.append(matched_placement)

        if with_question_type:
            # Cut Y3: 复用本次查询拿到的题目集合, 一次性查 question.type, 省一次独立 SQL
            picked_question_ids = list({placement.question_id for placement in placements})
            question_type_map: dict[int, str] = {}
            if picked_question_ids:
                type_stmt = select(Question.id, Question.type).where(Question.id.in_(picked_question_ids))
                type_rows = (await db.execute(type_stmt)).all()
                question_type_map = {row[0]: row[1] for row in type_rows}
            return placements, question_type_map

        return placements

    @staticmethod
    async def _create_session_snapshot(
        *,
        db: AsyncSession,
        user_id: int,
        session_type: str,
        placements: list[QuestionPlacement],
        practice_name: str | None = None,
        bank_id: int | None = None,
        chapter_id: int | None = None,
        exam_config: dict[str, Any] | None = None,
        source_key: str | None = None,
        source_snapshot: dict[str, Any] | None = None,
        shuffle: bool = False,
        limit: int | None = None,
        prefetched_question_type_map: dict[int, str] | None = None,
    ) -> PracticeSession:
        """
        根据挂载列表写入会话快照

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param session_type: 会话类型
        :param placements: 挂载列表
        :param practice_name: 练习名称
        :param bank_id: 题库 ID
        :param chapter_id: 篇章 ID
        :param exam_config: 考试配置
        :param source_key: 来源签名
        :param source_snapshot: 来源快照
        :param shuffle: 是否打乱
        :param limit: 限制题数
        :return:
        """
        snap_timings: list[tuple[str, float]] = []
        snap_total_start = perf_counter()

        if not placements:
            raise errors.NotFoundError(msg='没有可用的题目')

        t0 = perf_counter()
        if shuffle:
            random.shuffle(placements)

        original_count = len(placements)
        placements = SessionService._dedup_placements_by_question(placements)
        deduped_count = original_count - len(placements)
        if deduped_count > 0:
            log.info('Session create dedup: removed %d duplicate question placements', deduped_count)

        if limit is not None:
            placements = placements[:limit]

        if not placements:
            raise errors.NotFoundError(msg='没有可用的题目')
        snap_timings.append(('snap_dedup_limit', perf_counter() - t0))

        first_placement = placements[0]
        resolved_bank_id = bank_id or first_placement.bank_id
        resolved_chapter_id = chapter_id or first_placement.chapter_id

        practice_name = SessionService._build_contextual_practice_name(
            provided_name=practice_name,
            session_type=session_type,
            bank=first_placement.bank,
            chapter=first_placement.chapter,
            exam_config=exam_config,
            source_snapshot=source_snapshot,
            total_count=len(placements),
        )

        t0 = perf_counter()
        # Cut Y3: 优先使用上游预取的 question_type_map (来自 _query_placements_by_question_ids)
        if prefetched_question_type_map is not None:
            question_type_map = prefetched_question_type_map
        else:
            question_type_map = await SessionService._get_question_type_map(
                db=db,
                question_ids=list({placement.question_id for placement in placements}),
            )
        snap_timings.append(('snap_question_type_map', perf_counter() - t0))

        total_score = sum(placement.score or Decimal('0') for placement in placements)

        session_dict = {
            'session_key': uuid.uuid4().hex,
            'user_id': user_id,
            'session_type': session_type,
            'bank_id': resolved_bank_id,
            'chapter_id': resolved_chapter_id,
            'practice_name': practice_name,
            'source_key': source_key,
            'source_snapshot': source_snapshot,
            'total_count': len(placements),
            'total_score': total_score if total_score > 0 else None,
            'start_time': timezone.now(),
            'exam_config': exam_config,
            'created_by': user_id,
        }
        t0 = perf_counter()
        new_session = await practice_session_dao.create(db=db, obj_dict=session_dict)
        snap_timings.append(('snap_create_session', perf_counter() - t0))

        session_question_items: list[dict[str, Any]] = []
        for index, placement in enumerate(placements, start=1):
            session_question_items.append({
                'user_id': user_id,
                'seq_no': index,
                'question_id': placement.question_id,
                'placement_id': placement.id,
                'question_type': question_type_map.get(placement.question_id, 'single'),
                'full_score': placement.score or Decimal('0'),
            })
        t0 = perf_counter()
        # Cut #4b: 全新 session 走 batch_create_pristine 跳过 on_conflict_do_nothing
        # 新 session_id 刚 INSERT, 表中绝无相同 (session_id, question_id) 行
        await session_question_dao.batch_create_pristine(
            db=db,
            session_id=new_session.id,
            items=session_question_items,
        )
        snap_timings.append(('snap_batch_create_questions', perf_counter() - t0))

        logger.debug(
            'create_session_snapshot_timing | user_id={} session_id={} placement_count={} total={:.1f}ms detail={}',
            user_id,
            new_session.id,
            len(placements),
            (perf_counter() - snap_total_start) * 1000,
            ', '.join(f'{name}={cost * 1000:.1f}ms' for name, cost in snap_timings),
        )

        log.info(
            'Session created: id=%d user=%d type=%s total=%d',
            new_session.id,
            user_id,
            session_type,
            len(placements),
        )
        return new_session

    @staticmethod
    async def _get_owned_session(*, db: AsyncSession, session_id: int, user_id: int) -> PracticeSession:
        """
        获取当前用户可访问的会话

        :param db: 数据库会话
        :param session_id: 会话 ID
        :param user_id: 用户 ID
        :return:
        """
        session = await practice_session_dao.get(db=db, session_id=session_id)
        if not session:
            raise errors.NotFoundError(msg='会话不存在')
        if session.user_id != user_id:
            raise errors.ForbiddenError(msg='无权访问此会话')
        return session

    @staticmethod
    async def _get_owned_session_detail(*, db: AsyncSession, session_id: int, user_id: int) -> PracticeSession:
        """
        获取当前用户可访问的会话详情

        :param db: 数据库会话
        :param session_id: 会话 ID
        :param user_id: 用户 ID
        :return:
        """
        session = await practice_session_dao.get_detail(db=db, session_id=session_id)
        if not session:
            raise errors.NotFoundError(msg='会话不存在')
        if session.user_id != user_id:
            raise errors.ForbiddenError(msg='无权访问此会话')
        return session

    @staticmethod
    def _build_session_detail_response_dict(session: PracticeSession) -> dict:
        """根据已加载的 session（含 session_questions/placement/chapter）构造详情字典"""
        chapter_distribution: dict = {}
        session_questions_data: list[dict] = []

        for sq in session.session_questions:
            chapter_data = None
            if sq.placement and sq.placement.chapter:
                chapter = sq.placement.chapter
                chapter_data = {
                    'id': chapter.id,
                    'name': chapter.name,
                    'code': chapter.code,
                    'parent_id': chapter.parent_id,
                    'level': chapter.level,
                    'sort_order': chapter.sort_order,
                }

                chapter_key = chapter.id
                if chapter_key not in chapter_distribution:
                    chapter_distribution[chapter_key] = {
                        'chapter_id': chapter.id,
                        'chapter_name': chapter.name,
                        'chapter_code': chapter.code,
                        'question_count': 0,
                        'sort_order': chapter.sort_order,
                    }
                chapter_distribution[chapter_key]['question_count'] += 1
            else:
                if None not in chapter_distribution:
                    chapter_distribution[None] = {
                        'chapter_id': None,
                        'chapter_name': '未分类',
                        'chapter_code': None,
                        'question_count': 0,
                    }
                chapter_distribution[None]['question_count'] += 1

            session_questions_data.append({
                'id': sq.id,
                'session_id': sq.session_id,
                'seq_no': sq.seq_no,
                'question_id': sq.question_id,
                'placement_id': sq.placement_id,
                'question_type': sq.question_type,
                'full_score': sq.full_score,
                'chapter': chapter_data,
                'user_answer': sq.user_answer,
                'is_correct': sq.is_correct,
                'score': sq.score,
                'answer_time': sq.answer_time,
                'judged_at': sq.judged_at,
                'judge_version': sq.judge_version,
            })

        distribution_list = sorted(
            chapter_distribution.values(),
            key=lambda x: x['question_count'],
            reverse=True,
        )

        return {
            **session.__dict__,
            'chapter_distribution': distribution_list,
            'session_questions': session_questions_data,
        }

    @staticmethod
    async def get_session_detail(*, db: AsyncSession, session_id: int, user_id: int) -> dict:
        """
        获取练习会话详情（含会话题目快照和答题记录）

        :param db: 数据库会话
        :param session_id: 会话 ID
        :param user_id: 用户 ID
        :return:
        """
        timings: list[tuple[str, float]] = []
        total_start = perf_counter()

        t0 = perf_counter()
        session = await SessionService._get_owned_session_detail(
            db=db,
            session_id=session_id,
            user_id=user_id,
        )
        timings.append(('sql_get_detail_with_selectin', perf_counter() - t0))

        t0 = perf_counter()
        result = SessionService._build_session_detail_response_dict(session)
        timings.append(('build_response_dict', perf_counter() - t0))

        logger.debug(
            'session_detail_timing | session_id={} user_id={} sq_count={} total={:.1f}ms detail={}',
            session_id,
            user_id,
            len(result['session_questions']),
            (perf_counter() - total_start) * 1000,
            ', '.join(f'{name}={cost * 1000:.1f}ms' for name, cost in timings),
        )
        return result

    @staticmethod
    async def get_session_detail_by_key(*, db: AsyncSession, session_key: str, user_id: int) -> dict:
        """
        按 session_key 获取练习会话详情（一条 SQL 取代 by_key + by_id 两步）

        :param db: 数据库会话
        :param session_key: 会话唯一标识
        :param user_id: 用户 ID
        :return:
        """
        timings: list[tuple[str, float]] = []
        total_start = perf_counter()

        t0 = perf_counter()
        session = await practice_session_dao.get_detail_by_key(db=db, session_key=session_key)
        if not session:
            raise errors.NotFoundError(msg='会话不存在')
        if session.user_id != user_id:
            raise errors.ForbiddenError(msg='无权访问此会话')
        timings.append(('sql_get_detail_by_key_with_selectin', perf_counter() - t0))

        t0 = perf_counter()
        result = SessionService._build_session_detail_response_dict(session)
        timings.append(('build_response_dict', perf_counter() - t0))

        logger.debug(
            'session_detail_by_key_timing | session_key={} session_id={} user_id={} sq_count={} total={:.1f}ms detail={}',
            session_key,
            session.id,
            user_id,
            len(result['session_questions']),
            (perf_counter() - total_start) * 1000,
            ', '.join(f'{name}={cost * 1000:.1f}ms' for name, cost in timings),
        )
        return result

    @staticmethod
    async def get_latest_session(
        *,
        db: AsyncSession,
        user_id: int,
        session_type: str | None = None,
        bank_id: int | None = None,
        chapter_id: int | None = None,
        source_key: str | None = None,
    ) -> PracticeSession | None:
        """
        获取用户最新的进行中会话

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param session_type: 会话类型
        :param bank_id: 题库 ID
        :param chapter_id: 章节 ID
        :param source_key: 来源签名
        :return:
        """
        return await practice_session_dao.get_latest_session(
            db=db,
            user_id=user_id,
            session_type=session_type,
            bank_id=bank_id,
            chapter_id=chapter_id,
            source_key=source_key,
        )

    @staticmethod
    async def abandon_session(*, db: AsyncSession, session_id: int, user_id: int) -> int:
        """
        放弃练习会话

        :param db: 数据库会话
        :param session_id: 会话 ID
        :param user_id: 用户 ID
        :return:
        """
        await SessionService._get_owned_session(db=db, session_id=session_id, user_id=user_id)

        log.info('Session abandoned: id=%d user=%d', session_id, user_id)
        return await practice_session_dao.abandon_session(db=db, session_id=session_id)

    @staticmethod
    async def delete_session(*, db: AsyncSession, session_id: int, user_id: int) -> int:
        """
        删除练习会话

        :param db: 数据库会话
        :param session_id: 会话 ID
        :param user_id: 用户 ID
        :return:
        """
        await SessionService._get_owned_session(db=db, session_id=session_id, user_id=user_id)

        return await practice_session_dao.delete(db=db, session_id=session_id)

    # ------------------------------------------------------------------
    #  答题记录 Upsert
    # ------------------------------------------------------------------

    @staticmethod
    async def upsert_records(
        *, db: AsyncSession, user_id: int, obj: BatchUpsertSessionQuestionsParam
    ) -> dict[str, Any]:
        """
        批量创建/更新答题记录（基于 session_id + question_id 幂等）

        纯写入路径：仅做鉴权 + 落盘，判题/错题本/统计快照全部由异步任务承担。
        客户端通过 GET /qbank/questions/{qid}/solution 单独获取答案与解析。

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param obj: 批量提交参数
        :return:
        """
        # 鉴权 + 加载 session（题目明细按本次提交的 question_id 单独查询）
        session_stmt = select(PracticeSession).where(PracticeSession.id == obj.session_id)
        session_result = await db.execute(session_stmt)
        session = session_result.scalars().first()
        if not session:
            raise errors.NotFoundError(msg='会话不存在')
        if session.user_id != user_id:
            raise errors.ForbiddenError(msg='无权访问此会话')
        if session.status != 'in_progress':
            raise errors.ForbiddenError(msg='会话已结束，不可作答')

        practice_mode = SessionService._resolve_practice_mode(
            session_type=session.session_type,
            exam_config=session.exam_config,
            source_snapshot=session.source_snapshot,
        )
        allow_judge_now = practice_mode == SessionService.PRACTICE_MODE_PRACTICE

        request_question_ids = list(dict.fromkeys(item.question_id for item in obj.records))
        session_questions = await session_question_dao.get_by_session_question_ids(
            db,
            int(obj.session_id),
            request_question_ids,
        )
        sq_map: dict[int, SessionQuestion] = {sq.question_id: sq for sq in session_questions}

        records_dict: list[dict] = []
        for item in obj.records:
            sq = sq_map.get(item.question_id)
            if not sq:
                continue
            if item.user_answer is None and practice_mode != SessionService.PRACTICE_MODE_MEMORIZE:
                raise errors.RequestError(msg='非背题模式必须提交用户答案')
            if sq.is_correct is not None and practice_mode == SessionService.PRACTICE_MODE_PRACTICE:
                raise errors.ForbiddenError(msg='该题已出答案，不允许修改答案')

            records_dict.append({
                'session_id': obj.session_id,
                'user_id': user_id,
                'question_id': item.question_id,
                'placement_id': sq.placement_id,
                'seq_no': sq.seq_no,
                'question_type': sq.question_type,
                'user_answer': item.user_answer
                if item.user_answer is not None
                else {'mode': 'memorize', 'viewed': True},
                'answer_time': item.answer_time,
                'full_score': sq.full_score,
            })

        result: dict[str, Any] = {
            'upserted_count': len(records_dict),
            'completed_count': session.completed_count,
            'total_count': session.total_count,
            'total_time': session.total_time,
            'progress_percent': (
                Decimal(str(round(session.completed_count / session.total_count * 100, 2)))
                if session.total_count > 0
                else Decimal('0')
            ),
            'records': [],
            'judge_results': [],
        }

        upserted_records: list[SessionQuestion] = []
        if records_dict:
            upserted_records = await session_question_dao.batch_upsert_answer(db=db, records=records_dict)
            # 同步落盘题目进度，保证客户端退出后立即可读到最新进度；判题后的 is_correct 由异步任务再次幂等修正
            await user_bank_progress_dao.upsert_by_record_ids(
                db=db,
                record_ids=[int(record.id) for record in upserted_records],
            )
            completed_count, total_time = await session_question_dao.get_answered_progress_by_session(
                db,
                obj.session_id,
            )
            await practice_session_dao.update_progress(
                db,
                obj.session_id,
                completed_count=completed_count,
                total_time=total_time,
            )
            result['completed_count'] = completed_count
            result['total_time'] = total_time
            result['progress_percent'] = (
                Decimal(str(round(completed_count / session.total_count * 100, 2)))
                if session.total_count > 0
                else Decimal('0')
            )
            result['records'] = [
                {
                    'record_id': int(record.id),
                    'question_id': int(record.question_id),
                    'placement_id': int(record.placement_id),
                    'seq_no': int(record.seq_no),
                }
                for record in upserted_records
            ]

        # 异步副作用：服务端判题 + 错题本 + completed_count + 统计快照
        # 通过 result['_async_payload'] 让 API 层在事务 commit 之后用 BackgroundTasks 投递
        if upserted_records:
            result['_async_payload'] = {
                'user_id': user_id,
                'session_id': obj.session_id,
                'record_ids': [int(r.id) for r in upserted_records],
                'allow_judge_now': allow_judge_now,
                'practice_mode': practice_mode,
            }

        return result

    @staticmethod
    async def get_record(*, db: AsyncSession, record_id: int, user_id: int) -> SessionQuestion:
        """
        获取答题记录详情

        :param db: 数据库会话
        :param record_id: 记录 ID
        :param user_id: 用户 ID
        :return:
        """
        record = await session_question_dao.get(db=db, record_id=record_id)
        if not record:
            raise errors.NotFoundError(msg='记录不存在')
        if record.user_id != user_id:
            raise errors.ForbiddenError(msg='无权访问此记录')

        return record

    @staticmethod
    async def get_session_records(*, db: AsyncSession, session_id: int, user_id: int) -> list[SessionQuestion]:
        """
        获取会话的所有答题记录

        :param db: 数据库会话
        :param session_id: 会话 ID
        :param user_id: 用户 ID
        :return:
        """
        await SessionService._get_owned_session(db=db, session_id=session_id, user_id=user_id)

        return await session_question_dao.get_records_by_session(db=db, session_id=session_id)

    @staticmethod
    def _build_completed_submit_result(session: PracticeSession) -> SubmitPracticeSessionResult:
        """基于已完成会话构建幂等提交结果"""
        return SubmitPracticeSessionResult(
            completed_count=session.completed_count,
            correct_count=session.correct_count,
            wrong_count=session.wrong_count,
            accuracy_rate=session.accuracy_rate,
            score=session.score,
            total_score=session.total_score,
            reward_exp=0,
        )

    @staticmethod
    async def _lock_session_for_submit(*, db: AsyncSession, session_id: int) -> PracticeSession:
        """
        锁定并刷新待提交会话

        :param db: 数据库会话
        :param session_id: 会话 ID
        :return:
        """
        stmt = (
            select(PracticeSession)
            .where(PracticeSession.id == session_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        session = (await db.execute(stmt)).scalars().first()
        if not session:
            raise errors.NotFoundError(msg='会话不存在')
        if session.status not in {'in_progress', 'completed'}:
            raise errors.ForbiddenError(msg='会话状态异常，无法提交')
        return session

    # ------------------------------------------------------------------
    #  提交会话（判题 + 统计 + 错题本 一次事务）
    # ------------------------------------------------------------------

    @staticmethod
    async def _grant_practice_correct_experience(
        *,
        db: AsyncSession,
        user_id: int,
        session_id: int,
        completed_count: int,
        correct_count: int,
        total_time: int,
    ) -> dict[str, int | str | None]:
        """
        按答对题数发放练习经验

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param session_id: 会话 ID
        :param completed_count: 完成题数
        :param correct_count: 答对题数
        :param total_time: 总耗时
        :return:
        """
        if correct_count <= 0:
            return {'reward_exp': 0}

        snapshot = await snapshot_service.load(db, user_id=user_id, ts=timezone.now())
        reward_rule = await experience_rule_dao.get_active_rule(
            db,
            event_code='practice_correct',
            held_entitlement_codes=snapshot.all_entitlement_codes,
        )
        if not reward_rule:
            return {'reward_exp': 0}

        if completed_count < reward_rule.min_practice_count:
            return {'reward_exp': 0}

        if total_time < reward_rule.min_practice_duration:
            return {'reward_exp': 0}

        reward_exp = reward_rule.exp_delta * correct_count
        progress = await experience_service.add_experience(
            db,
            user_id=user_id,
            exp_delta=reward_exp,
            source='practice_correct',
            source_key=f'practice_correct:{session_id}',
            reason=f'完成练习答对 {correct_count} 题奖励',
        )
        return {
            'reward_exp': reward_exp,
            'tier_grade': progress.get('current_grade'),
            'exp': progress.get('total_exp'),
            'available_exp': progress.get('available_exp'),
        }

    @staticmethod
    async def submit_session(
        *,
        db: AsyncSession,
        session_id: int,
        user_id: int,
        obj: SubmitPracticeSessionParam,
    ) -> tuple[SubmitPracticeSessionResult, bool]:
        """
        提交练习会话并统一判题

        流程：读取会话和判题数据 → AI 判分 → 锁会话行 → 批量落库 → 标记完成

        :param db: 数据库会话
        :param session_id: 会话 ID
        :param user_id: 用户 ID
        :param obj: 提交参数
        :return: 提交结果与本次是否首次完成
        """
        # 1. 先读取会话；耗时的 AI 判分完成后再加锁，缩短行锁持有时间。
        session_stmt = select(PracticeSession).where(PracticeSession.id == session_id)
        result = await db.execute(session_stmt)
        session = result.scalars().first()

        if not session:
            raise errors.NotFoundError(msg='会话不存在')
        if session.user_id != user_id:
            raise errors.ForbiddenError(msg='无权操作此会话')
        if session.status == 'completed':
            # 幂等：已提交直接返回上次结果
            return SessionService._build_completed_submit_result(session), False
        if session.status != 'in_progress':
            raise errors.ForbiddenError(msg='会话状态异常，无法提交')

        practice_mode = SessionService._resolve_practice_mode(
            session_type=session.session_type,
            exam_config=session.exam_config,
            source_snapshot=session.source_snapshot,
        )

        # 考试模式：校验时间限制
        if practice_mode == SessionService.PRACTICE_MODE_EXAM and session.exam_config:
            time_limit_minutes = SessionService._parse_positive_int(session.exam_config.get('time_limit'))
            time_limit_seconds = time_limit_minutes * 60
            if time_limit_seconds > 0 and obj.total_time > time_limit_seconds:
                raise errors.ForbiddenError(msg=f'考试已超时（限时 {time_limit_minutes} 分钟）')

        # 2. 查询答题记录 + 题目 + 解析
        records = await session_question_dao.get_records_by_session(db=db, session_id=session_id)
        if not records:
            raise errors.NotFoundError(msg='没有答题记录可提交')

        if practice_mode == SessionService.PRACTICE_MODE_MEMORIZE:
            session = await SessionService._lock_session_for_submit(db=db, session_id=session_id)
            if session.status == 'completed':
                return SessionService._build_completed_submit_result(session), False

            await user_bank_progress_dao.upsert_by_record_ids(
                db=db,
                record_ids=[int(record.id) for record in records],
            )
            completed_count = len(records)
            await practice_session_dao.mark_completed(
                db=db,
                session_id=session_id,
                submit_time=timezone.now(),
                completed_count=completed_count,
                correct_count=0,
                wrong_count=0,
                total_time=obj.total_time,
            )
            return (
                SubmitPracticeSessionResult(
                    completed_count=completed_count,
                    correct_count=0,
                    wrong_count=0,
                    accuracy_rate=Decimal('0'),
                    score=None,
                    total_score=None,
                    reward_exp=0,
                ),
                True,
            )

        pre_submit_unjudged_qids = {record.question_id for record in records if record.is_correct is None}
        question_ids = [r.question_id for r in records]
        stmt = select(Question).where(Question.id.in_(question_ids)).options(selectinload(Question.analyses))
        q_result = await db.execute(stmt)
        question_map: dict[int, Question] = {q.id: q for q in q_result.scalars().all()}

        # 查询 SessionQuestion 快照（取 placement_id / full_score）
        session_questions = await session_question_dao.list_by_session(db=db, session_id=session_id)
        sq_map: dict[int, SessionQuestion] = {sq.question_id: sq for sq in session_questions}

        submit_time = timezone.now()
        judge_version = obj.judge_version or 'rule_v1'

        # 读取用户错题掌握阈值
        from backend.app.question_bank.service.user_settings_service import user_settings_service

        mastery_threshold = await user_settings_service.get_mastery_threshold(db=db, user_id=user_id)
        total_score = Decimal('0')
        earned_score = Decimal('0')
        correct_count = 0
        judged_record_rows: list[dict[str, Any]] = []
        question_stats_rows: list[dict[str, Any]] = []
        wrong_create_rows: list[dict[str, Any]] = []
        wrong_update_rows: list[dict[str, Any]] = []

        existing_wrongs = await wrong_question_dao.list_by_user_and_questions(
            db=db,
            user_id=user_id,
            question_ids=question_ids,
        )
        existing_wrong_by_qid: dict[int, list[WrongQuestionBook]] = {}
        for wrong in existing_wrongs:
            existing_wrong_by_qid.setdefault(wrong.question_id, []).append(wrong)

        subjective_records = [
            record
            for record in records
            if (
                question_map.get(record.question_id)
                and question_map[record.question_id].type in SUBJECTIVE_QUESTION_TYPES
            )
        ]
        subjective_eval_map: dict[int, Any] = {}
        if subjective_records:
            subjective_eval_map = await practice_ai_evaluation_service.evaluate_subjective_records(
                db=db,
                session=session,
                records=subjective_records,
                question_map=question_map,
                trigger_source='auto',
                force_regenerate=True,
                judge_version=judge_version,
            )
            failed_subjective_records = [
                record.seq_no
                for record in subjective_records
                if (record.id not in subjective_eval_map or subjective_eval_map[record.id].status != 'succeeded')
            ]
            if failed_subjective_records:
                seq_text = '、'.join(str(item) for item in failed_subjective_records[:10])
                raise errors.RequestError(msg=f'主观题 AI 判分失败，请稍后重试。题序：{seq_text}')

        # 3. 遍历判题
        for record in records:
            question = question_map.get(record.question_id)
            if not question:
                continue

            # 取默认解析
            analysis = None
            if question.analyses:
                analysis = next((a for a in question.analyses if a.is_default), question.analyses[0])

            # 计算得分
            sq = sq_map.get(record.question_id)
            full = sq.full_score if sq else record.full_score
            if question.type in SUBJECTIVE_QUESTION_TYPES:
                evaluation = subjective_eval_map.get(record.id)
                if not evaluation or evaluation.status != 'succeeded':
                    raise errors.RequestError(msg=f'题目 {record.seq_no} AI 判分失败，请稍后重试')
                score = evaluation.score or Decimal('0')
                full = evaluation.max_score or full
                is_correct = score >= (full * Decimal('0.60'))
                record_judge_version = evaluation.prompt_version or 'subjective_eval_v1'
            else:
                is_correct = False
                if analysis and analysis.answer_data:
                    is_correct = question_service.check_answer(
                        question.type,
                        record.user_answer,
                        analysis.answer_data,
                    )
                score = full if is_correct else Decimal('0')
                record_judge_version = judge_version
            total_score += full
            earned_score += score
            if is_correct:
                correct_count += 1

            placement_id = sq.placement_id if sq else record.placement_id
            judged_record_rows.append({
                'session_id': record.session_id,
                'user_id': record.user_id,
                'question_id': record.question_id,
                'placement_id': placement_id,
                'seq_no': record.seq_no,
                'question_type': question.type,
                'user_answer': record.user_answer,
                'answer_time': record.answer_time,
                'full_score': full,
                'is_correct': is_correct,
                'score': score,
                'judged_at': submit_time,
                'judge_version': record_judge_version,
            })

            # 3a. 提取选中的选项编码
            selected_codes = question_service.parse_selected_option_codes(
                question_type=question.type,
                user_answer=record.user_answer,
            )

            option_select_counts: dict[str, int] | None = None
            if question.type in ['single', 'multiple', 'judgement'] and selected_codes:
                option_select_counts = {}
                for option_code in selected_codes:
                    current_count = option_select_counts.get(option_code, 0)
                    option_select_counts[option_code] = current_count + 1

            # 有效数据过滤（answer_time < 3s 视为秒杀）
            is_valid = record.answer_time is not None and record.answer_time >= INVALID_TIME_THRESHOLD

            question_stats_rows.append({
                'question_id': record.question_id,
                'attempt_count': 1,
                'correct_count': 1 if is_correct else 0,
                'answer_time_total': record.answer_time,
                'option_select_counts': option_select_counts,
                'valid_attempt_count': 1 if is_valid else 0,
                'valid_correct_count': 1 if (is_valid and is_correct) else 0,
                'valid_answer_time_total': record.answer_time if is_valid else Decimal('0'),
            })

            # 3c. 汇总错题本（按 question_id 宽松匹配，忽略 placement）
            should_update_wrong_book = (
                question.type in SUBJECTIVE_QUESTION_TYPES or record.question_id in pre_submit_unjudged_qids
            )
            if should_update_wrong_book:
                existing_wrong_list = existing_wrong_by_qid.get(record.question_id, [])
                if not is_correct:
                    if existing_wrong_list:
                        for existing_wrong in existing_wrong_list:
                            wrong_update_rows.append({
                                'filter_wrong_id': existing_wrong.id,
                                'set_wrong_count': existing_wrong.wrong_count + 1,
                                'set_correct_streak': 0,
                                'set_last_wrong_time': submit_time,
                                'set_last_practice_time': existing_wrong.last_practice_time,
                            })
                    else:
                        wrong_create_rows.append({
                            'user_id': user_id,
                            'question_id': record.question_id,
                            'placement_id': placement_id,
                            'wrong_count': 1,
                            'correct_streak': 0,
                            'first_wrong_time': submit_time,
                            'last_wrong_time': submit_time,
                            'last_practice_time': None,
                            'created_by': user_id,
                        })
                else:
                    for existing_wrong in existing_wrong_list:
                        new_streak = existing_wrong.correct_streak + 1
                        wrong_update_rows.append({
                            'filter_wrong_id': existing_wrong.id,
                            'set_wrong_count': existing_wrong.wrong_count,
                            'set_correct_streak': new_streak,
                            'set_last_wrong_time': existing_wrong.last_wrong_time,
                            'set_last_practice_time': submit_time,
                        })

        # 4. 写入前锁定并刷新会话，防止并发重复提交。
        session = await SessionService._lock_session_for_submit(db=db, session_id=session_id)
        if session.status == 'completed':
            return SessionService._build_completed_submit_result(session), False

        # 5. 批量落库
        if judged_record_rows:
            judged_records = await session_question_dao.batch_upsert_answer(db=db, records=judged_record_rows)
            await user_bank_progress_dao.upsert_by_record_ids(
                db=db,
                record_ids=[int(record.id) for record in judged_records],
            )

        if question_stats_rows:
            await question_statistics_dao.batch_update_stats(db=db, items=question_stats_rows)

        if wrong_create_rows:
            await wrong_question_dao.batch_create(db=db, rows=wrong_create_rows)

        if wrong_update_rows:
            await wrong_question_dao.batch_update(db=db, rows=wrong_update_rows)

        # 5b. 批量更新掌握状态
        from backend.app.question_bank.service.mastery_service import mastery_service

        await mastery_service.apply_answer_batch(
            db=db,
            user_id=user_id,
            answers=[(int(row['question_id']), bool(row['is_correct'])) for row in judged_record_rows],
            mastery_threshold=mastery_threshold,
        )

        completed_count = len(records)
        wrong_count = completed_count - correct_count

        # 6. 标记会话完成
        await practice_session_dao.mark_completed(
            db=db,
            session_id=session_id,
            submit_time=submit_time,
            completed_count=completed_count,
            correct_count=correct_count,
            wrong_count=wrong_count,
            total_time=obj.total_time,
            score=earned_score if earned_score > 0 else None,
            total_score=total_score if total_score > 0 else None,
        )

        # 7. 增量更新用户统计快照（只统计提交前尚未判题的记录，避免与异步任务重复）
        # 刷题模式：每题 Celery process_record_side_effects 已增量过 → 提交前已判 → 跳过
        # 考试模式 / 主观题手动未批改：提交前仍未判 → 此刻首次判 → 增量
        if pre_submit_unjudged_qids:
            newly_rows = [row for row in judged_record_rows if row['question_id'] in pre_submit_unjudged_qids]
            await user_practice_stats_dao.increment(
                db=db,
                user_id=user_id,
                answered=len(newly_rows),
                correct=sum(1 for row in newly_rows if row['is_correct']),
                duration=sum(row.get('answer_time', 0) or 0 for row in newly_rows),
            )

        reward_progress = await SessionService._grant_practice_correct_experience(
            db=db,
            user_id=user_id,
            session_id=session_id,
            completed_count=completed_count,
            correct_count=correct_count,
            total_time=obj.total_time,
        )
        check_in_result = await check_in_service.try_auto_check_in(db=db, user_id=user_id)
        practice_reward_exp = int(reward_progress.get('reward_exp') or 0)
        check_in_reward_exp = int(check_in_result.reward_exp) if check_in_result else 0
        reward_exp = practice_reward_exp + check_in_reward_exp
        latest_progress: dict[str, int | str | None] = reward_progress
        if check_in_result and check_in_result.reward_exp > 0:
            latest_progress = {
                'tier_grade': check_in_result.tier_grade,
                'exp': check_in_result.exp,
                'available_exp': check_in_result.available_exp,
            }

        log.info(
            'Session submitted: id=%d user=%d completed=%d correct=%d wrong=%d score=%s reward_exp=%s check_in=%s',
            session_id,
            user_id,
            completed_count,
            correct_count,
            wrong_count,
            earned_score,
            reward_exp,
            bool(check_in_result),
        )

        return (
            SubmitPracticeSessionResult(
                completed_count=completed_count,
                correct_count=correct_count,
                wrong_count=wrong_count,
                accuracy_rate=(
                    Decimal(str(round(correct_count / completed_count * 100, 2)))
                    if completed_count > 0
                    else Decimal('0')
                ),
                score=earned_score if earned_score > 0 else None,
                total_score=total_score if total_score > 0 else None,
                reward_exp=reward_exp,
                practice_reward_exp=practice_reward_exp,
                check_in_reward_exp=check_in_reward_exp,
                is_auto_checked_in=bool(check_in_result),
                check_in_streak=check_in_result.check_in_streak if check_in_result else None,
                tier_grade=latest_progress.get('tier_grade'),
                exp=latest_progress.get('exp'),
                available_exp=latest_progress.get('available_exp'),
            ),
            True,
        )

    # ------------------------------------------------------------------
    #  报告 / 解析
    # ------------------------------------------------------------------

    @staticmethod
    async def get_session_report(*, db: AsyncSession, session_id: int, user_id: int) -> SessionReport:
        """
        获取会话答题报告

        :param db: 数据库会话
        :param session_id: 会话 ID
        :param user_id: 用户 ID
        :return:
        """
        session = await SessionService._get_owned_session_detail(
            db=db,
            session_id=session_id,
            user_id=user_id,
        )

        # 构造答题卡 + 错题列表
        answer_items: list[AnswerCardItem] = []
        wrong_question_ids: list[int] = []

        for sq in session.session_questions:
            if sq.user_answer is None:
                status = 'unanswered'
                answer_time = 0
            elif sq.is_correct:
                status = 'correct'
                answer_time = sq.answer_time or 0
            else:
                status = 'wrong'
                answer_time = sq.answer_time or 0
                wrong_question_ids.append(sq.question_id)

            answer_items.append(
                AnswerCardItem(
                    seq_no=sq.seq_no,
                    question_id=sq.question_id,
                    placement_id=sq.placement_id,
                    status=status,
                    answer_time=answer_time,
                    chapter_name=sq.placement.chapter.name if sq.placement and sq.placement.chapter else None,
                )
            )

        unanswered_count = session.total_count - session.completed_count

        return SessionReport(
            session_id=session.id,
            session_type=session.session_type,
            status=session.status,
            bank_id=session.bank_id,
            chapter_id=session.chapter_id,
            total_count=session.total_count,
            completed_count=session.completed_count,
            correct_count=session.correct_count,
            wrong_count=session.wrong_count,
            unanswered_count=unanswered_count,
            accuracy_rate=session.accuracy_rate,
            total_time=session.total_time,
            answer_items=answer_items,
            wrong_question_ids=wrong_question_ids,
        )

    @staticmethod
    async def get_session_solution(*, db: AsyncSession, session_id: int, user_id: int) -> list[dict]:
        """
        获取会话全部题目的答案与解析

        :param db: 数据库会话
        :param session_id: 会话 ID
        :param user_id: 用户 ID
        :return: 逐题解析列表
        """
        await SessionService._get_owned_session(
            db=db,
            session_id=session_id,
            user_id=user_id,
        )
        session_questions = await session_question_dao.list_by_session(db=db, session_id=session_id)

        # 批量查题目 + 解析 + 选项
        question_ids = [sq.question_id for sq in session_questions]
        if not question_ids:
            return []

        stmt = (
            select(Question)
            .where(Question.id.in_(question_ids))
            .options(
                load_only(Question.id, Question.stem, Question.type, Question.options),
                selectinload(Question.analyses).load_only(
                    QuestionAnalysis.id,
                    QuestionAnalysis.question_id,
                    QuestionAnalysis.answer_data,
                    QuestionAnalysis.content,
                    QuestionAnalysis.is_default,
                ),
            )
        )
        result = await db.execute(stmt)
        question_map: dict[int, Question] = {q.id: q for q in result.scalars().all()}

        solutions: list[dict] = []
        for sq in session_questions:
            q = question_map.get(sq.question_id)
            if not q:
                continue

            analysis = None
            if q.analyses:
                analysis = next((a for a in q.analyses if a.is_default), q.analyses[0])

            correct_answer = None
            if analysis and analysis.answer_data:
                correct_answer = analysis.answer_data.get('correct')

            options_data = question_service.build_options_data(question=q)
            options_list = list(options_data.values()) if options_data and isinstance(options_data, dict) else None

            solutions.append({
                'seq_no': sq.seq_no,
                'question_id': q.id,
                'placement_id': sq.placement_id,
                'content': q.stem,
                'type': q.type,
                'options': options_list,
                'correct_answer': correct_answer,
                'analysis': analysis.content if analysis else None,
                'user_answer': sq.user_answer,
                'is_correct': sq.is_correct,
                'score': sq.score,
                'full_score': sq.full_score,
                'answer_time': sq.answer_time or 0,
            })

        return solutions

    @staticmethod
    async def get_session_questions_with_materials(
        *, db: AsyncSession, session_key: str, user_id: int
    ) -> dict[str, Any]:
        """
        获取会话题目静态内容和去重材料

        :param db: 数据库会话
        :param session_key: 会话唯一标识
        :param user_id: 用户 ID
        :return: 包含 questions 和 materials 的字典
        """
        # 分段计时埋点（性能诊断用，定位瓶颈后可移除）
        timings: list[tuple[str, float]] = []
        total_start = perf_counter()

        # 1. 一条 SQL 同时完成 key→id 解析 + 归属校验（替代旧的 _resolve_session_id + _get_owned_session 两次 SQL）
        t0 = perf_counter()
        session = await practice_session_dao.get_by_key(db=db, session_key=session_key)
        if not session:
            raise errors.NotFoundError(msg='会话不存在')
        if session.user_id != user_id:
            raise errors.ForbiddenError(msg='无权访问此会话')
        session_id = session.id
        timings.append(('sql1_resolve_session_by_key', perf_counter() - t0))

        t0 = perf_counter()
        session_questions = await session_question_dao.list_by_session(db=db, session_id=session_id)
        timings.append(('sql2_list_session_questions', perf_counter() - t0))
        if not session_questions:
            logger.debug(
                'session_questions_timing | session_id={} user_id={} sq_count=0 total={:.1f}ms detail={}',
                session_id,
                user_id,
                (perf_counter() - total_start) * 1000,
                ', '.join(f'{name}={cost * 1000:.1f}ms' for name, cost in timings),
            )
            return {'questions': [], 'materials': []}

        placement_ids = [sq.placement_id for sq in session_questions if sq.placement_id]
        placement_bank_map: dict[int, int] = {}
        t0 = perf_counter()
        if placement_ids:
            placement_stmt = select(QuestionPlacement.id, QuestionPlacement.bank_id).where(
                QuestionPlacement.id.in_(placement_ids)
            )
            placement_rows = (await db.execute(placement_stmt)).all()
            placement_bank_map = {row.id: row.bank_id for row in placement_rows}
        timings.append(('sql3_placement_bank_map', perf_counter() - t0))

        bank_ids = sorted(set(placement_bank_map.values()))
        bank_info_map: dict[int, Any] = {}
        bank_material_map: dict[int, list[int]] = {}
        t0 = perf_counter()
        if bank_ids:
            from backend.app.question_bank.model.bank import QuestionBank
            from backend.app.question_bank.model.question import QuestionMaterial

            bank_stmt = select(QuestionBank).where(QuestionBank.id.in_(bank_ids))
            bank_rows = (await db.execute(bank_stmt)).scalars().all()
            bank_info_map = {bank.id: bank for bank in bank_rows}

            # Cut #3：仅当 session 涉及"申论"题库时才预取材料 ID
            # 非申论 session 完全跳过这条 SQL（典型 50-100ms 收益）
            shenlun_bank_ids = [
                bid
                for bid, bank in bank_info_map.items()
                if '申论' in str(getattr(bank, 'name', '') or '') or '申论' in str(getattr(bank, 'desc', '') or '')
            ]
            if shenlun_bank_ids:
                bank_material_stmt = (
                    select(QuestionMaterial.id, QuestionMaterial.bank_id)
                    .where(
                        QuestionMaterial.bank_id.in_(shenlun_bank_ids),
                        QuestionMaterial.is_active.is_(True),
                    )
                    .order_by(
                        QuestionMaterial.bank_id.asc(),
                        QuestionMaterial.sort_order.asc(),
                        QuestionMaterial.id.asc(),
                    )
                )
                bank_material_rows = (await db.execute(bank_material_stmt)).all()
                for row in bank_material_rows:
                    bank_material_map.setdefault(row.bank_id, []).append(row.id)
        timings.append(('sql4_bank_and_bank_materials', perf_counter() - t0))

        # 2. 批量查询题目详情（含选项和材料关联）
        t0 = perf_counter()
        question_ids = [sq.question_id for sq in session_questions]
        stmt = (
            select(Question)
            .where(Question.id.in_(question_ids))
            .options(
                selectinload(Question.materials),
            )
        )
        result = await db.execute(stmt)
        question_map: dict[int, Question] = {q.id: q for q in result.unique().scalars().all()}
        timings.append(('sql5_questions_with_materials_relation', perf_counter() - t0))

        # 3. 构建题目列表（按 seq_no 排序）
        t0 = perf_counter()
        questions_list: list[dict[str, Any]] = []
        all_material_ids: set[int] = set()
        for sq in session_questions:
            question = question_map.get(sq.question_id)
            if not question:
                continue

            # 构建选项数组
            options_list = [
                {
                    'option_code': option['option_code'],
                    'content': option['content'],
                }
                for option in question_service.normalize_options(question.options, active_only=True)
            ]

            # 提取材料 ID 列表
            material_ids = [m.id for m in question.materials] if question.materials else []
            if not material_ids:
                placement_bank_id = placement_bank_map.get(sq.placement_id or 0)
                bank_info = bank_info_map.get(placement_bank_id or 0)
                bank_name = str(getattr(bank_info, 'name', '') or '')
                bank_desc = str(getattr(bank_info, 'desc', '') or '')
                if '申论' in bank_name or '申论' in bank_desc:
                    material_ids = list(bank_material_map.get(placement_bank_id or 0, []))

            all_material_ids.update(material_ids)

            questions_list.append({
                'seq_no': sq.seq_no,
                'question_id': question.id,
                'type': question.type,
                'stem': question.stem,
                'options': options_list,
                'material_ids': material_ids,
                'knowledge_point': question.knowledge_point,
                'difficulty': question.difficulty,
            })
        timings.append(('build_questions_list', perf_counter() - t0))

        # 4. 去重并批量查询材料
        t0 = perf_counter()
        materials_list: list[dict[str, Any]] = []
        if all_material_ids:
            from backend.app.question_bank.model.question import QuestionMaterial

            material_ids_list = list(all_material_ids)
            materials_stmt = select(QuestionMaterial).where(QuestionMaterial.id.in_(material_ids_list))
            materials_result = await db.execute(materials_stmt)
            materials = materials_result.scalars().all()

            for material in materials:
                materials_list.append({
                    'id': material.id,
                    'title': material.title,
                    'content': material.content,
                })
        timings.append(('sql6_materials_full', perf_counter() - t0))

        # 5. 批量解析知识点 code → 显示名称
        t0 = perf_counter()
        all_kp_codes: set[str] = set()
        for q_item in questions_list:
            kp_raw = q_item.get('knowledge_point')
            if isinstance(kp_raw, list):
                for kp in kp_raw:
                    if isinstance(kp, str) and kp.strip():
                        all_kp_codes.add(kp.strip())
        if all_kp_codes:
            code_map = await knowledge_point_service.resolve_codes_to_names(db, list(all_kp_codes))
            for q_item in questions_list:
                kp_raw = q_item.get('knowledge_point')
                if isinstance(kp_raw, list):
                    q_item['knowledge_point_display'] = [
                        code_map.get(kp.strip(), kp.strip()) for kp in kp_raw if isinstance(kp, str) and kp.strip()
                    ]
        timings.append(('sql7_resolve_kp_codes', perf_counter() - t0))

        logger.debug(
            'session_questions_timing | session_id={} user_id={} sq_count={} q_count={} mat_count={} total={:.1f}ms detail={}',
            session_id,
            user_id,
            len(session_questions),
            len(questions_list),
            len(materials_list),
            (perf_counter() - total_start) * 1000,
            ', '.join(f'{name}={cost * 1000:.1f}ms' for name, cost in timings),
        )
        return {
            'questions': questions_list,
            'materials': materials_list,
        }

    # ------------------------------------------------------------------
    #  列表查询（包装 DAO，避免 API 层直接访问 DAO）
    # ------------------------------------------------------------------

    @staticmethod
    async def get_session_list_select(
        *,
        db: AsyncSession,
        user_id: int,
        session_type: str | None = None,
        status: str | None = None,
        cat_id: int | None = None,
        kp_cat_id: int | None = None,
    ) -> select:
        """
        获取会话列表查询表达式

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param session_type: 会话类型
        :param status: 状态
        :param cat_id: 题库目录分类 ID
        :param kp_cat_id: 知识点分类 ID
        :return:
        """
        resolved_bank_ids = None
        category_filter = await category_filter_service.get_question_filter(
            db=db,
            cat_id=cat_id,
            kp_cat_id=kp_cat_id,
        )
        if category_filter and cat_id is not None:
            resolved_bank_ids = list(category_filter.bank_ids)

        return await practice_session_dao.get_select(
            user_id=user_id,
            session_type=session_type,
            bank_ids=resolved_bank_ids,
            status=status,
        )

    @staticmethod
    async def get_record_list_select(
        *,
        user_id: int,
        session_id: int | None = None,
        question_id: int | None = None,
    ) -> select:
        """
        获取答题记录列表查询表达式

        :param user_id: 用户 ID
        :param session_id: 会话 ID
        :param question_id: 题目 ID
        :return:
        """
        return await session_question_dao.get_select(
            user_id=user_id,
            session_id=session_id,
            question_id=question_id,
        )

    @classmethod
    async def _filter_question_ids_by_knowledge_point(
        cls,
        *,
        db: AsyncSession,
        question_ids: list[int],
        knowledge_point: list[Any] | None,
    ) -> list[int]:
        """
        根据知识点过滤题目 ID 列表

        :param db: 数据库会话
        :param question_ids: 题目 ID 列表
        :param knowledge_point: 知识点条件
        :return:
        """
        if not question_ids or not knowledge_point:
            return question_ids

        kp_ids, kp_names = cls._normalize_knowledge_point_terms(knowledge_point)
        if not kp_ids and not kp_names:
            return []

        stmt = select(Question.id).where(
            Question.id.in_(question_ids),
            or_(*cls._build_knowledge_point_conditions(kp_ids=kp_ids, kp_names=kp_names)),
        )
        matched_question_ids = set((await db.execute(stmt)).scalars().all())
        return [question_id for question_id in question_ids if question_id in matched_question_ids]

    @classmethod
    async def create_unified_session(
        cls,
        *,
        db: AsyncSession,
        user_id: int,
        obj: CreatePracticeSessionParam,
    ) -> PracticeSession:
        """
        统一创建练习会话

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param obj: 创建会话参数
        :return:
        """
        unified_timings: list[tuple[str, float]] = []
        unified_total_start = perf_counter()

        t0 = perf_counter()
        # Cut #4a: 仅当调用方未提供 bank_id 时才兜底解析
        # POST /sessions 路由层已经做过 membership_service.resolve_bank_context_for_chapter
        # bank_id 已被填回 obj，这里再做一次纯属浪费 ~113ms
        if obj.chapter_id is not None and obj.bank_id is None:
            from backend.app.question_bank.service.membership_service import membership_service

            # 复习类会话（错题/收藏/笔记）跳过题库权限校验，只做 chapter → bank 上下文解析
            is_review_session = obj.session_type in {'wrong', 'favorite', 'note'}
            obj.bank_id = await membership_service.resolve_bank_context_for_chapter(
                db=db,
                chapter_id=obj.chapter_id,
                bank_id=obj.bank_id,
                user_id=None if is_review_session else user_id,
            )
        unified_timings.append(('uni_resolve_bank_ctx', perf_counter() - t0))

        t0 = perf_counter()
        obj.exam_config = cls._normalize_exam_config(obj.session_type, obj.exam_config)
        source_snapshot = cls._build_session_source_snapshot(obj)
        source_key = cls._build_session_source_key(source_snapshot)
        unified_timings.append(('uni_build_source_key', perf_counter() - t0))

        t0 = perf_counter()
        latest_session = await practice_session_dao.get_latest_session(
            db=db,
            user_id=user_id,
            session_type=obj.session_type,
            bank_id=obj.bank_id,
            chapter_id=obj.chapter_id,
            source_key=source_key,
        )
        unified_timings.append(('uni_get_latest_session', perf_counter() - t0))
        if latest_session:
            logger.debug(
                'create_unified_session_timing | user_id={} session_type={} branch=reused total={:.1f}ms detail={}',
                user_id,
                obj.session_type,
                (perf_counter() - unified_total_start) * 1000,
                ', '.join(f'{name}={cost * 1000:.1f}ms' for name, cost in unified_timings),
            )
            return latest_session

        if obj.session_type not in {'wrong', 'favorite', 'note'}:
            t0 = perf_counter()
            new_session = await cls.create_session(
                db=db,
                user_id=user_id,
                obj=obj,
                source_key=source_key,
                source_snapshot=source_snapshot,
            )
            unified_timings.append(('uni_create_session', perf_counter() - t0))
            logger.debug(
                'create_unified_session_timing | user_id={} session_type={} branch=normal total={:.1f}ms detail={}',
                user_id,
                obj.session_type,
                (perf_counter() - unified_total_start) * 1000,
                ', '.join(f'{name}={cost * 1000:.1f}ms' for name, cost in unified_timings),
            )
            return new_session

        t0 = perf_counter()
        collect_result = await question_selector_service.collect_question_ids(
            db=db,
            params=cls._build_collect_param(obj=obj, source_type=obj.session_type),
            user_id=user_id,
        )
        unified_timings.append(('uni_collect_question_ids_review', perf_counter() - t0))
        question_ids = collect_result.question_ids

        t0 = perf_counter()
        chapter_scope_ids = await question_selector_service.resolve_chapter_scope_ids(
            db=db,
            chapter_id=obj.chapter_id,
        )
        unified_timings.append(('uni_resolve_chapter_scope', perf_counter() - t0))

        t0 = perf_counter()
        placements = await cls._query_placements_by_question_ids(
            db=db,
            question_ids=question_ids,
            bank_id=obj.bank_id,
            chapter_id=obj.chapter_id,
            chapter_scope_ids=chapter_scope_ids,
        )
        unified_timings.append(('uni_query_placements_review', perf_counter() - t0))

        t0 = perf_counter()
        new_session = await cls._create_session_snapshot(
            db=db,
            user_id=user_id,
            session_type=obj.session_type,
            placements=placements,
            practice_name=obj.practice_name,
            bank_id=obj.bank_id,
            chapter_id=obj.chapter_id,
            exam_config=obj.exam_config,
            source_key=source_key,
            source_snapshot=source_snapshot,
            shuffle=obj.shuffle,
            limit=obj.limit,
        )
        unified_timings.append(('uni_create_snapshot_review', perf_counter() - t0))

        logger.debug(
            'create_unified_session_timing | user_id={} session_type={} branch=review total={:.1f}ms detail={}',
            user_id,
            obj.session_type,
            (perf_counter() - unified_total_start) * 1000,
            ', '.join(f'{name}={cost * 1000:.1f}ms' for name, cost in unified_timings),
        )
        return new_session


session_service: SessionService = SessionService()
