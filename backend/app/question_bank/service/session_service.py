#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio
import hashlib
import json
import logging
import random

from decimal import Decimal
from typing import Any

from sqlalchemy import cast, func, or_, select, update
from sqlalchemy.dialects.postgresql import JSONB as PGJSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, load_only, selectinload

from backend.app.membership.crud.crud_experience_rule import membership_experience_rule_dao
from backend.app.membership.service.experience_service import membership_experience_service
from backend.app.question_bank.crud.crud_practice_record import practice_record_dao
from backend.app.question_bank.crud.crud_practice_session import practice_session_dao
from backend.app.question_bank.crud.crud_question import (
    question_option_stats_dao,
    question_statistics_dao,
)
from backend.app.question_bank.crud.crud_session_question import session_question_dao
from backend.app.question_bank.crud.crud_user_practice_stats import user_practice_stats_dao
from backend.app.question_bank.crud.crud_wrong_question import wrong_question_dao
from backend.app.question_bank.model import (
    OptionContent,
    PracticeRecord,
    PracticeSession,
    Question,
    QuestionAnalysis,
    QuestionBank,
    QuestionChapter,
    QuestionOption,
    QuestionPlacement,
    SessionQuestion,
    WrongQuestionBook,
)
from backend.app.question_bank.schema.practice import (
    AnswerCardItem,
    BatchUpsertPracticeRecordsParam,
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
from backend.app.question_bank.service.check_in_service import check_in_service
from backend.app.question_bank.service.question_selector_service import question_selector_service
from backend.app.question_bank.service.question_service import question_service
from backend.app.question_bank.service.study_domain_service import study_domain_service
from backend.common.exception import errors
from backend.database.db import async_db_session
from backend.utils.timezone import timezone

log = logging.getLogger(__name__)


class SessionService:
    """练习会话服务类（唯一刷题写入入口）"""

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
        return f'{value[:max_length - 1]}…'

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
        if mode:
            return mode
        if session_type == 'exam':
            return 'exam'
        return 'practice'

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
            content_status=10,
            is_active=True if source_type == 'placement' else None,
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
        chapter_id: int | None = None,
        chapter_scope_ids: list[int] | None = None,
    ) -> QuestionPlacement | None:
        """
        按题库/章节上下文选择挂载

        :param placements: 候选挂载列表
        :param bank_id: 题库 ID
        :param chapter_id: 章节 ID
        :param chapter_scope_ids: 章节及子章节 ID 列表
        :return:
        """
        if not placements:
            return None

        sorted_candidates = sorted(placements, key=lambda item: (item.sort_order, item.id))

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
        collect_result = await question_selector_service.collect_question_ids(
            db=db,
            params=cls._build_collect_param(obj=obj, source_type='placement'),
            user_id=user_id,
        )
        chapter_scope_ids = await question_selector_service.resolve_chapter_scope_ids(
            db=db,
            chapter_id=obj.chapter_id,
        )
        placements = await cls._query_placements_by_question_ids(
            db=db,
            question_ids=collect_result.question_ids,
            bank_id=obj.bank_id,
            chapter_id=obj.chapter_id,
            chapter_scope_ids=chapter_scope_ids,
        )

        return await cls._create_session_snapshot(
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
        placements = await cls._query_placements_by_question_ids(
            db=db,
            question_ids=obj.question_ids,
            bank_id=obj.bank_id,
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
    async def _get_question_type_map(
        *, db: AsyncSession, question_ids: list[int]
    ) -> dict[int, str]:
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
        chapter_id: int | None = None,
        chapter_scope_ids: list[int] | None = None,
    ) -> list[QuestionPlacement]:
        """
        根据题目 ID 列表反查挂载

        :param db: 数据库会话
        :param question_ids: 题目 ID 列表
        :param bank_id: 题库 ID
        :param chapter_id: 篇章 ID
        :param chapter_scope_ids: 篇章及子篇章 ID 列表
        :return:
        """
        if not question_ids:
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
                chapter_id=chapter_id,
                chapter_scope_ids=chapter_scope_ids,
            )
            if matched_placement is not None:
                placements.append(matched_placement)

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
        if not placements:
            raise errors.NotFoundError(msg='没有可用的题目')

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

        question_type_map = await SessionService._get_question_type_map(
            db=db,
            question_ids=list({placement.question_id for placement in placements}),
        )
        total_score = sum(placement.score or Decimal('0') for placement in placements)

        session_dict = {
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
        new_session = await practice_session_dao.create(db=db, obj_dict=session_dict)

        session_question_items: list[dict[str, Any]] = []
        for index, placement in enumerate(placements, start=1):
            session_question_items.append({
                'seq_no': index,
                'question_id': placement.question_id,
                'placement_id': placement.id,
                'question_type': question_type_map.get(placement.question_id, 'single'),
                'full_score': placement.score or Decimal('0'),
            })
        await session_question_dao.batch_create(
            db=db,
            session_id=new_session.id,
            items=session_question_items,
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
    async def _get_owned_session(
        *, db: AsyncSession, session_id: int, user_id: int
    ) -> PracticeSession:
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
    async def _get_owned_session_detail(
        *, db: AsyncSession, session_id: int, user_id: int
    ) -> PracticeSession:
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
    async def get_session_detail(*, db: AsyncSession, session_id: int, user_id: int) -> dict:
        """
        获取练习会话详情（含会话题目快照和答题记录）

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

        # 计算章节分布统计 & 构造 session_questions 数据
        chapter_distribution = {}
        session_questions_data = []

        for sq in session.session_questions:
            # 获取章节信息
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

                # 统计章节分布
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
                # 未分类章节
                if None not in chapter_distribution:
                    chapter_distribution[None] = {
                        'chapter_id': None,
                        'chapter_name': '未分类',
                        'chapter_code': None,
                        'question_count': 0,
                    }
                chapter_distribution[None]['question_count'] += 1

            # 构造题目数据（包含 chapter）
            session_questions_data.append({
                'id': sq.id,
                'session_id': sq.session_id,
                'seq_no': sq.seq_no,
                'question_id': sq.question_id,
                'placement_id': sq.placement_id,
                'question_type': sq.question_type,
                'full_score': sq.full_score,
                'chapter': chapter_data,
            })

        # 转换为列表并按题目数量降序排序
        distribution_list = sorted(
            chapter_distribution.values(),
            key=lambda x: x['question_count'],
            reverse=True,
        )

        # 构造返回数据
        return {
            **session.__dict__,
            'chapter_distribution': distribution_list,
            'session_questions': session_questions_data,
            'records': session.records,
        }

    @staticmethod
    async def get_latest_session(
        *, db: AsyncSession, user_id: int, session_type: str | None = None,
        bank_id: int | None = None, chapter_id: int | None = None, source_key: str | None = None
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
            db=db, user_id=user_id, session_type=session_type,
            bank_id=bank_id, chapter_id=chapter_id, source_key=source_key,
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
        *, db: AsyncSession, user_id: int, obj: BatchUpsertPracticeRecordsParam
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
        # 鉴权 + 加载 session_questions（用于过滤合法题目 + 取 placement_id / seq_no / full_score）
        session_stmt = (
            select(PracticeSession)
            .where(PracticeSession.id == obj.session_id)
            .options(selectinload(PracticeSession.session_questions))
        )
        session_result = await db.execute(session_stmt)
        session = session_result.scalars().first()
        if not session:
            raise errors.NotFoundError(msg='会话不存在')
        if session.user_id != user_id:
            raise errors.ForbiddenError(msg='无权访问此会话')
        if session.status != 'in_progress':
            raise errors.ForbiddenError(msg='会话已结束，不可作答')

        # 考试模式不允许异步任务判题（保持原 allow_judge_now 语义）
        allow_judge_now = obj.judge_now and session.session_type != 'exam'

        sq_map: dict[int, SessionQuestion] = {sq.question_id: sq for sq in session.session_questions}

        records_dict: list[dict] = []
        for item in obj.records:
            sq = sq_map.get(item.question_id)
            if not sq:
                continue

            records_dict.append({
                'session_id': obj.session_id,
                'user_id': user_id,
                'question_id': item.question_id,
                'placement_id': sq.placement_id,
                'seq_no': sq.seq_no,
                'user_answer': item.user_answer,
                'answer_time': item.answer_time,
                'full_score': sq.full_score,
            })

        result: dict[str, Any] = {'upserted_count': len(records_dict), 'judge_results': []}

        upserted_records: list[PracticeRecord] = []
        if records_dict:
            upserted_records = await practice_record_dao.batch_upsert(db=db, records=records_dict)

        # 异步副作用：服务端判题 + 错题本 + completed_count + 统计快照
        # 通过 result['_async_payload'] 让 API 层在事务 commit 之后用 BackgroundTasks 投递
        if upserted_records:
            result['_async_payload'] = {
                'user_id': user_id,
                'session_id': obj.session_id,
                'record_ids': [int(r.id) for r in upserted_records],
                'allow_judge_now': allow_judge_now,
            }

        return result

    @staticmethod
    async def get_record(*, db: AsyncSession, record_id: int, user_id: int) -> PracticeRecord:
        """
        获取答题记录详情

        :param db: 数据库会话
        :param record_id: 记录 ID
        :param user_id: 用户 ID
        :return:
        """
        record = await practice_record_dao.get(db=db, record_id=record_id)
        if not record:
            raise errors.NotFoundError(msg='记录不存在')
        if record.user_id != user_id:
            raise errors.ForbiddenError(msg='无权访问此记录')

        return record

    @staticmethod
    async def get_session_records(*, db: AsyncSession, session_id: int, user_id: int) -> list[PracticeRecord]:
        """
        获取会话的所有答题记录

        :param db: 数据库会话
        :param session_id: 会话 ID
        :param user_id: 用户 ID
        :return:
        """
        await SessionService._get_owned_session(db=db, session_id=session_id, user_id=user_id)

        return await practice_record_dao.get_by_session(db=db, session_id=session_id)

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

        family_code = await membership_experience_service.resolve_reward_family(db, user_id=user_id)
        reward_rule = await membership_experience_rule_dao.get_active_rule(
            db,
            event_code='practice_correct',
            family_code=family_code,
        )
        if not reward_rule:
            return {'reward_exp': 0, 'family_code': family_code}

        if completed_count < reward_rule.min_practice_count:
            return {'reward_exp': 0, 'family_code': family_code}

        if total_time < reward_rule.min_practice_duration:
            return {'reward_exp': 0, 'family_code': family_code}

        reward_exp = reward_rule.exp_delta * correct_count
        progress = await membership_experience_service.add_experience(
            db,
            user_id=user_id,
            family_code=family_code,
            exp_delta=reward_exp,
            source='practice_correct',
            source_key=f'practice_correct:{session_id}',
            remark=f'完成练习答对 {correct_count} 题奖励',
        )
        return {
            'reward_exp': reward_exp,
            'family_code': family_code,
            'tier_grade': progress.get('tier_grade'),
            'exp': progress.get('exp'),
            'available_exp': progress.get('available_exp'),
        }

    @staticmethod
    async def submit_session(
        *,
        db: AsyncSession,
        session_id: int,
        user_id: int,
        obj: SubmitPracticeSessionParam,
    ) -> SubmitPracticeSessionResult:
        """
        提交练习会话并统一判题

        流程：锁会话行 → 判题 → 更新记录 → 更新全站统计 → 写错题本 → 标记完成

        :param db: 数据库会话
        :param session_id: 会话 ID
        :param user_id: 用户 ID
        :param obj: 提交参数
        :return:
        """
        # 1. 加锁查询会话，防并发重复提交
        lock_stmt = (
            select(PracticeSession)
            .where(PracticeSession.id == session_id)
            .with_for_update()
        )
        result = await db.execute(lock_stmt)
        session = result.scalars().first()

        if not session:
            raise errors.NotFoundError(msg='会话不存在')
        if session.user_id != user_id:
            raise errors.ForbiddenError(msg='无权操作此会话')
        if session.status == 'completed':
            # 幂等：已提交直接返回上次结果
            return SubmitPracticeSessionResult(
                completed_count=session.completed_count,
                correct_count=session.correct_count,
                wrong_count=session.wrong_count,
                accuracy_rate=session.accuracy_rate,
                score=session.score,
                total_score=session.total_score,
                reward_exp=0,
            )
        if session.status != 'in_progress':
            raise errors.ForbiddenError(msg='会话状态异常，无法提交')

        # 考试模式：校验时间限制
        if session.session_type == 'exam' and session.exam_config:
            time_limit = session.exam_config.get('time_limit')
            if time_limit and obj.total_time > time_limit:
                raise errors.ForbiddenError(msg=f'考试已超时（限时 {time_limit} 秒）')

        # 2. 查询答题记录 + 题目 + 解析
        records = await practice_record_dao.get_by_session(db=db, session_id=session_id)
        if not records:
            raise errors.NotFoundError(msg='没有答题记录可提交')

        question_ids = [r.question_id for r in records]
        stmt = (
            select(Question)
            .where(Question.id.in_(question_ids))
            .options(selectinload(Question.analyses))
        )
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
        option_stat_rows: list[dict[str, Any]] = []
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
            if (question_map.get(record.question_id) and question_map[record.question_id].type in SUBJECTIVE_QUESTION_TYPES)
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
                if (
                    record.id not in subjective_eval_map
                    or subjective_eval_map[record.id].status != 'succeeded'
                )
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

            question_stats_rows.append({
                'question_id': record.question_id,
                'attempt_count': 1,
                'correct_count': 1 if is_correct else 0,
                'answer_time_total': record.answer_time,
                'option_select_counts': option_select_counts,
            })

            # 3c. 汇总选项统计
            if selected_codes and placement_id is not None:
                option_stat_rows.append({
                    'placement_id': placement_id,
                    'question_id': record.question_id,
                    'option_codes': selected_codes,
                    'is_correct': is_correct,
                })

            # 3d. 汇总错题本（按 question_id 宽松匹配，忽略 placement）
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
                            'set_is_mastered': False,
                            'set_mastered_time': None,
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
                        'is_mastered': False,
                        'mastered_time': None,
                        'created_by': user_id,
                    })
            else:
                for existing_wrong in existing_wrong_list:
                    new_streak = existing_wrong.correct_streak + 1
                    is_mastered = existing_wrong.is_mastered or new_streak >= mastery_threshold
                    mastered_time = existing_wrong.mastered_time
                    if is_mastered and mastered_time is None:
                        mastered_time = submit_time
                    wrong_update_rows.append({
                        'filter_wrong_id': existing_wrong.id,
                        'set_wrong_count': existing_wrong.wrong_count,
                        'set_correct_streak': new_streak,
                        'set_last_wrong_time': existing_wrong.last_wrong_time,
                        'set_last_practice_time': submit_time,
                        'set_is_mastered': is_mastered,
                        'set_mastered_time': mastered_time,
                    })

        # 4. 批量落库
        if judged_record_rows:
            await practice_record_dao.batch_upsert(db=db, records=judged_record_rows)

        if question_stats_rows:
            await question_statistics_dao.batch_update_stats(db=db, items=question_stats_rows)

        if option_stat_rows:
            await question_option_stats_dao.batch_increment_by_records(db=db, records=option_stat_rows)

        if wrong_create_rows:
            await wrong_question_dao.batch_create(db=db, rows=wrong_create_rows)

        if wrong_update_rows:
            await wrong_question_dao.batch_update(db=db, rows=wrong_update_rows)

        completed_count = len(records)
        wrong_count = completed_count - correct_count

        # 5. 标记会话完成
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

        # 6. 增量更新用户统计快照（只统计本次新判的记录，避免与异步任务重复）
        # 刷题模式：每题 Celery process_record_side_effects 已增量过 → newly_judged 为空 → 跳过
        # 考试模式 / 异常情况：record.is_correct 仍为 NULL → 此刻首次判 → 增量
        newly_judged_qids = {r.question_id for r in records if r.is_correct is None}
        if newly_judged_qids:
            newly_rows = [row for row in judged_record_rows if row['question_id'] in newly_judged_qids]
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
                'family_code': check_in_result.family_code,
                'tier_grade': check_in_result.tier_grade,
                'exp': check_in_result.exp,
                'available_exp': check_in_result.available_exp,
            }

        log.info(
            'Session submitted: id=%d user=%d completed=%d correct=%d wrong=%d score=%s reward_exp=%s check_in=%s',
            session_id, user_id, completed_count, correct_count, wrong_count, earned_score,
            reward_exp, bool(check_in_result),
        )
        return SubmitPracticeSessionResult(
            completed_count=completed_count,
            correct_count=correct_count,
            wrong_count=wrong_count,
            accuracy_rate=(
                Decimal(str(round(correct_count / completed_count * 100, 2)))
                if completed_count > 0 else Decimal('0')
            ),
            score=earned_score if earned_score > 0 else None,
            total_score=total_score if total_score > 0 else None,
            reward_exp=reward_exp,
            practice_reward_exp=practice_reward_exp,
            check_in_reward_exp=check_in_reward_exp,
            is_auto_checked_in=bool(check_in_result),
            check_in_streak=check_in_result.check_in_streak if check_in_result else None,
            family_code=latest_progress.get('family_code'),
            tier_grade=latest_progress.get('tier_grade'),
            exp=latest_progress.get('exp'),
            available_exp=latest_progress.get('available_exp'),
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
        record_map: dict[int, PracticeRecord] = {r.question_id: r for r in session.records}
        answer_items: list[AnswerCardItem] = []
        wrong_question_ids: list[int] = []

        for sq in session.session_questions:
            record = record_map.get(sq.question_id)

            if record is None:
                status = 'unanswered'
                answer_time = 0
            elif record.is_correct:
                status = 'correct'
                answer_time = record.answer_time or 0
            else:
                status = 'wrong'
                answer_time = record.answer_time or 0
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
    async def get_session_solution(
        *, db: AsyncSession, session_id: int, user_id: int
    ) -> list[dict]:
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
        records = await practice_record_dao.get_by_session(db=db, session_id=session_id)

        # 批量查题目 + 解析 + 选项
        question_ids = [sq.question_id for sq in session_questions]
        if not question_ids:
            return []

        stmt = (
            select(Question)
            .where(Question.id.in_(question_ids))
            .options(
                load_only(Question.id, Question.stem, Question.type),
                selectinload(Question.analyses).load_only(
                    QuestionAnalysis.id,
                    QuestionAnalysis.question_id,
                    QuestionAnalysis.answer_data,
                    QuestionAnalysis.content,
                    QuestionAnalysis.is_default,
                ),
                selectinload(Question.options)
                .load_only(
                    QuestionOption.id,
                    QuestionOption.question_id,
                    QuestionOption.option_code,
                    QuestionOption.sort_order,
                    QuestionOption.is_active,
                )
                .joinedload(QuestionOption.content_ref)
                .load_only(OptionContent.content),
            )
        )
        result = await db.execute(stmt)
        question_map: dict[int, Question] = {q.id: q for q in result.scalars().all()}

        record_map: dict[int, PracticeRecord] = {record.question_id: record for record in records}

        solutions: list[dict] = []
        for sq in session_questions:
            q = question_map.get(sq.question_id)
            if not q:
                continue

            record = record_map.get(sq.question_id)
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
                'user_answer': record.user_answer if record else None,
                'is_correct': record.is_correct if record else None,
                'score': record.score if record else None,
                'full_score': sq.full_score,
                'answer_time': record.answer_time if record else 0,
            })

        return solutions

    @staticmethod
    async def get_session_questions_with_materials(
        *, db: AsyncSession, session_id: int, user_id: int
    ) -> dict[str, Any]:
        """
        获取会话题目静态内容和去重材料

        :param db: 数据库会话
        :param session_id: 会话 ID
        :param user_id: 用户 ID
        :return: 包含 questions 和 materials 的字典
        """
        # 1. 获取会话题目快照（按 seq_no 排序）
        await SessionService._get_owned_session(db=db, session_id=session_id, user_id=user_id)
        session_questions = await session_question_dao.list_by_session(db=db, session_id=session_id)
        if not session_questions:
            return {'questions': [], 'materials': []}

        placement_ids = [sq.placement_id for sq in session_questions if sq.placement_id]
        placement_bank_map: dict[int, int] = {}
        if placement_ids:
            placement_stmt = select(QuestionPlacement.id, QuestionPlacement.bank_id).where(
                QuestionPlacement.id.in_(placement_ids)
            )
            placement_rows = (await db.execute(placement_stmt)).all()
            placement_bank_map = {row.id: row.bank_id for row in placement_rows}

        bank_ids = sorted(set(placement_bank_map.values()))
        bank_info_map: dict[int, Any] = {}
        bank_material_map: dict[int, list[int]] = {}
        if bank_ids:
            from backend.app.question_bank.model.bank import QuestionBank
            from backend.app.question_bank.model.question import QuestionMaterial

            bank_stmt = select(QuestionBank).where(QuestionBank.id.in_(bank_ids))
            bank_rows = (await db.execute(bank_stmt)).scalars().all()
            bank_info_map = {bank.id: bank for bank in bank_rows}

            bank_material_stmt = (
                select(QuestionMaterial.id, QuestionMaterial.bank_id)
                .where(
                    QuestionMaterial.bank_id.in_(bank_ids),
                    QuestionMaterial.is_active.is_(True),
                )
                .order_by(QuestionMaterial.bank_id.asc(), QuestionMaterial.sort_order.asc(), QuestionMaterial.id.asc())
            )
            bank_material_rows = (await db.execute(bank_material_stmt)).all()
            for row in bank_material_rows:
                bank_material_map.setdefault(row.bank_id, []).append(row.id)

        # 2. 批量查询题目详情（含选项和材料关联）
        question_ids = [sq.question_id for sq in session_questions]
        stmt = (
            select(Question)
            .where(Question.id.in_(question_ids))
            .options(
                selectinload(Question.options).joinedload(QuestionOption.content_ref),
                selectinload(Question.materials),
            )
        )
        result = await db.execute(stmt)
        question_map: dict[int, Question] = {q.id: q for q in result.unique().scalars().all()}

        # 3. 构建题目列表（按 seq_no 排序）
        questions_list: list[dict[str, Any]] = []
        all_material_ids: set[int] = set()
        for sq in session_questions:
            question = question_map.get(sq.question_id)
            if not question:
                continue

            # 构建选项数组
            options_list: list[dict[str, str]] = []
            if question.options:
                active_options = [opt for opt in question.options if opt.is_active]
                sorted_options = sorted(active_options, key=lambda x: (x.sort_order, x.option_code))
                for opt in sorted_options:
                    options_list.append({
                        'option_code': opt.option_code,
                        'content': opt.content_ref.content if opt.content_ref else '',
                    })

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

        # 4. 去重并批量查询材料
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
        study_domain: str | None = None,
    ) -> select:
        """
        获取会话列表查询表达式

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param session_type: 会话类型
        :param status: 状态
        :param study_domain: 学习领域编码
        :return:
        """
        resolved_bank_ids = None
        if study_domain is not None:
            domain_filter = await study_domain_service.get_question_filter(db=db, code=study_domain)
            resolved_bank_ids = list(domain_filter.bank_ids)

        return await practice_session_dao.get_select(
            user_id=user_id, session_type=session_type, bank_ids=resolved_bank_ids, status=status,
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
        return await practice_record_dao.get_select(
            user_id=user_id, session_id=session_id, question_id=question_id,
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
        if obj.chapter_id is not None:
            from backend.app.question_bank.service.membership_service import membership_service

            obj.bank_id = await membership_service.resolve_bank_context_for_chapter(
                db=db,
                chapter_id=obj.chapter_id,
                bank_id=obj.bank_id,
                user_id=user_id,
            )

        source_snapshot = cls._build_session_source_snapshot(obj)
        source_key = cls._build_session_source_key(source_snapshot)

        latest_session = await practice_session_dao.get_latest_session(
            db=db,
            user_id=user_id,
            session_type=obj.session_type,
            bank_id=obj.bank_id,
            chapter_id=obj.chapter_id,
            source_key=source_key,
        )
        if latest_session:
            return latest_session

        if obj.session_type not in {'wrong', 'favorite', 'note'}:
            return await cls.create_session(
                db=db,
                user_id=user_id,
                obj=obj,
                source_key=source_key,
                source_snapshot=source_snapshot,
            )

        collect_result = await question_selector_service.collect_question_ids(
            db=db,
            params=cls._build_collect_param(obj=obj, source_type=obj.session_type),
            user_id=user_id,
        )
        question_ids = collect_result.question_ids

        from backend.app.question_bank.service.membership_service import membership_service

        await membership_service.verify_question_ids_access(
            db=db,
            user_id=user_id,
            question_ids=question_ids,
        )

        placements = await cls._query_placements_by_question_ids(
            db=db,
            question_ids=question_ids,
            bank_id=obj.bank_id,
            chapter_id=obj.chapter_id,
        )
        return await cls._create_session_snapshot(
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


session_service: SessionService = SessionService()
