#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import logging
import re
from decimal import Decimal
from typing import Any

from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.question_bank.crud.crud_bank import bank_dao
from backend.app.question_bank.crud.crud_chapter import chapter_dao
from backend.app.question_bank.crud.crud_material import material_dao
from backend.app.question_bank.model import (
    Question,
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
from backend.common.exception import errors

log = logging.getLogger(__name__)

# 题型映射
TYPE_MAPPING: dict[str, str] = {
    '单选': 'single', '单选题': 'single',
    '多选': 'multiple', '多选题': 'multiple',
    '判断': 'judgement', '判断题': 'judgement',
    '填空': 'fill', '填空题': 'fill',
    '简答': 'shortAnswer', '简答题': 'shortAnswer',
}

# 难度映射
DIFFICULTY_MAPPING: dict[str, str] = {
    '简单': 'easy',
    '中等': 'medium',
    '困难': 'hard',
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

                difficulty = DIFFICULTY_MAPPING.get(row.难度 or '中等', 'medium')

                chapter_id = await QuestionService._get_or_create_chapter(
                    db=db,
                    bank_id=obj.bank_id,
                    level1_name=row.一级目录,
                    level2_name=row.二级目录,
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
                    'analysis_content': row.解析 if row.解析 else '暂无解析',
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
        chapter_count: dict[int, int] = {}

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

            if row_data['chapter_id']:
                chapter_count[row_data['chapter_id']] = chapter_count.get(row_data['chapter_id'], 0) + 1

        success_count = len(validated_rows)

        # ============ 第三阶段：更新 q_count_cache ============
        if success_count > 0:
            for chap_id, count in chapter_count.items():
                await db.execute(
                    update(QuestionChapter)
                    .where(QuestionChapter.id == chap_id)
                    .values(q_count_cache=QuestionChapter.q_count_cache + count)
                )

            await QuestionService._update_bank_q_count_cache_recursive(
                db=db,
                bank_id=obj.bank_id,
                delta=success_count,
            )

            await db.flush()

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
            raise errors.NotFoundError(msg='题库不存在')

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

        # ============ 第二阶段：构建题干去重索引 ============
        existing_stmt = (
            select(Question.id, Question.stem)
            .join(QuestionPlacement, QuestionPlacement.question_id == Question.id)
            .where(QuestionPlacement.bank_id == bank_id)
        )
        existing_rows = (await db.execute(existing_stmt)).all()
        stem_to_question_id: dict[str, int] = {}
        for q_id, q_stem in existing_rows:
            normalized = QuestionImportService._normalize_stem(q_stem)
            if normalized:
                stem_to_question_id[normalized] = int(q_id)

        # 获取当前题库的最大 sort_order
        max_order_stmt = select(func.coalesce(func.max(QuestionPlacement.sort_order), 0)).where(
            QuestionPlacement.bank_id == bank_id
        )
        max_order = (await db.execute(max_order_stmt)).scalar() or 0

        # ============ 第三阶段：映射和验证 ============
        chapter_cache: dict[str, int] = {}
        results: list[ImportResultItem] = []
        success_count = 0
        dedup_count = 0
        chapter_count: dict[int, int] = {}

        for row_index, row in enumerate(question_rows, start=2):
            try:
                # 题型
                question_type = TYPE_MAPPING.get(row.题型)
                if not question_type:
                    raise ValueError(f'不支持的题型：{row.题型}')

                # 难度
                difficulty = DIFFICULTY_MAPPING.get(row.难度 or '中等', 'medium')

                # 章节
                chapter_id = await QuestionService._get_or_create_chapter(
                    db=db,
                    bank_id=bank_id,
                    level1_name=row.一级目录,
                    level2_name=row.二级目录,
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

                # ============ 去重检查 ============
                stem = row.题目
                normalized_stem = QuestionImportService._normalize_stem(stem)
                existing_qid = stem_to_question_id.get(normalized_stem) if normalized_stem else None

                if existing_qid is not None:
                    # 题目已存在，仅新增挂载
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

                    # 材料关联
                    if material_ids:
                        for mid in material_ids:
                            await db.execute(
                                question_material_relation.insert().values(
                                    question_id=existing_qid,
                                    material_id=mid,
                                    sort_order=0,
                                )
                            )

                    dedup_count += 1
                    results.append(ImportResultItem(
                        row_number=row_index,
                        success=True,
                        question_id=existing_qid,
                        error_message='去重复用',
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
                        content=row.解析 if row.解析 else '暂无解析',
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

                    # 加入去重索引
                    if normalized_stem:
                        stem_to_question_id[normalized_stem] = question.id

                    results.append(ImportResultItem(
                        row_number=row_index,
                        success=True,
                        question_id=question.id,
                    ))

                success_count += 1
                if chapter_id:
                    chapter_count[chapter_id] = chapter_count.get(chapter_id, 0) + 1

            except Exception as e:
                log.warning(f'Excel 导入第 {row_index} 行失败: {e}')
                results.append(ImportResultItem(
                    row_number=row_index,
                    success=False,
                    question_id=None,
                    error_message=str(e),
                ))

        # ============ 第四阶段：更新缓存计数 ============
        new_count = success_count - dedup_count
        if new_count > 0:
            for chap_id, count in chapter_count.items():
                await db.execute(
                    update(QuestionChapter)
                    .where(QuestionChapter.id == chap_id)
                    .values(q_count_cache=QuestionChapter.q_count_cache + count)
                )
            await QuestionService._update_bank_q_count_cache_recursive(
                db=db, bank_id=bank_id, delta=new_count,
            )
            await db.flush()

        fail_count = len(question_rows) - success_count
        return ExcelImportResult(
            total=len(question_rows),
            success_count=success_count,
            fail_count=fail_count,
            details=results,
            materials_count=len(material_id_map),
            dedup_count=dedup_count,
        )

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
            '一级目录': '一级目录', '二级目录': '二级目录',
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
            pass

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
                '知识点', '材料编号',
            ])
            ws1.append([
                1, '单选', '下列关于宪法的说法，正确的是（ ）',
                '宪法具有最高法律效力', '宪法由全国人大常委会制定',
                '宪法修改由国务院提议', '宪法不具有直接法律效力',
                'A', '根据《宪法》规定，宪法具有最高法律效力。',
                '中等', 1, '常识判断', None, '宪法学', None,
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
            raise errors.NotFoundError(msg='题库不存在')

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
            c_name = q_data.get('chapter_name')
            if c_name:
                chapter_id = await QuestionService._get_or_create_chapter(
                    db=db, bank_id=bank_id, level1_name=c_name, level2_name=None, chapter_cache=chapter_cache,
                )

            # 2b. 基本字段
            q_type = q_data.get('type') or 'single'
            q_diff = q_data.get('difficulty') or 'medium'
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

        # -------- 3. 更新题库 q_count_cache --------
        if success_count > 0:
            await QuestionService._update_bank_q_count_cache_recursive(
                db=db, bank_id=bank_id, delta=success_count,
            )
            await db.flush()

        return {
            'materials_count': len(materials_data),
            'questions_count': success_count,
        }

    # ------------------------------------------------------------------
    #  内部工具
    # ------------------------------------------------------------------

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
        text = re.sub(r'[（(）)【】\[\]{}《》""''。，、；：？！]', '', text)
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

    @staticmethod
    def _extract_option_codes(text: str | list[str]) -> list[str]:
        """
        提取选项编码

        :param text: 答案文本
        :return:
        """
        if isinstance(text, list):
            raw = ','.join([str(item) for item in text if str(item).strip()])
        else:
            raw = str(text or '')

        raw = raw.strip().upper()
        if not raw:
            return []

        parts = re.split(r'[\s,，、|]+', raw)
        codes: list[str] = []
        for part in parts:
            token = part.strip()
            if not token:
                continue
            if token.isalpha():
                codes.extend(list(token)) if len(token) > 1 else codes.append(token)
                continue
            letters = [ch for ch in token if ch.isalpha()]
            if not letters:
                continue
            if len(letters) == 1:
                codes.append(letters[0])
            else:
                codes.extend(letters)

        return codes

    @staticmethod
    def _split_answer_text(answer_str: str) -> list[str]:
        """
        分割答案文本

        :param answer_str: 答案字符串
        :return:
        """
        if not answer_str:
            return []
        text = str(answer_str)
        for sep in ['\r\n', '\n', '\r', '，', ';', '；', '|', '\\', '、']:
            text = text.replace(sep, ',')
        return [item.strip() for item in text.split(',') if item.strip()]


question_import_service: QuestionImportService = QuestionImportService()
