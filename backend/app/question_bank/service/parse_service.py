#!/usr/bin/env python3
import json
import logging
import uuid

from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from backend.app.question_bank.crud.crud_bank import bank_dao
from backend.app.question_bank.schema.parse import ReviewJobUpdateParam
from backend.core.path_conf import UPLOAD_DIR
from backend.plugin.ocr.service.ocr_service import ocr_service
from backend.plugin.ocr.service.providers.base import OCRDocumentParseResultData
from backend.utils.file_ops import upload_file
from backend.utils.path_safety import safe_path_segment

log = logging.getLogger(__name__)


class ParseService:
    @staticmethod
    async def parse_pdf_to_ocr_result(file_path: Path, images_dir_name: str) -> OCRDocumentParseResultData:
        """
        调用 OCR 插件解析 PDF

        :param file_path: PDF 文件路径
        :param images_dir_name: 图片保存目录名
        :return:
        """
        if not images_dir_name:
            raise ValueError("必须提供 images_dir_name 参数")

        file_bytes = await run_in_threadpool(file_path.read_bytes)
        result = await ocr_service.parse_document_bytes(
            filename=file_path.name,
            content=file_bytes,
            content_type='application/pdf',
            output_format='markdown',
            images_dir_name=images_dir_name,
            wait=True,
        )
        log.info(f'OCR 插件解析 PDF 成功，provider={result.provider}, job_id={result.job_id}')
        return result

    @staticmethod
    async def parse_pdf_to_markdown(file_path: Path, images_dir_name: str) -> str:
        """
        调用 OCR 插件将 PDF 转为 Markdown

        :param file_path: PDF 文件路径
        :param images_dir_name: 图片保存目录名
        :return:
        """
        result = await ParseService.parse_pdf_to_ocr_result(file_path=file_path, images_dir_name=images_dir_name)
        return result.content

    @staticmethod
    async def _export_markdown(md_content: str, filename_stem: str) -> dict[str, Any]:
        """
        导出 Markdown 文件

        :param md_content: Markdown 内容
        :param filename_stem: 文件名前缀
        :return:
        """
        export_dir = UPLOAD_DIR / 'parse_export'
        export_dir.mkdir(parents=True, exist_ok=True)
        safe_stem = safe_path_segment(filename_stem, default='document')
        md_file_name = f'{safe_stem}_{uuid.uuid4().hex[:8]}.md'
        md_file_path = export_dir / md_file_name
        await run_in_threadpool(md_file_path.write_text, md_content, encoding='utf-8')
        return {
            'md_url': f'parse_export/{md_file_name}',
            'md_length': len(md_content),
            'file_name': md_file_name,
        }

    @staticmethod
    async def _export_text(text_content: str, filename_stem: str) -> dict[str, Any]:
        """
        导出 Text 文件

        :param text_content: Text 内容
        :param filename_stem: 文件名前缀
        :return:
        """
        export_dir = UPLOAD_DIR / 'parse_export'
        export_dir.mkdir(parents=True, exist_ok=True)
        safe_stem = safe_path_segment(filename_stem, default='document')
        text_file_name = f'{safe_stem}_{uuid.uuid4().hex[:8]}.txt'
        text_file_path = export_dir / text_file_name
        await run_in_threadpool(text_file_path.write_text, text_content, encoding='utf-8')
        return {
            'text_url': f'parse_export/{text_file_name}',
            'text_length': len(text_content),
            'text_file_name': text_file_name,
        }

    @staticmethod
    async def _recover_text_content(job_id: str | None) -> str:
        """
        从云端 OCR 任务恢复纯文本

        :param job_id: 云端 OCR 任务 ID
        :return:
        """
        if not job_id:
            return ''

        try:
            result = await ocr_service.recover_document(
                job_id=job_id,
                output_format='text',
                download_images=False,
            )
        except Exception as exc:
            log.warning(f'恢复 OCR Text 失败，job_id={job_id}: {exc!s}')
            return ''

        return result.content

    @staticmethod
    async def _export_markdown_with_text(
        md_content: str,
        filename_stem: str,
        text_content: str | None,
        job_id: str | None,
    ) -> dict[str, Any]:
        """
        导出 Markdown 和 Text 文件

        :param md_content: Markdown 内容
        :param filename_stem: 文件名前缀
        :param text_content: Text 内容
        :param job_id: 云端 OCR 任务 ID
        :return:
        """
        data = await ParseService._export_markdown(md_content, filename_stem)
        if not text_content:
            text_content = await ParseService._recover_text_content(job_id)
        if not text_content:
            return data

        text_data = await ParseService._export_text(text_content, filename_stem)
        data.update(text_data)
        return data

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
        from backend.app.question_bank.service.question_import_service import question_import_service

        return await question_import_service.smart_commit(
            db=db,
            bank_id=bank_id,
            materials_data=materials_data,
            questions_data=questions_data,
            user_id=user_id,
        )

    @staticmethod
    async def upload_and_parse_pdf_file(file: UploadFile) -> dict[str, Any]:
        """
        上传并解析 PDF 试卷为 Markdown

        :param file: 上传的文件对象
        :return: 包含 markdown 内容的字典
        """
        if not file.filename.lower().endswith('.pdf'):
            raise ValueError('请上传 .pdf 格式文件')

        temp_folder = 'temp_pdf'
        filename = await upload_file(file, folder=temp_folder)
        file_path = UPLOAD_DIR / filename

        folder_name = file.filename.rsplit('.', 1)[0]
        md_content = await ParseService.parse_pdf_to_markdown(
            file_path=file_path,
            images_dir_name=folder_name,
        )
        return {'markdown': md_content}

    @staticmethod
    async def convert_pdf_to_markdown_only(
        db: AsyncSession,
        file: UploadFile,
        bank_id: int,
    ) -> dict[str, Any]:
        """
        仅将 PDF 转为 Markdown

        :param db: 数据库会话
        :param file: 上传的 PDF 文件
        :param bank_id: 题库 ID
        :return:
        """
        if not file.filename.lower().endswith('.pdf'):
            raise ValueError('请上传 .pdf 格式文件')

        bank = await bank_dao.get(db, bank_id)
        if not bank:
            raise ValueError('题库不存在')

        filename = await upload_file(file, folder='temp_pdf')
        file_path = UPLOAD_DIR / filename
        safe_bank_name = safe_path_segment(bank.name, default='bank')
        result = await ParseService.parse_pdf_to_ocr_result(
            file_path=file_path,
            images_dir_name=safe_bank_name,
        )

        return await ParseService._export_markdown_with_text(
            result.content,
            f'markdown_{Path(file.filename).stem}',
            result.text_content,
            result.job_id,
        )

    @staticmethod
    async def recover_markdown_from_ocr_job(
        db: AsyncSession,
        bank_id: int,
        job_id: str,
        download_images: bool = False,
    ) -> dict[str, Any]:
        """
        从云端 OCR 任务恢复 Markdown

        :param db: 数据库会话
        :param bank_id: 题库 ID
        :param job_id: 云端 OCR 任务 ID
        :param download_images: 是否同时下载图片
        :return:
        """
        bank = await bank_dao.get(db, bank_id)
        if not bank:
            raise ValueError('题库不存在')

        safe_bank_name = safe_path_segment(bank.name, default='bank')
        result = await ocr_service.recover_document(
            job_id=job_id,
            output_format='markdown',
            images_dir_name=safe_bank_name,
            download_images=download_images,
        )

        data = await ParseService._export_markdown_with_text(
            result.content,
            f'ocr_{result.job_id or job_id}',
            result.text_content,
            result.job_id or job_id,
        )
        data.update({
            'job_id': result.job_id,
            'status': result.status,
        })
        return data

    @staticmethod
    def _review_dir() -> Path:
        """获取审核任务目录"""
        review_dir = UPLOAD_DIR / 'parse_review'
        review_dir.mkdir(parents=True, exist_ok=True)
        return review_dir

    @staticmethod
    def _review_job_path(job_id: str) -> Path:
        """
        获取审核任务路径

        :param job_id: 审核任务 ID
        :return:
        """
        safe_job_id = ''.join([char for char in job_id if char.isalnum() or char in ('_', '-')])
        return ParseService._review_dir() / f'{safe_job_id}.json'

    @staticmethod
    async def _read_review_job(job_id: str) -> dict[str, Any]:
        """
        读取审核任务

        :param job_id: 审核任务 ID
        :return:
        """
        job_path = ParseService._review_job_path(job_id)
        if not job_path.exists():
            raise ValueError('审核任务不存在')
        content = await run_in_threadpool(job_path.read_text, encoding='utf-8')
        return json.loads(content)

    @staticmethod
    async def _write_review_job(job_data: dict[str, Any]) -> None:
        """
        写入审核任务

        :param job_data: 审核任务数据
        :return:
        """
        job_path = ParseService._review_job_path(job_data['job_id'])
        text = json.dumps(job_data, ensure_ascii=False, indent=2)
        await run_in_threadpool(job_path.write_text, text, encoding='utf-8')

    @staticmethod
    async def create_review_job_stream(
        db: AsyncSession,
        file: UploadFile,
        bank_id: int,
        provider_id: int = 4,
        user_id: int | None = None,
        extract_mode: str = 'question',
    ) -> AsyncGenerator[dict[str, Any], None]:
        """
        流式创建 AI 审核任务

        :param db: 数据库会话
        :param file: 上传文件
        :param bank_id: 题库 ID
        :param provider_id: AI 供应商 ID
        :param user_id: 用户 ID
        :param extract_mode: 抽取模式
        :return:
        """
        from backend.app.question_bank.service.review_parse_service import review_parse_service

        if extract_mode not in {'question', 'answer'}:
            raise ValueError('不支持的解析模式')

        is_pdf = file.filename.lower().endswith('.pdf')
        is_md = file.filename.lower().endswith('.md')
        if not (is_pdf or is_md):
            raise ValueError('请上传 .pdf 或 .md 格式文件')

        bank = await bank_dao.get(db, bank_id)
        if not bank:
            raise ValueError('题库不存在')

        yield {'type': 'stage', 'stage': 'parse', 'message': '正在解析文档...'}

        filename = await upload_file(file, folder='temp_pdf')
        file_path = UPLOAD_DIR / filename
        if is_pdf:
            md_content = await ParseService.parse_pdf_to_markdown(
                file_path=file_path,
                images_dir_name=bank.name,
            )
        else:
            md_content = await run_in_threadpool(file_path.read_text, encoding='utf-8')

        job_id = uuid.uuid4().hex
        review_dir = ParseService._review_dir()
        md_file_name = f'{job_id}.md'
        md_file_path = review_dir / md_file_name
        await run_in_threadpool(md_file_path.write_text, md_content, encoding='utf-8')

        yield {
            'type': 'stage',
            'stage': 'parse_done',
            'message': f'文档解析完成，共 {len(md_content)} 字符',
            'md_length': len(md_content),
            'md_url': f'parse_review/{md_file_name}',
        }

        yield {'type': 'stage', 'stage': 'segment', 'message': '正在分段...'}

        segments = review_parse_service.build_review_segments(md_content)
        yield {
            'type': 'stage',
            'stage': 'segment_done',
            'message': f'分段完成，识别到 {len(segments)} 段',
            'segments_count': len(segments),
        }

        yield {'type': 'stage', 'stage': 'ai_extract', 'message': '正在进行 AI 智能提取...'}

        materials: list[dict[str, Any]] = []
        questions: list[dict[str, Any]] = []
        answers: list[dict[str, Any]] = []
        warnings: list[str] = []
        if extract_mode == 'answer':
            async for event in review_parse_service.extract_answers_with_ai(db, segments, provider_id):
                if event['type'] == 'progress':
                    yield event
                if event['type'] == 'complete':
                    answers = event.get('answers', [])
                    warnings = event.get('warnings', [])
        else:
            async for event in review_parse_service.extract_review_with_ai(db, segments, provider_id):
                if event['type'] == 'progress':
                    yield event
                if event['type'] == 'complete':
                    materials = event.get('materials', [])
                    questions = event.get('questions', [])
                    answers = event.get('answers', [])
                    warnings = event.get('warnings', [])

        yield {
            'type': 'stage',
            'stage': 'ai_extract_done',
            'message': f'AI 提取完成，题目 {len(questions)} 道，答案解析 {len(answers)} 条',
            'questions_count': len(questions),
            'answers_count': len(answers),
        }

        job_data = {
            'job_id': job_id,
            'status': 'pending_review',
            'bank_id': bank_id,
            'bank_name': bank.name,
            'provider_id': provider_id,
            'file_name': file.filename,
            'file_type': 'pdf' if is_pdf else 'md',
            'extract_mode': extract_mode,
            'user_id': user_id,
            'md_url': f'parse_review/{md_file_name}',
            'excel_url': None,
            'segments': segments,
            'materials': materials,
            'questions': ParseService._normalize_review_questions(questions),
            'answers': ParseService._normalize_review_answers(answers),
            'warnings': warnings,
            'materials_count': len(materials),
            'questions_count': len(questions),
            'answers_count': len(answers),
            'segments_count': len(segments),
        }
        await ParseService._write_review_job(job_data)

        yield {
            'type': 'done',
            'message': '审核任务已创建',
            'job': job_data,
            'job_id': job_id,
            'materials_count': len(materials),
            'questions_count': len(questions),
            'answers_count': len(answers),
            'segments_count': len(segments),
            'warnings_count': len(warnings),
        }

    @staticmethod
    def _normalize_review_questions(questions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        规范化审核题目

        :param questions: 题目列表
        :return:
        """
        normalized: list[dict[str, Any]] = []
        for index, question in enumerate(questions, start=1):
            item = dict(question)
            item['question_id'] = str(item.get('question_id') or f'Q{index}')
            item['sort_order'] = item.get('sort_order') or index
            item['status'] = item.get('status') or 'pending_review'
            item['warnings'] = item.get('warnings') or []
            if not str(item.get('stem') or '').strip():
                warning = '题干为空，疑似答案解析册条目，不能直接作为新题入库'
                if warning not in item['warnings']:
                    item['warnings'].append(warning)
            chapter_level1_name = (
                item.get('chapter_level1_name')
                or item.get('一级目录')
                or item.get('chapter_name')
            )
            item['chapter_level1_name'] = chapter_level1_name
            item['chapter_level2_name'] = item.get('chapter_level2_name') or item.get('二级目录')
            item['chapter_level3_name'] = item.get('chapter_level3_name') or item.get('三级目录')
            item['chapter_name'] = item.get('chapter_name') or chapter_level1_name
            normalized.append(item)
        return normalized

    @staticmethod
    def _normalize_review_answers(answers: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        规范化审核答案解析

        :param answers: 答案解析列表
        :return:
        """
        normalized: list[dict[str, Any]] = []
        for index, answer_item in enumerate(answers, start=1):
            item = dict(answer_item)
            item['answer_id'] = str(item.get('answer_id') or f'A{index}')
            item['sort_order'] = item.get('sort_order') or index
            item['status'] = item.get('status') or 'pending_review'
            item['warnings'] = item.get('warnings') or []
            answer_data = item.get('answer_data')
            if not isinstance(answer_data, dict):
                answer_data = {}
            item['answer_data'] = answer_data
            if not answer_data.get('correct') and not str(item.get('analysis_content') or '').strip():
                warning = '答案和解析均为空'
                if warning not in item['warnings']:
                    item['warnings'].append(warning)
            normalized.append(item)
        return normalized

    @staticmethod
    async def get_review_job(job_id: str) -> dict[str, Any]:
        """
        获取审核任务

        :param job_id: 审核任务 ID
        :return:
        """
        return await ParseService._read_review_job(job_id)

    @staticmethod
    async def update_review_job(job_id: str, param: ReviewJobUpdateParam) -> dict[str, Any]:
        """
        更新审核任务

        :param job_id: 审核任务 ID
        :param param: 更新参数
        :return:
        """
        job_data = await ParseService._read_review_job(job_id)
        job_data['materials'] = [item.model_dump() for item in param.materials]
        job_data['questions'] = [item.model_dump() for item in param.questions]
        job_data['answers'] = [item.model_dump() for item in param.answers]
        job_data['segments'] = param.segments
        job_data['status'] = param.status
        job_data['materials_count'] = len(job_data['materials'])
        job_data['questions_count'] = len(job_data['questions'])
        job_data['answers_count'] = len(job_data['answers'])
        job_data['segments_count'] = len(job_data['segments'])
        await ParseService._write_review_job(job_data)
        return job_data

    @staticmethod
    async def export_review_job_excel(job_id: str) -> dict[str, Any]:
        """
        导出审核任务 Excel

        :param job_id: 审核任务 ID
        :return:
        """
        from backend.app.question_bank.service.review_parse_service import review_parse_service

        job_data = await ParseService._read_review_job(job_id)
        excel_filename = f'review_{job_id}.xlsx'
        excel_path = ParseService._review_dir() / excel_filename
        _, warnings_count = await run_in_threadpool(
            review_parse_service.export_review_to_excel,
            materials=job_data.get('materials', []),
            questions=job_data.get('questions', []),
            answers=job_data.get('answers', []),
            output_path=excel_path,
        )
        job_data['excel_url'] = f'parse_review/{excel_filename}'
        job_data['warnings_count'] = warnings_count
        await ParseService._write_review_job(job_data)
        return {
            'excel_url': job_data['excel_url'],
            'warnings_count': warnings_count,
        }

    @staticmethod
    async def commit_review_job(db: AsyncSession, job_id: str, user_id: int) -> dict[str, Any]:
        """
        提交审核任务入库

        :param db: 数据库会话
        :param job_id: 审核任务 ID
        :param user_id: 用户 ID
        :return:
        """
        job_data = await ParseService._read_review_job(job_id)
        materials = [
            item for item in job_data.get('materials', [])
            if item.get('status') != 'rejected'
        ]
        questions = [
            item for item in job_data.get('questions', [])
            if item.get('status') != 'rejected'
        ]
        questions = ParseService._normalize_review_questions(questions)
        skipped_empty_stem_count = len([
            item for item in questions
            if not str(item.get('stem') or '').strip()
        ])
        questions = [
            item for item in questions
            if str(item.get('stem') or '').strip()
        ]
        answers = job_data.get('answers', [])
        if not questions and answers:
            raise ValueError('当前审核任务只有答案解析，请复制到原题后再入库')
        if skipped_empty_stem_count > 0 and not questions:
            raise ValueError('当前审核任务没有可直接入库的完整题目，疑似只有答案解析，请先匹配原题后再入库')

        result = await ParseService.smart_commit(
            db=db,
            bank_id=job_data['bank_id'],
            materials_data=materials,
            questions_data=questions,
            user_id=user_id,
        )
        if skipped_empty_stem_count > 0:
            result['skipped_empty_stem_count'] = skipped_empty_stem_count
            job_warnings = job_data.get('warnings') or []
            job_warnings.append(f'已跳过 {skipped_empty_stem_count} 条题干为空的解析册条目')
            job_data['warnings'] = job_warnings
        job_data['status'] = 'committed'
        job_data['commit_result'] = result
        await ParseService._write_review_job(job_data)
        return result


parse_service = ParseService()
