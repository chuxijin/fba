#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any

from sqlalchemy import String, cast, or_, select
from sqlalchemy.dialects.postgresql import JSONB as PGJSONB
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.admin.crud.crud_category import category_dao
from backend.app.question_bank.crud.crud_material import material_dao
from backend.app.question_bank.crud.crud_question_favorite import question_favorite_dao
from backend.app.question_bank.crud.crud_question_note import question_note_dao
from backend.app.question_bank.crud.crud_wrong_question import wrong_question_dao
from backend.app.question_bank.model import (
    Question,
    QuestionAnalysis,
    QuestionBank,
    QuestionChapter,
    QuestionPlacement,
)
from backend.app.question_bank.schema.question import QuestionCollectParam, QuestionCollectResult


class QuestionSelectorService:
    """统一筛题服务，输出稳定的 question_ids。"""

    @staticmethod
    def _dedup_ints(values: list[int] | None) -> list[int]:
        if not values:
            return []
        result: list[int] = []
        seen: set[int] = set()
        for value in values:
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0 or value in seen:
                continue
            seen.add(value)
            result.append(value)
        return result

    @staticmethod
    def _parse_kp_id(value: Any) -> int | None:
        if isinstance(value, bool):
            return None
        if isinstance(value, int) and value > 0:
            return value
        if isinstance(value, str) and value.strip().isdigit():
            parsed = int(value.strip())
            return parsed if parsed > 0 else None
        return None

    @classmethod
    def _normalize_knowledge_point_terms(cls, items: list[Any] | None) -> tuple[list[int], list[str]]:
        kp_ids: list[int] = []
        kp_names: list[str] = []
        seen_ids: set[int] = set()
        seen_names: set[str] = set()

        for item in items or []:
            if isinstance(item, dict):
                obj_id = cls._parse_kp_id(item.get('id') or item.get('category_id') or item.get('cat_id'))
                obj_name = str(item.get('name') or item.get('label') or item.get('title') or '').strip()
                if obj_id and obj_id not in seen_ids:
                    seen_ids.add(obj_id)
                    kp_ids.append(obj_id)
                if obj_name and obj_name not in seen_names:
                    seen_names.add(obj_name)
                    kp_names.append(obj_name)
                continue

            obj_id = cls._parse_kp_id(item)
            if obj_id:
                if obj_id not in seen_ids:
                    seen_ids.add(obj_id)
                    kp_ids.append(obj_id)
                continue

            obj_name = str(item).strip()
            if obj_name and obj_name not in seen_names:
                seen_names.add(obj_name)
                kp_names.append(obj_name)

        return kp_ids, kp_names

    @staticmethod
    def _build_knowledge_point_conditions(*, kp_ids: list[int], kp_names: list[str]) -> list[Any]:
        kp_column = cast(Question.knowledge_point, PGJSONB)
        conditions: list[Any] = []

        for kp_id in kp_ids:
            conditions.append(kp_column.contains([kp_id]))
            conditions.append(kp_column.contains([{'id': kp_id}]))
            conditions.append(kp_column.contains([{'category_id': kp_id}]))
            conditions.append(kp_column.contains([{'cat_id': kp_id}]))

        for kp_name in kp_names:
            conditions.append(kp_column.contains([kp_name]))
            conditions.append(kp_column.contains([{'name': kp_name}]))
            conditions.append(kp_column.contains([{'label': kp_name}]))
            conditions.append(kp_column.contains([{'title': kp_name}]))

        return conditions

    @staticmethod
    def _build_option_exists(option_keyword: str):
        return cast(Question.options, String).ilike(f'%{option_keyword}%')

    @staticmethod
    def _build_analysis_exists(analysis_keyword: str):
        return (
            select(1)
            .select_from(QuestionAnalysis)
            .where(
                QuestionAnalysis.question_id == Question.id,
                QuestionAnalysis.status == 10,
                QuestionAnalysis.content.ilike(f'%{analysis_keyword}%'),
            )
            .exists()
        )

    @classmethod
    async def _resolve_category_ids(cls, *, db: AsyncSession, cat_id: int | None) -> list[int] | None:
        if cat_id is None:
            return None
        return await category_dao.get_all_children_ids(db, cat_id)

    @staticmethod
    async def resolve_chapter_scope_ids(*, db: AsyncSession, chapter_id: int | None) -> list[int] | None:
        """
        解析章节及其所有子章节 ID

        :param db: 数据库会话
        :param chapter_id: 章节 ID
        :return:
        """
        if chapter_id is None:
            return None

        chapter_stmt = select(QuestionChapter).where(QuestionChapter.id == chapter_id)
        chapter = (await db.execute(chapter_stmt)).scalars().first()
        if not chapter:
            return [chapter_id]

        chapter_list_stmt = select(QuestionChapter.id, QuestionChapter.parent_id).where(
            QuestionChapter.bank_id == chapter.bank_id
        )
        rows = (await db.execute(chapter_list_stmt)).all()
        children_map: dict[int, list[int]] = {}
        for row in rows:
            if row.parent_id is None:
                continue
            children_map.setdefault(row.parent_id, []).append(row.id)

        scope_ids: list[int] = []
        pending_ids = [chapter_id]
        while pending_ids:
            current_id = pending_ids.pop(0)
            scope_ids.append(current_id)
            pending_ids.extend(children_map.get(current_id, []))

        return scope_ids

    @classmethod
    def _apply_question_filters(
        cls,
        *,
        stmt,
        params: QuestionCollectParam,
        kp_ids: list[int],
        kp_names: list[str],
    ):
        if params.content_status is not None:
            stmt = stmt.where(Question.content_status == params.content_status)
        if params.question_types:
            stmt = stmt.where(Question.type.in_(params.question_types))
        if params.difficulties:
            stmt = stmt.where(Question.difficulty.in_(params.difficulties))

        stem_text = (params.stem_keyword or '').strip()
        if stem_text:
            stmt = stmt.where(Question.stem.ilike(f'%{stem_text}%'))

        option_text = (params.option_keyword or '').strip()
        if option_text:
            stmt = stmt.where(cls._build_option_exists(option_text))

        analysis_text = (params.analysis_keyword or '').strip()
        if analysis_text:
            stmt = stmt.where(cls._build_analysis_exists(analysis_text))

        kp_conditions = cls._build_knowledge_point_conditions(kp_ids=kp_ids, kp_names=kp_names)
        if kp_conditions:
            stmt = stmt.where(or_(*kp_conditions))

        return stmt

    @classmethod
    def _apply_placement_filters(
        cls,
        *,
        stmt,
        params: QuestionCollectParam,
        cat_ids: list[int] | None,
        needs_bank_join: bool,
        chapter_scope_ids: list[int] | None,
    ):
        if params.bank_ids:
            stmt = stmt.where(QuestionPlacement.bank_id.in_(params.bank_ids))
        elif params.bank_id is not None:
            stmt = stmt.where(QuestionPlacement.bank_id == params.bank_id)
        if chapter_scope_ids:
            stmt = stmt.where(QuestionPlacement.chapter_id.in_(chapter_scope_ids))
        elif params.chapter_id is not None:
            stmt = stmt.where(QuestionPlacement.chapter_id == params.chapter_id)
        if params.is_active is not None:
            stmt = stmt.where(QuestionPlacement.is_active.is_(params.is_active))
        if params.review_status is not None:
            stmt = stmt.where(QuestionPlacement.review_status == params.review_status)

        region_text = (params.region or '').strip()
        if needs_bank_join:
            stmt = stmt.join(QuestionBank, QuestionBank.id == QuestionPlacement.bank_id)
            stmt = stmt.where(
                QuestionBank.status == 1,
                QuestionBank.bank_type == 2,
            )
            if cat_ids:
                stmt = stmt.where(QuestionBank.cat_id.in_(cat_ids))
            if region_text:
                stmt = stmt.where(
                    or_(
                        QuestionBank.name.ilike(f'%{region_text}%'),
                        QuestionBank.code.ilike(f'%{region_text}%'),
                        QuestionBank.desc.ilike(f'%{region_text}%'),
                    )
                )

            # 年份范围按试卷年份（题库 year 字段）过滤。
            year_start = params.year_start
            year_end = params.year_end
            if year_start is not None and year_end is not None and year_start > year_end:
                year_start, year_end = year_end, year_start
            if year_start is not None:
                stmt = stmt.where(QuestionBank.year >= year_start)
            if year_end is not None:
                stmt = stmt.where(QuestionBank.year <= year_end)

        return stmt

    @classmethod
    async def _filter_ordered_question_ids(
        cls,
        *,
        db: AsyncSession,
        ordered_ids: list[int],
        params: QuestionCollectParam,
        kp_ids: list[int],
        kp_names: list[str],
        cat_ids: list[int] | None,
        chapter_scope_ids: list[int] | None,
        apply_limit: bool = True,
    ) -> list[int]:
        if not ordered_ids:
            return []

        stmt = select(Question.id).where(Question.id.in_(ordered_ids))
        stmt = cls._apply_question_filters(stmt=stmt, params=params, kp_ids=kp_ids, kp_names=kp_names)

        needs_bank_join = (
            params.cat_id is not None
            or bool((params.region or '').strip())
            or params.year_start is not None
            or params.year_end is not None
        )
        needs_placement_exists = (
            any(
                value is not None
                for value in (params.bank_id, params.chapter_id, params.review_status, params.is_active)
            )
            or bool(params.bank_ids)
            or needs_bank_join
        )
        if needs_placement_exists:
            placement_stmt = (
                select(1).select_from(QuestionPlacement).where(QuestionPlacement.question_id == Question.id)
            )
            placement_stmt = cls._apply_placement_filters(
                stmt=placement_stmt,
                params=params,
                cat_ids=cat_ids,
                needs_bank_join=needs_bank_join,
                chapter_scope_ids=chapter_scope_ids,
            )
            stmt = stmt.where(placement_stmt.exists())

        matched_ids = set((await db.execute(stmt)).scalars().all())
        filtered = [question_id for question_id in ordered_ids if question_id in matched_ids]
        if apply_limit and params.limit is not None:
            filtered = filtered[: params.limit]
        return filtered

    @classmethod
    async def _select_placement_question_ids(
        cls,
        *,
        db: AsyncSession,
        params: QuestionCollectParam,
        kp_ids: list[int],
        kp_names: list[str],
        cat_ids: list[int] | None,
        chapter_scope_ids: list[int] | None,
        apply_limit: bool = True,
    ) -> list[int]:
        stmt = (
            select(QuestionPlacement.question_id)
            .select_from(QuestionPlacement)
            .join(
                Question,
                Question.id == QuestionPlacement.question_id,
            )
        )
        stmt = cls._apply_question_filters(stmt=stmt, params=params, kp_ids=kp_ids, kp_names=kp_names)

        needs_bank_join = (
            params.cat_id is not None
            or bool((params.region or '').strip())
            or params.year_start is not None
            or params.year_end is not None
        )
        stmt = cls._apply_placement_filters(
            stmt=stmt,
            params=params,
            cat_ids=cat_ids,
            needs_bank_join=needs_bank_join,
            chapter_scope_ids=chapter_scope_ids,
        )

        if params.chapter_id is not None:
            stmt = stmt.order_by(QuestionPlacement.sort_order.asc(), QuestionPlacement.question_id.asc())
        elif params.bank_id is not None:
            stmt = stmt.order_by(
                QuestionPlacement.chapter_id.asc(),
                QuestionPlacement.sort_order.asc(),
                QuestionPlacement.question_id.asc(),
            )
        else:
            stmt = stmt.order_by(
                QuestionPlacement.bank_id.asc(),
                QuestionPlacement.chapter_id.asc(),
                QuestionPlacement.sort_order.asc(),
                QuestionPlacement.question_id.asc(),
            )

        rows = (await db.execute(stmt)).scalars().all()
        ordered_ids = list(dict.fromkeys(rows))
        if apply_limit and params.limit is not None:
            ordered_ids = ordered_ids[: params.limit]
        return ordered_ids

    @classmethod
    async def _filter_sibling_candidates(
        cls,
        *,
        db: AsyncSession,
        candidate_ids: list[int],
        params: QuestionCollectParam,
        cat_ids: list[int] | None,
        chapter_scope_ids: list[int] | None,
    ) -> set[int]:
        """
        校验材料兄弟题是否合格（过审 + 落在当前挂载场景内）

        :param db: 数据库会话
        :param candidate_ids: 候选兄弟题 ID 列表
        :param params: 筛题参数
        :param cat_ids: 分类范围 ID
        :param chapter_scope_ids: 章节范围 ID
        :return:
        """
        if not candidate_ids:
            return set()

        stmt = select(Question.id).where(
            Question.id.in_(candidate_ids),
            Question.content_status == 10,
        )

        needs_bank_join = (
            params.cat_id is not None
            or bool((params.region or '').strip())
            or params.year_start is not None
            or params.year_end is not None
        )
        needs_placement_exists = (
            any(
                value is not None
                for value in (params.bank_id, params.chapter_id, params.review_status, params.is_active)
            )
            or bool(params.bank_ids)
            or needs_bank_join
        )
        if needs_placement_exists:
            placement_stmt = (
                select(1).select_from(QuestionPlacement).where(QuestionPlacement.question_id == Question.id)
            )
            placement_stmt = cls._apply_placement_filters(
                stmt=placement_stmt,
                params=params,
                cat_ids=cat_ids,
                needs_bank_join=needs_bank_join,
                chapter_scope_ids=chapter_scope_ids,
            )
            stmt = stmt.where(placement_stmt.exists())

        return set((await db.execute(stmt)).scalars().all())

    @classmethod
    async def _expand_and_group_by_material(
        cls,
        *,
        db: AsyncSession,
        ordered_ids: list[int],
        params: QuestionCollectParam,
        cat_ids: list[int] | None,
        chapter_scope_ids: list[int] | None,
    ) -> list[int]:
        """
        将挂载题集按材料展开为不可分割的题组并聚合排序

        :param db: 数据库会话
        :param ordered_ids: 已排序的命中题目 ID 列表
        :param params: 筛题参数
        :param cat_ids: 分类范围 ID
        :param chapter_scope_ids: 章节范围 ID
        :return:
        """
        if not ordered_ids:
            return []

        question_material_rows = await material_dao.get_material_ids_by_questions(db, ordered_ids)
        if not question_material_rows:
            if params.limit is not None:
                return ordered_ids[: params.limit]
            return ordered_ids

        question_to_material: dict[int, int] = {}
        material_ids: list[int] = []
        seen_materials: set[int] = set()
        for question_id, material_id in question_material_rows:
            question_to_material.setdefault(question_id, material_id)
            if material_id not in seen_materials:
                seen_materials.add(material_id)
                material_ids.append(material_id)

        sibling_rows = await material_dao.get_sibling_relations(db, material_ids)
        candidate_ids = list({question_id for _, question_id in sibling_rows})
        valid_ids = await cls._filter_sibling_candidates(
            db=db,
            candidate_ids=candidate_ids,
            params=params,
            cat_ids=cat_ids,
            chapter_scope_ids=chapter_scope_ids,
        )

        material_to_questions: dict[int, list[int]] = {}
        for material_id, question_id in sibling_rows:
            if question_id in valid_ids:
                material_to_questions.setdefault(material_id, []).append(question_id)

        placed: set[int] = set()
        groups: list[list[int]] = []
        for question_id in ordered_ids:
            if question_id in placed:
                continue
            material_id = question_to_material.get(question_id)
            if material_id is None:
                groups.append([question_id])
                placed.add(question_id)
                continue
            group = [qid for qid in material_to_questions.get(material_id, []) if qid not in placed]
            if not group:
                group = [question_id]
            placed.update(group)
            groups.append(group)

        if params.limit is None:
            return [question_id for group in groups for question_id in group]

        result: list[int] = []
        for group in groups:
            if len(result) >= params.limit:
                break
            result.extend(group)
        return result

    @classmethod
    async def _get_personal_source_ids(
        cls,
        *,
        db: AsyncSession,
        params: QuestionCollectParam,
        user_id: int,
        knowledge_name: str | None,
        chapter_scope_ids: list[int] | None,
    ) -> list[int]:
        if params.source_type == 'wrong':
            return await wrong_question_dao.get_question_ids(
                db=db,
                user_id=user_id,
                bank_id=params.bank_id if not params.bank_ids else None,
                bank_ids=params.bank_ids or None,
                chapter_id=params.chapter_id,
                chapter_ids=chapter_scope_ids,
                knowledge_point=knowledge_name,
                recent_days=params.recent_days,
            )
        if params.source_type == 'favorite':
            return await question_favorite_dao.get_question_ids(
                db=db,
                user_id=user_id,
                bank_id=params.bank_id,
                chapter_id=params.chapter_id,
                knowledge_point=knowledge_name,
            )
        if params.source_type == 'note':
            return await question_note_dao.get_question_ids(
                db=db,
                user_id=user_id,
                bank_id=params.bank_id,
                chapter_id=params.chapter_id,
                knowledge_point=knowledge_name,
            )
        return []

    @classmethod
    async def collect_question_ids(
        cls,
        *,
        db: AsyncSession,
        params: QuestionCollectParam,
        user_id: int | None = None,
    ) -> QuestionCollectResult:
        explicit_ids = cls._dedup_ints(params.question_ids)
        kp_ids, kp_names = cls._normalize_knowledge_point_terms(params.knowledge_point)
        cat_ids = await cls._resolve_category_ids(db=db, cat_id=params.cat_id)
        chapter_scope_ids = await cls.resolve_chapter_scope_ids(db=db, chapter_id=params.chapter_id)

        if params.source_type == 'placement':
            if explicit_ids:
                selected_ids = await cls._filter_ordered_question_ids(
                    db=db,
                    ordered_ids=explicit_ids,
                    params=params,
                    kp_ids=kp_ids,
                    kp_names=kp_names,
                    cat_ids=cat_ids,
                    chapter_scope_ids=chapter_scope_ids,
                    apply_limit=False,
                )
            else:
                selected_ids = await cls._select_placement_question_ids(
                    db=db,
                    params=params,
                    kp_ids=kp_ids,
                    kp_names=kp_names,
                    cat_ids=cat_ids,
                    chapter_scope_ids=chapter_scope_ids,
                    apply_limit=False,
                )

            selected_ids = await cls._expand_and_group_by_material(
                db=db,
                ordered_ids=selected_ids,
                params=params,
                cat_ids=cat_ids,
                chapter_scope_ids=chapter_scope_ids,
            )
        else:
            if not isinstance(user_id, int) or user_id <= 0:
                raise ValueError('个人题目来源必须提供有效的 user_id。')

            knowledge_name = kp_names[0] if kp_names else None
            source_ids = cls._dedup_ints(
                await cls._get_personal_source_ids(
                    db=db,
                    params=params,
                    user_id=user_id,
                    knowledge_name=knowledge_name,
                    chapter_scope_ids=chapter_scope_ids,
                )
            )
            if explicit_ids:
                source_id_set = set(source_ids)
                source_ids = [question_id for question_id in explicit_ids if question_id in source_id_set]

            selected_ids = await cls._filter_ordered_question_ids(
                db=db,
                ordered_ids=source_ids,
                params=params,
                kp_ids=kp_ids,
                kp_names=kp_names,
                cat_ids=cat_ids,
                chapter_scope_ids=chapter_scope_ids,
            )

        return QuestionCollectResult(
            source_type=params.source_type,
            question_ids=selected_ids,
            total=len(selected_ids),
        )


question_selector_service = QuestionSelectorService()
