#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import logging
import re

from decimal import Decimal
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.question_bank.crud.crud_bank import bank_dao
from backend.app.question_bank.crud.crud_material import material_dao
from backend.app.question_bank.model import (
    Question,
    QuestionAnalysis,
    QuestionChapter,
    QuestionPlacement,
)
from backend.app.question_bank.model.question import question_material_relation
from backend.app.question_bank.schema.material import CreateMaterialParam
from backend.app.question_bank.schema.question import (
    CreateQuestionParam,
    QuestionCoreBase,
    UpsertQuestionAnalysisItem,
    UpsertQuestionOptionItem,
    UpsertQuestionPlacementItem,
)
from backend.app.question_bank.schema.question_import import (
    BatchImportParam,
    BatchImportResult,
    ExcelImportResult,
    ImportResultItem,
    MaterialImportRow,
    QuestionImportRow,
)
from backend.app.question_bank.service.question_service import QuestionService
from backend.common.exception import errors
from backend.utils.answer_parser import extract_option_codes, split_answer_text

log = logging.getLogger(__name__)

# 题型映射
TYPE_MAPPING: dict[str, str] = {
    '单选': 'single', '单选题': 'single',
    '多选': 'multiple', '多选题': 'multiple',
    '判断': 'judgement', '判断题': 'judgement',
    '填空': 'fill', '填空题': 'fill',
    '简答': 'shortAnswer', '简答题': 'shortAnswer',
}

# 难度由答题数据动态计算，导入时不预设
DIFFICULTY_MAPPING: dict[str, None] = {
    '简单': None,
    '中等': None,
    '困难': None,
}


class QuestionImportService:
    """题目导入服务"""

    @staticmethod
    async def batch_import(*, db: AsyncSession, obj: BatchImportParam, user_id: int) -> BatchImportResult:
        """
        批量导入题目（复用 create 流程）

        :param db: 数据库会话
        :param obj: 批量导入参数
        :param user_id: 用户 ID
        :return:
        """
        from backend.app.question_bank.service.question_service import QuestionService

        bank = await bank_dao.get(db, obj.bank_id)
        if not bank:
            raise errors.NotFoundError(msg='Bank not found')

        chapter_cache: dict[str, int] = {}

        # ============ 第一阶段：验证所有数据 ============
        validated_rows: list[dict] = []
        validation_errors: list[ImportResultItem] = []

        for row_index, row in enumerate(obj.questions, start=2):
            try:
                question_type = TYPE_MAPPING.get(row.题型)
                if not question_type:
                    raise ValueError(f'不支持的题型：{row.题型}')

                difficulty = DIFFICULTY_MAPPING.get(row.难度 or '中等')

                chapter_id = await QuestionImportService._resolve_import_chapter_id(
                    db=db,
                    bank_id=obj.bank_id,
                    level1_name=row.一级目录,
                    level2_name=row.二级目录,
                    level3_name=row.三级目录,
                    chapter_cache=chapter_cache,
                )

                options_data = None
                if question_type in ['single', 'multiple', 'judgement']:
                    options_data = {}
                    for option_key in ['A', 'B', 'C', 'D']:
                        option_value = getattr(row, f'选项{option_key}', None)
                        if option_value:
                            options_data[option_key] = {
                                'code': option_key,
                                'content': option_value,
                            }

                answer_data = QuestionImportService._parse_answer(row.答案, question_type)
                default_score = Decimal(str(row.分数 if row.分数 is not None else 1))

                material_ids = None
                if row.材料编号:
                    try:
                        raw_str = str(row.材料编号).replace('，', ',')
                        material_ids = [int(m.strip()) for m in raw_str.split(',') if m.strip()]
                    except ValueError:
                        pass

                validated_rows.append({
                    'row_index': row_index,
                    'question_type': question_type,
                    'difficulty': difficulty,
                    'chapter_id': chapter_id,
                    'options_data': options_data,
                    'answer_data': answer_data,
                    'default_score': default_score,
                    'stem': row.题目,
                    'analysis_content': row.解析 or '暂无解析',
                    'sort_order': int(row.ID) if row.ID is not None else row_index,
                    'material_ids': material_ids,
                })

            except Exception as e:
                validation_errors.append(
                    ImportResultItem(
                        row_number=row_index,
                        success=False,
                        question_id=None,
                        error_message=str(e),
                    )
                )

        # 有验证错误，直接返回
        if validation_errors:
            return BatchImportResult(
                total=len(obj.questions),
                success_count=0,
                fail_count=len(validation_errors),
                details=validation_errors,
            )

        # ============ 第二阶段：复用 create 流程写入 ============
        results: list[ImportResultItem] = []
        for row_data in validated_rows:
            core = QuestionCoreBase(
                type=row_data['question_type'],
                stem=row_data['stem'],
                difficulty=row_data['difficulty'],
                default_score=row_data['default_score'],
            )

            options: list[UpsertQuestionOptionItem] = []
            if row_data['options_data']:
                for code, opt in row_data['options_data'].items():
                    options.append(UpsertQuestionOptionItem(
                        option_code=code,
                        content=opt['content'],
                        sort_order=ord(code) - ord('A'),
                    ))

            placements = [UpsertQuestionPlacementItem(
                bank_id=obj.bank_id,
                chapter_id=row_data['chapter_id'],
                sort_order=row_data['sort_order'],
                is_active=True,
                score=row_data['default_score'],
            )]

            analyses = [UpsertQuestionAnalysisItem(
                answer_data=row_data['answer_data'],
                content=row_data['analysis_content'],
                is_default=True,
            )]

            create_param = CreateQuestionParam(
                core=core,
                options=options,
                placements=placements,
                analyses=analyses,
                material_ids=row_data['material_ids'],
            )

            question = await QuestionService.create(db=db, obj=create_param, user_id=user_id)

            results.append(
                ImportResultItem(
                    row_number=row_data['row_index'],
                    success=True,
                    question_id=question.id,
                    error_message=None,
                )
            )

        success_count = len(validated_rows)

        return BatchImportResult(
            total=len(obj.questions),
            success_count=success_count,
            fail_count=0,
            details=results,
        )

    @staticmethod
    async def import_from_excel(
        *,
        db: AsyncSession,
        bank_id: int,
        question_rows: list[QuestionImportRow],
        material_rows: list[MaterialImportRow],
        user_id: int,
    ) -> ExcelImportResult:
        """
        从 Excel 导入题目（支持材料关联和题干去重）

        :param db: 数据库会话
        :param bank_id: 目标题库 ID
        :param question_rows: 题目行列表
        :param material_rows: 材料行列表
        :param user_id: 操作用户 ID
        :return:
        """
        from backend.app.question_bank.service.question_service import QuestionService

        bank = await bank_dao.get(db, bank_id)
        if not bank:
            raise errors.NotFoundError(msg='刷题内容不存在')

        # ============ 第一阶段：导入材料 ============
        material_id_map: dict[str, int] = {}
        for m_row in material_rows:
            key = str(m_row.材料编号).strip()
            if not key:
                continue
            create_material = CreateMaterialParam(
                bank_id=bank_id,
                title=m_row.材料标题 or f'材料 {key}',
                content=m_row.材料内容,
                is_active=True,
            )
            material = await material_dao.create(db, create_material, created_by=user_id)
            await db.flush()
            material_id_map[key] = material.id

        # ============ 第二阶段：构建全库复用索引 ============
        row_types = {
            TYPE_MAPPING.get(row.题型)
            for row in question_rows
            if TYPE_MAPPING.get(row.题型)
        }
        normalized_stems = {
            QuestionImportService._normalize_stem(row.题目)
            for row in question_rows
            if QuestionImportService._normalize_stem(row.题目)
        }
        fingerprint_index, stem_fingerprint_index = await QuestionImportService._load_reuse_index(
            db=db,
            question_types={item for item in row_types if item},
            normalized_stems=normalized_stems,
            bank_id=bank_id,
        )

        max_order_stmt = select(func.coalesce(func.max(QuestionPlacement.sort_order), 0)).where(
            QuestionPlacement.bank_id == bank_id
        )
        max_order = (await db.execute(max_order_stmt)).scalar() or 0

        # ============ 第三阶段：映射和验证 ============
        chapter_cache: dict[str, int] = {}
        results: list[ImportResultItem] = []
        success_count = 0
        dedup_count = 0
        existing_count = 0
        skipped_count = 0
        conflict_count = 0
        batch_mounted_question_ids: set[int] = set()

        for row_index, row in enumerate(question_rows, start=2):
            try:
                # 题型
                question_type = TYPE_MAPPING.get(row.题型)
                if not question_type:
                    raise ValueError(f'不支持的题型：{row.题型}')

                # 难度
                difficulty = DIFFICULTY_MAPPING.get(row.难度 or '中等')

                # 章节
                chapter_id = await QuestionImportService._resolve_import_chapter_id(
                    db=db,
                    bank_id=bank_id,
                    level1_name=row.一级目录,
                    level2_name=row.二级目录,
                    level3_name=row.三级目录,
                    chapter_cache=chapter_cache,
                )

                # 选项
                options: list[UpsertQuestionOptionItem] = []
                if question_type in ['single', 'multiple', 'judgement']:
                    for option_key in ['A', 'B', 'C', 'D']:
                        option_value = getattr(row, f'选项{option_key}', None)
                        if option_value:
                            options.append(UpsertQuestionOptionItem(
                                option_code=option_key,
                                content=str(option_value),
                                sort_order=ord(option_key) - ord('A'),
                            ))

                # 答案
                answer_data = QuestionImportService._parse_answer(row.答案, question_type)

                # 分值
                default_score = Decimal(str(row.分数 if row.分数 is not None else 1))

                # 排序
                sort_order = int(row.ID) if row.ID is not None else (max_order + row_index - 1)

                # 知识点
                knowledge_point = None
                if row.知识点:
                    knowledge_point = [row.知识点]

                # 材料关联（支持多个，英文或中文逗号分隔）
                material_ids: list[int] | None = None
                if row.材料编号 is not None:
                    raw_str = str(row.材料编号).replace('，', ',')
                    mat_keys = [k.strip() for k in raw_str.split(',') if k.strip()]
                    for mat_key in mat_keys:
                        if mat_key in material_id_map:
                            if material_ids is None:
                                material_ids = []
                            material_ids.append(material_id_map[mat_key])

                # ============ 内容复用检查 ============
                stem = row.题目
                normalized_stem = QuestionImportService._normalize_stem(stem)
                fingerprint = QuestionImportService._build_question_fingerprint(
                    question_type=question_type,
                    stem=stem,
                    options=options,
                )
                reuse_item = fingerprint_index.get(fingerprint)
                has_same_stem = bool(
                    normalized_stem
                    and normalized_stem in stem_fingerprint_index
                    and fingerprint not in stem_fingerprint_index[normalized_stem]
                )
                row_message = None
                if has_same_stem:
                    conflict_count += 1
                    row_message = '题干相同但题型或选项不同，已按新题导入，请人工核对'

                if reuse_item is not None:
                    answer_conflict = not QuestionImportService._same_answer(
                        reuse_item.get('answer_data'),
                        answer_data,
                    )
                    analysis_conflict = not QuestionImportService._same_text(
                        reuse_item.get('analysis_content'),
                        row.解析 or '暂无解析',
                    )
                    if answer_conflict or analysis_conflict:
                        conflict_count += 1
                        row_message = '复用已有题目，但答案或解析与已有版本不一致，请人工核对'

                    existing_qid = int(reuse_item['question_id'])
                    target_placement = await QuestionImportService._get_target_placement(
                        db=db,
                        question_id=existing_qid,
                        bank_id=bank_id,
                    )

                    if target_placement and existing_qid in batch_mounted_question_ids:
                        skipped_count += 1
                        success_count += 1
                        await QuestionImportService._attach_materials(
                            db=db,
                            question_id=existing_qid,
                            material_ids=material_ids,
                        )
                        results.append(ImportResultItem(
                            row_number=row_index,
                            success=True,
                            question_id=existing_qid,
                            error_message=row_message or '本批次重复题目，已复用首条记录',
                            action='skipped',
                        ))
                        continue

                    placement_item = UpsertQuestionPlacementItem(
                        bank_id=bank_id,
                        chapter_id=chapter_id,
                        sort_order=sort_order,
                        is_active=True,
                        score=default_score,
                    )
                    if target_placement:
                        await QuestionImportService._update_existing_placement(
                            db=db,
                            placement=target_placement,
                            item=placement_item,
                            user_id=user_id,
                        )
                        existing_count += 1
                        action = 'exists'
                        message = row_message or '当前内容已存在，已更新挂载信息'
                    else:
                        db.add(QuestionPlacement(
                            question_id=existing_qid,
                            bank_id=bank_id,
                            chapter_id=chapter_id,
                            sort_order=sort_order,
                            is_active=True,
                            score=default_score,
                            review_status=10,
                            created_by=user_id,
                        ))
                        await db.flush()
                        await QuestionService._update_placement_caches(
                            db=db,
                            placements=[placement_item],
                            delta=1,
                        )
                        batch_mounted_question_ids.add(existing_qid)
                        dedup_count += 1
                        action = 'reused'
                        message = row_message or '复用已有题目'

                    await QuestionImportService._attach_materials(
                        db=db,
                        question_id=existing_qid,
                        material_ids=material_ids,
                    )

                    results.append(ImportResultItem(
                        row_number=row_index,
                        success=True,
                        question_id=existing_qid,
                        error_message=message,
                        action=action,
                    ))
                else:
                    # 新建题目
                    core = QuestionCoreBase(
                        type=question_type,
                        stem=stem,
                        difficulty=difficulty,
                        default_score=default_score,
                        knowledge_point=knowledge_point,
                    )
                    placements = [UpsertQuestionPlacementItem(
                        bank_id=bank_id,
                        chapter_id=chapter_id,
                        sort_order=sort_order,
                        is_active=True,
                        score=default_score,
                    )]
                    analyses = [UpsertQuestionAnalysisItem(
                        answer_data=answer_data,
                        content=row.解析 or '暂无解析',
                        is_default=True,
                    )]
                    create_param = CreateQuestionParam(
                        core=core,
                        options=options,
                        placements=placements,
                        analyses=analyses,
                        material_ids=material_ids,
                    )
                    question = await QuestionService.create(db=db, obj=create_param, user_id=user_id)

                    QuestionImportService._remember_reuse_item(
                        fingerprint_index=fingerprint_index,
                        stem_fingerprint_index=stem_fingerprint_index,
                        fingerprint=fingerprint,
                        normalized_stem=normalized_stem,
                        question_id=question.id,
                        answer_data=answer_data,
                        analysis_content=row.解析 or '暂无解析',
                        bank_id=bank_id,
                    )
                    batch_mounted_question_ids.add(question.id)

                    results.append(ImportResultItem(
                        row_number=row_index,
                        success=True,
                        question_id=question.id,
                        error_message=row_message,
                        action='created',
                    ))

                success_count += 1

            except Exception as e:
                log.warning(f'Excel 导入第 {row_index} 行失败: {e}')
                results.append(ImportResultItem(
                    row_number=row_index,
                    success=False,
                    question_id=None,
                    error_message=str(e),
                ))

        fail_count = len(question_rows) - success_count
        return ExcelImportResult(
            total=len(question_rows),
            success_count=success_count,
            fail_count=fail_count,
            details=results,
            materials_count=len(material_id_map),
            dedup_count=dedup_count,
            existing_count=existing_count,
            skipped_count=skipped_count,
            conflict_count=conflict_count,
        )

    @staticmethod
    async def _load_reuse_index(
        *,
        db: AsyncSession,
        question_types: set[str],
        normalized_stems: set[str],
        bank_id: int,
    ) -> tuple[dict[str, dict[str, Any]], dict[str, set[str]]]:
        """
        加载全库题目复用索引

        :param db: 数据库会话
        :param question_types: 题型集合
        :param normalized_stems: 本次导入题干集合
        :param bank_id: 当前题库 ID
        :return:
        """
        if not question_types or not normalized_stems:
            return {}, {}

        stem_stmt = select(Question.id, Question.stem).where(Question.type.in_(question_types))
        stem_rows = (await db.execute(stem_stmt)).all()
        candidate_ids: list[int] = []
        for question_id, stem in stem_rows:
            normalized_stem = QuestionImportService._normalize_stem(stem)
            if normalized_stem in normalized_stems:
                candidate_ids.append(int(question_id))

        if not candidate_ids:
            return {}, {}

        detail_stmt = (
            select(Question)
            .where(Question.id.in_(candidate_ids))
            .options(
                selectinload(Question.analyses),
                selectinload(Question.placements),
            )
        )
        questions = (await db.execute(detail_stmt)).unique().scalars().all()
        fingerprint_index: dict[str, dict[str, Any]] = {}
        stem_fingerprint_index: dict[str, set[str]] = {}

        for question in questions:
            fingerprint = QuestionImportService._build_existing_question_fingerprint(question)
            if not fingerprint:
                continue

            normalized_stem = QuestionImportService._normalize_stem(question.stem)
            if normalized_stem:
                stem_fingerprint_index.setdefault(normalized_stem, set()).add(fingerprint)

            answer_data, analysis_content = QuestionImportService._pick_analysis_snapshot(question.analyses)
            in_current_bank = any(item.bank_id == bank_id for item in question.placements or [])
            reuse_item = {
                'question_id': question.id,
                'answer_data': answer_data,
                'analysis_content': analysis_content,
                'in_current_bank': in_current_bank,
            }
            old_item = fingerprint_index.get(fingerprint)
            if QuestionImportService._should_replace_reuse_item(old_item, reuse_item):
                fingerprint_index[fingerprint] = reuse_item

        return fingerprint_index, stem_fingerprint_index

    @staticmethod
    def _should_replace_reuse_item(old_item: dict[str, Any] | None, new_item: dict[str, Any]) -> bool:
        """
        判断是否替换复用候选

        :param old_item: 旧候选
        :param new_item: 新候选
        :return:
        """
        if old_item is None:
            return True

        if not old_item.get('in_current_bank') and new_item.get('in_current_bank'):
            return True

        if old_item.get('in_current_bank') and not new_item.get('in_current_bank'):
            return False

        return int(new_item['question_id']) < int(old_item['question_id'])

    @staticmethod
    def _remember_reuse_item(
        *,
        fingerprint_index: dict[str, dict[str, Any]],
        stem_fingerprint_index: dict[str, set[str]],
        fingerprint: str,
        normalized_stem: str,
        question_id: int,
        answer_data: dict,
        analysis_content: str,
        bank_id: int,
    ) -> None:
        """
        记录本次新建题用于后续行复用

        :param fingerprint_index: 指纹索引
        :param stem_fingerprint_index: 题干索引
        :param fingerprint: 题目指纹
        :param normalized_stem: 规范化题干
        :param question_id: 题目 ID
        :param answer_data: 答案数据
        :param analysis_content: 解析内容
        :param bank_id: 题库 ID
        """
        fingerprint_index[fingerprint] = {
            'question_id': question_id,
            'answer_data': answer_data,
            'analysis_content': analysis_content,
            'in_current_bank': True,
            'bank_id': bank_id,
        }
        if normalized_stem:
            stem_fingerprint_index.setdefault(normalized_stem, set()).add(fingerprint)

    @staticmethod
    def _build_existing_question_fingerprint(question: Question) -> str:
        """
        构建已有题目指纹

        :param question: 题目对象
        :return:
        """
        options: list[UpsertQuestionOptionItem] = []
        for option in QuestionService.normalize_options(question.options, active_only=True):
            options.append(UpsertQuestionOptionItem(
                option_code=option['option_code'],
                content=option['content'],
                sort_order=option['sort_order'],
                is_active=option['is_active'],
            ))

        return QuestionImportService._build_question_fingerprint(
            question_type=question.type,
            stem=question.stem,
            options=options,
        )

    @staticmethod
    def _build_question_fingerprint(
        *,
        question_type: str,
        stem: str,
        options: list[UpsertQuestionOptionItem],
    ) -> str:
        """
        构建题目内容指纹

        :param question_type: 题型
        :param stem: 题干
        :param options: 选项列表
        :return:
        """
        normalized_stem = QuestionImportService._normalize_stem(stem)
        option_parts: list[str] = []
        sorted_options = sorted(options, key=lambda item: item.option_code.strip().upper())
        for option in sorted_options:
            option_code = option.option_code.strip().upper()
            option_content = QuestionImportService._normalize_content_text(option.content)
            option_parts.append(f'{option_code}:{option_content}')

        options_text = '|'.join(option_parts)
        return f'{question_type}|{normalized_stem}|{options_text}'

    @staticmethod
    def _pick_analysis_snapshot(
        analyses: list[QuestionAnalysis] | None,
    ) -> tuple[dict[str, Any] | None, str | None]:
        """
        选择默认解析快照

        :param analyses: 解析列表
        :return:
        """
        if not analyses:
            return None, None

        default_items = [item for item in analyses if item.is_default]
        candidates = default_items or analyses
        analysis = min(candidates, key=lambda item: item.id)
        return analysis.answer_data, analysis.content

    @staticmethod
    async def _get_target_placement(
        *,
        db: AsyncSession,
        question_id: int,
        bank_id: int,
    ) -> QuestionPlacement | None:
        """
        获取当前题库挂载

        :param db: 数据库会话
        :param question_id: 题目 ID
        :param bank_id: 题库 ID
        :return:
        """
        stmt = select(QuestionPlacement).where(
            QuestionPlacement.question_id == question_id,
            QuestionPlacement.bank_id == bank_id,
        )
        return (await db.execute(stmt)).scalars().first()

    @staticmethod
    async def _update_existing_placement(
        *,
        db: AsyncSession,
        placement: QuestionPlacement,
        item: UpsertQuestionPlacementItem,
        user_id: int,
    ) -> None:
        """
        更新已有挂载并修正章节缓存

        :param db: 数据库会话
        :param placement: 已有挂载
        :param item: 新挂载信息
        :param user_id: 用户 ID
        """
        old_chapter_id = placement.chapter_id
        new_chapter_id = item.chapter_id
        if old_chapter_id != new_chapter_id:
            if old_chapter_id:
                await db.execute(
                    update(QuestionChapter)
                    .where(QuestionChapter.id == old_chapter_id)
                    .values(q_count_cache=QuestionChapter.q_count_cache - 1)
                )
            if new_chapter_id:
                await db.execute(
                    update(QuestionChapter)
                    .where(QuestionChapter.id == new_chapter_id)
                    .values(q_count_cache=QuestionChapter.q_count_cache + 1)
                )

        placement.chapter_id = new_chapter_id
        placement.sort_order = item.sort_order
        placement.is_active = item.is_active
        placement.score = item.score
        placement.review_status = item.review_status
        placement.scene_mask = item.scene_mask
        placement.updated_by = user_id
        await db.flush()

    @staticmethod
    async def _attach_materials(
        *,
        db: AsyncSession,
        question_id: int,
        material_ids: list[int] | None,
    ) -> None:
        """
        追加题目材料关联

        :param db: 数据库会话
        :param question_id: 题目 ID
        :param material_ids: 材料 ID 列表
        """
        if not material_ids:
            return

        existing_stmt = select(question_material_relation.c.material_id).where(
            question_material_relation.c.question_id == question_id,
            question_material_relation.c.material_id.in_(material_ids),
        )
        existing_ids = set((await db.execute(existing_stmt)).scalars().all())
        for material_id in material_ids:
            if material_id in existing_ids:
                continue
            await db.execute(
                question_material_relation.insert().values(
                    question_id=question_id,
                    material_id=material_id,
                    sort_order=0,
                )
            )
        await db.flush()

    @staticmethod
    def _same_answer(old_answer: Any, new_answer: dict) -> bool:
        """
        比较答案是否一致

        :param old_answer: 已有答案
        :param new_answer: 新答案
        :return:
        """
        if old_answer is None:
            return True
        return old_answer == new_answer

    @staticmethod
    def _same_text(old_text: Any, new_text: str) -> bool:
        """
        比较文本是否一致

        :param old_text: 已有文本
        :param new_text: 新文本
        :return:
        """
        if old_text is None:
            return True
        old_normalized = QuestionImportService._normalize_content_text(old_text)
        new_normalized = QuestionImportService._normalize_content_text(new_text)
        return old_normalized == new_normalized

    @staticmethod
    def _normalize_content_text(value: Any) -> str:
        """
        规范化内容文本

        :param value: 原始内容
        :return:
        """
        if value is None:
            return ''
        text = re.sub(r'<[^>]+>', '', str(value))
        text = text.replace('&nbsp;', ' ')
        text = re.sub(r'\s+', '', text)
        text = re.sub(r'[（(）)【】\[\]{}《》""。，、；：？！]', '', text)
        return text.strip()

    @staticmethod
    async def parse_excel_file(
        *,
        content: bytes,
        filename: str | None,
    ) -> tuple[list[QuestionImportRow], list[MaterialImportRow]]:
        """
        解析 Excel 文件，返回题目行和材料行

        :param content: 文件二进制内容
        :param filename: 文件名
        :return:
        """
        import io

        import pandas as pd

        from starlette.concurrency import run_in_threadpool

        if not filename or not filename.lower().endswith(('.xlsx', '.xls')):
            raise errors.RequestError(msg='请上传 .xlsx 格式文件')

        excel_bytes = io.BytesIO(content)

        # 读取 Sheet1（题目）
        try:
            df_questions = await run_in_threadpool(pd.read_excel, excel_bytes, sheet_name=0)
        except Exception as e:
            raise errors.RequestError(msg=f'读取 Excel 题目页失败: {e}')

        df_questions = df_questions.where(df_questions.notna(), None)
        question_rows: list[QuestionImportRow] = []
        col_map = {
            '序号': 'ID', '题型': '题型', '题目': '题目',
            '选项A': '选项A', '选项B': '选项B', '选项C': '选项C', '选项D': '选项D',
            '答案': '答案', '解析': '解析', '难度': '难度', '分数': '分数',
            '一级目录': '一级目录', '二级目录': '二级目录', '三级目录': '三级目录',
            '知识点': '知识点', '材料编号': '材料编号',
        }
        for _, pandas_row in df_questions.iterrows():
            row_dict: dict[str, Any] = {}
            for excel_col, schema_col in col_map.items():
                if excel_col in pandas_row.index:
                    val = pandas_row[excel_col]
                    if pd.notna(val) and val is not None:
                        row_dict[schema_col] = val
            if not row_dict.get('题目') or not row_dict.get('答案'):
                continue
            if not row_dict.get('题型'):
                row_dict['题型'] = '单选'
            question_rows.append(QuestionImportRow(**row_dict))

        if not question_rows:
            raise errors.RequestError(msg='Excel 中没有有效题目数据')

        # 读取 Sheet2（材料，可选）
        material_rows: list[MaterialImportRow] = []
        try:
            excel_bytes.seek(0)
            df_materials = await run_in_threadpool(pd.read_excel, excel_bytes, sheet_name=1)
            df_materials = df_materials.where(df_materials.notna(), None)
            for _, pandas_row in df_materials.iterrows():
                mat_id = pandas_row.get('材料编号')
                mat_content = pandas_row.get('材料内容')
                if pd.notna(mat_id) and pd.notna(mat_content) and mat_id:
                    mat_title = pandas_row.get('材料标题')
                    material_rows.append(MaterialImportRow(
                        材料编号=str(mat_id),
                        材料标题=mat_title if pd.notna(mat_title) else None,
                        材料内容=str(mat_content),
                    ))
        except Exception:
            log.warning('读取材料 sheet 失败，跳过材料导入', exc_info=True)

        return question_rows, material_rows

    @staticmethod
    async def build_import_template() -> bytes:
        """构建 Excel 导入模板"""
        import io

        from openpyxl import Workbook
        from starlette.concurrency import run_in_threadpool

        def _build() -> bytes:
            """构建 Excel 模板"""
            wb = Workbook()

            # Sheet1: 题目
            ws1 = wb.active
            ws1.title = '题目'
            ws1.append([
                '序号', '题型', '题目', '选项A', '选项B', '选项C', '选项D',
                '答案', '解析', '难度', '分数', '一级目录', '二级目录',
                '三级目录', '知识点', '材料编号',
            ])
            ws1.append([
                1, '单选', '下列关于宪法的说法，正确的是（ ）',
                '宪法具有最高法律效力', '宪法由全国人大常委会制定',
                '宪法修改由国务院提议', '宪法不具有直接法律效力',
                'A', '根据《宪法》规定，宪法具有最高法律效力。',
                '中等', 1, '常识判断', '宪法基础', None, '宪法学', None,
            ])

            # Sheet2: 材料
            ws2 = wb.create_sheet('材料')
            ws2.append(['材料编号', '材料标题', '材料内容'])
            ws2.append(['M1', '资料分析材料一', '根据以下资料，回答 1-5 题。（材料正文...）'])

            buf = io.BytesIO()
            wb.save(buf)
            return buf.getvalue()

        return await run_in_threadpool(_build)

    @staticmethod
    async def smart_commit(
        *,
        db: AsyncSession,
        bank_id: int,
        materials_data: list[dict],
        questions_data: list[dict],
        user_id: int,
    ) -> dict:
        """
        将智能解析结果批量入库

        :param db: 数据库会话
        :param bank_id: 题库 ID
        :param materials_data: 材料数据列表
        :param questions_data: 题目数据列表
        :param user_id: 操作用户 ID
        :return:
        """
        from backend.app.question_bank.service.question_service import QuestionService, question_service

        bank = await bank_dao.get(db, bank_id)
        if not bank:
            raise errors.NotFoundError(msg='刷题内容不存在')

        # -------- 1. 保存公共材料 --------
        material_id_map: dict[str | int, int] = {}
        for m_data in materials_data:
            create_material = CreateMaterialParam(
                bank_id=bank_id,
                title=m_data.get('title', '资料分析材料'),
                content=m_data.get('content', ''),
                is_active=True,
            )
            material = await material_dao.create(db, create_material, created_by=user_id)
            await db.flush()

            temp_id = m_data.get('material_id')
            if temp_id is not None:
                material_id_map[temp_id] = material.id

        # -------- 2. 逐题构建 CreateQuestionParam 并调用 service --------
        chapter_cache: dict[str, int] = {}
        success_count = 0

        for q_data in questions_data:
            # 2a. 章节处理
            chapter_id = None
            level1_name = (
                q_data.get('chapter_level1_name')
                or q_data.get('一级目录')
                or q_data.get('chapter_name')
            )
            level2_name = q_data.get('chapter_level2_name') or q_data.get('二级目录')
            level3_name = q_data.get('chapter_level3_name') or q_data.get('三级目录')
            if level1_name:
                chapter_id = await QuestionImportService._resolve_import_chapter_id(
                    db=db,
                    bank_id=bank_id,
                    level1_name=level1_name,
                    level2_name=level2_name,
                    level3_name=level3_name,
                    chapter_cache=chapter_cache,
                )

            # 2b. 基本字段
            q_type = q_data.get('type') or 'single'
            q_diff = q_data.get('difficulty') or None
            q_default_score = Decimal(str(q_data.get('score') or '1.0'))

            sort_order = q_data.get('sort_order')
            if sort_order is None:
                sort_order = success_count + 1
            elif isinstance(sort_order, str) and sort_order.isdigit():
                sort_order = int(sort_order)
            elif not isinstance(sort_order, int):
                sort_order = success_count + 1

            knowledge_point = q_data.get('knowledge_point')
            if isinstance(knowledge_point, str):
                knowledge_point = [knowledge_point] if knowledge_point else None

            # 2c. 构建 core
            core = QuestionCoreBase(
                type=q_type,
                stem=q_data.get('stem') or '',
                difficulty=q_diff,
                default_score=q_default_score,
                knowledge_point=knowledge_point,
            )

            # 2d. 构建选项
            options: list[UpsertQuestionOptionItem] = []
            raw_options = q_data.get('options_data')
            if isinstance(raw_options, dict):
                for code, opt in raw_options.items():
                    content = opt.get('content', '') if isinstance(opt, dict) else str(opt)
                    options.append(UpsertQuestionOptionItem(
                        option_code=code.upper(),
                        content=content,
                        sort_order=ord(code.upper()) - ord('A'),
                    ))

            # 2e. 构建挂载（一题一挂载，挂到 bank + chapter）
            placements = [UpsertQuestionPlacementItem(
                bank_id=bank_id,
                chapter_id=chapter_id,
                sort_order=sort_order,
                is_active=True,
                score=q_default_score,
                review_status=10,
            )]

            # 2f. 构建解析
            answer_data = q_data.get('answer_data') or {}
            analysis_content = q_data.get('analysis_content') or ''
            analyses = [UpsertQuestionAnalysisItem(
                type='official',
                is_default=True,
                answer_data=answer_data,
                content=analysis_content or '暂无解析',
            )]

            # 2g. 材料关联
            material_ids: list[int] | None = None
            temp_mid = q_data.get('material_id')
            if temp_mid is not None and temp_mid in material_id_map:
                material_ids = [material_id_map[temp_mid]]

            # 2h. 组装并调用 service.create
            create_param = CreateQuestionParam(
                core=core,
                options=options,
                placements=placements,
                analyses=analyses,
                material_ids=material_ids,
            )
            await question_service.create(db=db, obj=create_param, user_id=user_id)
            success_count += 1

        return {
            'materials_count': len(materials_data),
            'questions_count': success_count,
        }

    # ------------------------------------------------------------------
    #  内部工具
    # ------------------------------------------------------------------

    @staticmethod
    async def _resolve_import_chapter_id(
        *,
        db: AsyncSession,
        bank_id: int,
        level1_name: str | None,
        level2_name: str | None,
        level3_name: str | None,
        chapter_cache: dict[str, int],
    ) -> int | None:
        """
        解析导入章节，忽略末尾题型目录

        :param db: 数据库会话
        :param bank_id: 题库 ID
        :param level1_name: 一级章节名称
        :param level2_name: 二级章节名称
        :param level3_name: 三级章节名称
        :param chapter_cache: 章节缓存
        :return:
        """
        from backend.app.question_bank.service.question_service import QuestionService

        chapter_names = QuestionImportService._normalize_import_chapter_names(
            level1_name=level1_name,
            level2_name=level2_name,
            level3_name=level3_name,
        )
        return await QuestionService._get_or_create_chapter(
            db=db,
            bank_id=bank_id,
            level1_name=chapter_names[0],
            level2_name=chapter_names[1],
            chapter_cache=chapter_cache,
            level3_name=chapter_names[2],
        )

    @staticmethod
    def _normalize_import_chapter_names(
        *,
        level1_name: str | None,
        level2_name: str | None,
        level3_name: str | None,
    ) -> tuple[str | None, str | None, str | None]:
        """
        规范化导入章节名称

        :param level1_name: 一级章节名称
        :param level2_name: 二级章节名称
        :param level3_name: 三级章节名称
        :return:
        """
        names = [
            QuestionImportService._clean_chapter_name(level1_name),
            QuestionImportService._clean_chapter_name(level2_name),
            QuestionImportService._clean_chapter_name(level3_name),
        ]
        chapter_names = [name for name in names if name]
        if chapter_names and QuestionImportService._is_question_type_chapter(chapter_names[-1]):
            chapter_names.pop()

        while len(chapter_names) < 3:
            chapter_names.append(None)

        return chapter_names[0], chapter_names[1], chapter_names[2]

    @staticmethod
    def _clean_chapter_name(value: str | None) -> str | None:
        """
        清理章节名称

        :param value: 原始章节名称
        :return:
        """
        if value is None:
            return None

        name = str(value).strip()
        if not name:
            return None
        return name

    @staticmethod
    def _is_question_type_chapter(name: str) -> bool:
        """
        判断章节名称是否只是题型

        :param name: 章节名称
        :return:
        """
        return name.strip() in TYPE_MAPPING

    @staticmethod
    def _normalize_stem(stem: str) -> str:
        """
        规范化题干用于去重比对

        :param stem: 原始题干
        :return:
        """
        if not stem:
            return ''
        text = re.sub(r'<[^>]+>', '', stem)
        text = re.sub(r'\s+', '', text)
        text = re.sub(r'[（(）)【】\[\]{}《》""。，、；：？！]', '', text)
        return text.strip()

    @staticmethod
    def _parse_answer(answer_str: str, question_type: str) -> dict:
        """
        解析答案字符串

        :param answer_str: 答案字符串
        :param question_type: 题型
        :return:
        """
        if question_type in ['single', 'judgement']:
            codes = QuestionImportService._extract_option_codes(answer_str)
            return {'correct': codes[0] if codes else ''}

        if question_type == 'multiple':
            answers = QuestionImportService._extract_option_codes(answer_str)
            return {'correct': sorted(set(answers))}

        if question_type in ['fill', 'shortAnswer']:
            answers = QuestionImportService._split_answer_text(answer_str)
            return {'correct': answers}

        return {'correct': answer_str}

    _extract_option_codes = staticmethod(extract_option_codes)
    _split_answer_text = staticmethod(split_answer_text)


question_import_service: QuestionImportService = QuestionImportService()
