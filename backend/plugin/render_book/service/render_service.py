#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio
import json
import mimetypes

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import anyio
import httpx

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.question_bank.service.category_filter_service import category_filter_service
from backend.common.exception import errors
from backend.common.log import log
from backend.common.pagination import _CustomPageParams, paging_list_data
from backend.core.conf import settings
from backend.database.db import async_db_session
from backend.plugin.render_book.crud import render_book_job_dao, render_book_job_file_dao
from backend.plugin.render_book.model import RenderBookJob, RenderBookJobFile
from backend.plugin.render_book.schema.payload import RenderDocumentPayload
from backend.plugin.render_book.schema.render import (
    JobStatus,
    RenderArtifactKind,
    RenderFileKind,
    RenderJobCreate,
    RenderJobFileRead,
    RenderJobListParams,
    RenderJobRead,
    RenderJobValidationResult,
    RenderOptions,
    RenderOutputTargets,
    RenderTemplateDetail,
    RenderTemplatePreviewRequest,
    RenderTemplatePreviewResponse,
    RenderTemplateSummary,
    RenderValidationIssue,
    RenderVariant,
)
from backend.plugin.render_book.service.payload_service import render_payload_service
from backend.plugin.render_book.service.quota_service import render_book_quota_service
from backend.plugin.render_book.utils import get_template_registry


class RenderService:
    def __init__(self) -> None:
        self._template_registry = get_template_registry()

    @property
    def jobs_root(self) -> Path:
        root = Path(settings.RENDER_BOOK_STORAGE_ROOT)
        jobs_root = root / 'jobs'
        jobs_root.mkdir(parents=True, exist_ok=True)
        return jobs_root

    async def list_templates(self) -> list[RenderTemplateSummary]:
        return [RenderTemplateSummary.model_validate(item.model_dump()) for item in self._template_registry.values()]

    async def get_template(self, template_key: str) -> RenderTemplateDetail | None:
        return self._template_registry.get(template_key)

    async def validate_job(self, payload: RenderJobCreate) -> RenderJobValidationResult:
        issues: list[RenderValidationIssue] = []
        template = self._template_registry.get(payload.template_key)
        normalized_title = payload.title.strip()

        if template is None:
            issues.append(
                RenderValidationIssue(field='template_key', level='error', message='模板不存在，请选择有效模板。')
            )
        if not normalized_title:
            issues.append(RenderValidationIssue(field='title', level='error', message='题本标题不能为空。'))

        self._validate_positive_integer(payload.filters, 'question_count', issues)
        self._validate_positive_integer(payload.filters, 'wrong_only_recent_days', issues)
        self._validate_positive_integer(payload.filters, 'bank_id', issues)
        self._validate_positive_integer(payload.filters, 'chapter_id', issues)
        self._validate_positive_integer(payload.filters, 'cat_id', issues)
        self._validate_positive_integer(payload.filters, 'year_start', issues)
        self._validate_positive_integer(payload.filters, 'year_end', issues)
        self._validate_list_of_type(payload.filters, 'question_types', str, issues)
        self._validate_list_of_type(payload.filters, 'difficulties', str, issues)
        self._validate_list_of_type(payload.filters, 'knowledge_points', str, issues)
        self._validate_question_ids(payload.filters.get('question_ids'), issues)

        year_start = payload.filters.get('year_start')
        year_end = payload.filters.get('year_end')
        if isinstance(year_start, int) and (year_start < 1900 or year_start > 2100):
            issues.append(
                RenderValidationIssue(
                    field='filters.year_start', level='warning', message='起始年份建议在 1900-2100 之间。'
                )
            )
        if isinstance(year_end, int) and (year_end < 1900 or year_end > 2100):
            issues.append(
                RenderValidationIssue(
                    field='filters.year_end', level='warning', message='结束年份建议在 1900-2100 之间。'
                )
            )

        if (
            payload.mode == 'preview'
            and isinstance(payload.filters.get('question_count'), int)
            and payload.filters['question_count'] > 50
        ):
            issues.append(
                RenderValidationIssue(
                    field='filters.question_count',
                    level='warning',
                    message='预览模式建议题量不超过 50，以提升预览速度。',
                )
            )

        if payload.options.include_analysis and not payload.options.include_answer:
            issues.append(
                RenderValidationIssue(
                    field='options.include_analysis',
                    level='warning',
                    message='开启解析通常也建议同时展示答案。',
                )
            )

        try:
            render_payload_service.resolve_export_config(payload)
        except ValueError as exc:
            issues.append(
                RenderValidationIssue(
                    field='content_mode',
                    level='error',
                    message=str(exc),
                )
            )

        if (
            payload.template_key == 'exam_paper'
            and not payload.filters.get('bank_id')
            and not payload.filters.get('question_ids')
        ):
            issues.append(
                RenderValidationIssue(
                    field='filters.bank_id',
                    level='warning',
                    message='真题套卷建议指定 bank_id 或 question_ids，以便锁定具体试卷。',
                )
            )

        if payload.template_key == 'wrong_question' and not payload.metadata.get('user_id'):
            issues.append(
                RenderValidationIssue(
                    field='metadata.user_id',
                    level='error',
                    message='错题重刷模板需要传入 metadata.user_id。',
                )
            )

        has_advanced_filters = any([
            payload.filters.get('cat_id'),
            payload.filters.get('region'),
            payload.filters.get('year_start'),
            payload.filters.get('year_end'),
            payload.filters.get('knowledge_points'),
            payload.filters.get('question_types'),
            payload.filters.get('difficulties'),
            payload.filters.get('stem_keyword'),
            payload.filters.get('option_keyword'),
            payload.filters.get('analysis_keyword'),
        ])
        if (
            payload.template_key not in {'wrong_question', 'hanyu', 'basic_calculation'}
            and not payload.filters.get('bank_id')
            and not payload.filters.get('chapter_id')
            and not payload.filters.get('question_ids')
            and not has_advanced_filters
        ):
            issues.append(
                RenderValidationIssue(
                    field='filters',
                    level='warning',
                    message='建议至少提供 bank_id、chapter_id 或 question_ids 之一，避免题本范围过大。',
                )
            )

        summary = None
        if template is not None:
            summary = RenderTemplateSummary.model_validate(template.model_dump())

        has_error = any(issue.level == 'error' for issue in issues)
        return RenderJobValidationResult(
            valid=not has_error,
            normalized_title=normalized_title,
            template=summary,
            issues=issues,
        )

    async def preview_payload(self, *, db: AsyncSession, payload: RenderJobCreate) -> RenderDocumentPayload:
        validation = await self.validate_job(payload)
        errors = [issue.message for issue in validation.issues if issue.level == 'error']
        if errors:
            raise ValueError('；'.join(errors))
        return await render_payload_service.build_payload(db=db, payload=payload)

    async def preview_template_pdf(
        self,
        *,
        db: AsyncSession,
        payload: RenderTemplatePreviewRequest,
    ) -> RenderTemplatePreviewResponse:
        validation = await self.validate_job(payload)
        errors = [issue.message for issue in validation.issues if issue.level == 'error']
        if errors:
            raise ValueError('；'.join(errors))

        document_payload = await render_payload_service.build_payload(db=db, payload=payload)
        resolved_metadata = self._merge_preview_metadata(
            base_metadata=document_payload.metadata,
            request_metadata=payload.metadata,
            layout_params=payload.layout_params,
        )
        document_payload = document_payload.model_copy(update={'metadata': resolved_metadata})

        available_variants = list(document_payload.render_plan.render_variants or [])
        if not available_variants:
            raise ValueError('当前模板未解析出可用渲染变体。')

        render_variant = payload.render_variant or available_variants[0]
        if render_variant not in available_variants:
            raise ValueError(f'预览变体 {render_variant} 不在当前任务允许的渲染范围内。')

        preview_job_payload = payload.model_copy(update={'mode': 'preview'})
        job = await self.create_job(preview_job_payload, db=db)
        if job.payload_path:
            self._write_json(Path(job.payload_path), document_payload.model_dump(mode='json'))

        quota_user_id = self._coerce_positive_int(job.metadata.get('user_id'))
        quota_source_ref = f'render_preview:{job.job_id}'
        quota_decision = None
        try:
            if quota_user_id is not None:
                quota_decision = await render_book_quota_service.consume_quota(
                    db=db,
                    user_id=quota_user_id,
                    source_ref=quota_source_ref,
                )
            await self.mark_job_running(db=db, job_id=job.job_id)

            executor_result = await self._call_render_executor(
                template_key=job.template_key,
                job_id=job.job_id,
                render_variant=render_variant,
                context=document_payload.model_dump(mode='json'),
            )
            downloaded_pdf = await self._download_executor_artifact(
                job_id=job.job_id,
                render_variant=render_variant,
                artifact_kind='pdf',
                artifact_path=executor_result.get('pdf_download_path'),
            )
            await self._download_executor_artifact(
                job_id=job.job_id,
                render_variant=render_variant,
                artifact_kind='log',
                artifact_path=executor_result.get('log_download_path'),
                required=False,
            )

            file_record = await self.register_output_file(
                db=db,
                job_id=job.job_id,
                file_kind=self._variant_to_file_kind(render_variant),
                local_path=downloaded_pdf,
                render_variant=render_variant,
                filename=downloaded_pdf.name,
                upload_to_oss=payload.upload_to_oss,
            )
            if file_record.status != 'available':
                raise errors.ServerError(msg=file_record.error_message or f'{render_variant} 预览产物登记失败')

            preview_pdf_url = (
                file_record.url
                or self._resolve_executor_artifact_url(executor_result.get('pdf_download_path'))
                or file_record.local_path
            )
            await self.mark_job_succeeded(
                db=db,
                job_id=job.job_id,
                output_path=preview_pdf_url,
            )

            final_job = await self.get_job(job.job_id, db=db)
            if final_job is None:
                raise errors.NotFoundError(msg='渲染任务不存在')

            return RenderTemplatePreviewResponse(
                job=final_job,
                render_variant=render_variant,
                pdf_url=self.build_preview_pdf_url(job_id=job.job_id, render_variant=render_variant),
                payload=document_payload.model_dump(mode='json'),
                resolved_metadata=resolved_metadata,
            )
        except Exception as exc:
            if quota_user_id is not None and quota_decision is not None:
                await render_book_quota_service.refund_quota(
                    db=db,
                    user_id=quota_user_id,
                    decision=quota_decision,
                    source_ref=quota_source_ref,
                )
            await self.mark_job_failed(db=db, job_id=job.job_id, error_message=str(exc))
            raise

    async def get_preview_pdf_file(
        self,
        *,
        db: AsyncSession,
        job_id: str,
        render_variant: RenderVariant | None = None,
    ) -> RenderJobFileRead:
        job = await self.get_job(job_id, db=db)
        if job is None:
            raise errors.NotFoundError(msg='渲染任务不存在')

        target_variant = render_variant
        if target_variant is None:
            target_variant = next((item.render_variant for item in job.files if item.render_variant), None)
            if target_variant is None and job.render_variants:
                target_variant = job.render_variants[0]

        if target_variant is None:
            raise errors.NotFoundError(msg='当前任务缺少可预览的 PDF 产物')

        file_kind = self._variant_to_file_kind(target_variant)
        matched = next(
            (
                item
                for item in job.files
                if item.status == 'available'
                and item.file_kind == file_kind
                and item.render_variant == target_variant
                and item.local_path
            ),
            None,
        )
        if matched is None:
            raise errors.NotFoundError(msg='当前任务的预览 PDF 尚未生成或本地文件不存在')

        file_path = Path(matched.local_path)
        async_file_path = anyio.Path(file_path)
        if not await async_file_path.exists() or not await async_file_path.is_file():
            raise errors.NotFoundError(msg='预览 PDF 文件不存在，请重新生成预览')

        return matched

    @staticmethod
    def build_preview_pdf_url(*, job_id: str, render_variant: RenderVariant | None = None) -> str:
        base_path = f'{settings.FASTAPI_API_V1_PATH}/render-books/jobs/{job_id}/preview.pdf'
        if render_variant:
            return f'{base_path}?render_variant={render_variant}'
        return base_path

    async def create_job(self, payload: RenderJobCreate, db: AsyncSession | None = None) -> RenderJobRead:
        validation = await self.validate_job(payload)
        errors = [issue.message for issue in validation.issues if issue.level == 'error']
        if errors:
            raise ValueError('；'.join(errors))

        template = await self.get_template(payload.template_key)
        now = datetime.now(timezone.utc)
        job_id = uuid4().hex
        job_dir = self.jobs_root / job_id
        job_dir.mkdir(parents=True, exist_ok=True)

        book_kind = render_payload_service.resolve_book_kind(payload)
        content_mode, answer_layout, delivery_mode = render_payload_service.resolve_export_config(payload)
        solution_mode = render_payload_service.resolve_solution_mode(payload)
        render_variants = render_payload_service.resolve_render_variants(payload, solution_mode)

        payload_path = None
        question_count = None
        material_count = None
        if db is not None:
            document_payload = await render_payload_service.build_payload(db=db, payload=payload)
            payload_path = job_dir / 'payload.json'
            self._write_json(payload_path, document_payload.model_dump(mode='json'))
            question_count = document_payload.paper.question_count
            material_count = document_payload.paper.material_count

        record = RenderJobRead(
            job_id=job_id,
            status='accepted',
            mode=payload.mode,
            template_key=payload.template_key,
            title=validation.normalized_title,
            subtitle=payload.subtitle,
            subject=payload.subject or (template.subject if template else None),
            book_kind=book_kind,
            content_mode=content_mode,
            answer_layout=answer_layout,
            delivery_mode=delivery_mode,
            solution_mode=solution_mode,
            filters=payload.filters,
            options=payload.options,
            output_targets=payload.output_targets,
            render_variants=render_variants,
            metadata={
                **payload.metadata,
                'executor_mode': settings.RENDER_BOOK_EXECUTOR_MODE,
                'executor_url': settings.RENDER_BOOK_EXECUTOR_URL,
            },
            payload_path=str(payload_path) if payload_path else None,
            question_count=question_count,
            material_count=material_count,
            output_path=None,
            error_message=None,
            files=[],
            created_at=now,
            updated_at=now,
        )

        self._write_json(job_dir / 'request.json', payload.model_dump(mode='json'))
        self._write_json(job_dir / 'job.json', record.model_dump(mode='json'))

        if db is not None:
            await self._persist_job(db=db, record=record)

        return record

    async def get_job(self, job_id: str, db: AsyncSession | None = None) -> RenderJobRead | None:
        if db is not None:
            job = await render_book_job_dao.get_by_job_id(db, job_id, with_files=True)
            if job is not None:
                return self._job_to_read(job)

        job_file = self.jobs_root / job_id / 'job.json'
        if not job_file.exists():
            return None
        return RenderJobRead.model_validate_json(job_file.read_text(encoding='utf-8'))

    async def list_jobs(
        self,
        *,
        db: AsyncSession,
        params: RenderJobListParams,
    ) -> dict:
        bank_ids: set[int] | None = None
        if params.cat_id is not None:
            category_filter = await category_filter_service.get_question_filter(
                db=db,
                cat_id=params.cat_id,
                kp_cat_id=params.kp_cat_id,
            )
            bank_ids = category_filter.bank_ids if category_filter else set()

        stmt = render_book_job_dao.build_list_stmt(
            job_id=params.job_id,
            status=params.status,
            template_key=params.template_key,
            mode=params.mode,
            user_id=params.user_id,
            keyword=params.keyword,
            cat_id=params.cat_id,
            kp_cat_id=params.kp_cat_id,
            bank_ids=bank_ids,
            with_files=True,
        )
        result = await db.execute(stmt)
        records = [self._job_to_read(item) for item in result.scalars().all()]
        page_params = _CustomPageParams(page=params.page, size=params.size)
        return paging_list_data(records, page_params)

    async def update_job_status(
        self,
        *,
        db: AsyncSession,
        job_id: str,
        status: JobStatus,
        error_message: str | None = None,
        output_path: str | None = None,
    ) -> RenderJobRead:
        job = await render_book_job_dao.get_by_job_id(db, job_id)
        if job is None:
            raise errors.NotFoundError(msg='渲染任务不存在')

        job.status = status
        job.error_message = error_message
        if output_path is not None:
            job.output_path = output_path
        await db.flush()

        latest = await render_book_job_dao.get_by_job_id(db, job_id, with_files=True)
        if latest is None:
            raise errors.NotFoundError(msg='渲染任务不存在')

        record = self._job_to_read(latest)
        self._sync_job_snapshot(record)
        return record

    async def mark_job_running(self, *, db: AsyncSession, job_id: str) -> RenderJobRead:
        return await self.update_job_status(db=db, job_id=job_id, status='running')

    async def soft_delete_job(self, *, db: AsyncSession, job_id: str) -> None:
        """
        软删除题本任务（用户视角：从「我的题本」列表中移除）

        :param db: 数据库会话
        :param job_id: 外部任务 ID
        :return:
        """
        count = await render_book_job_dao.soft_delete_by_job_id(db, job_id=job_id)
        if count == 0:
            raise errors.NotFoundError(msg='渲染任务不存在')

    async def mark_job_succeeded(
        self,
        *,
        db: AsyncSession,
        job_id: str,
        output_path: str | None = None,
    ) -> RenderJobRead:
        return await self.update_job_status(db=db, job_id=job_id, status='succeeded', output_path=output_path)

    async def mark_job_failed(
        self,
        *,
        db: AsyncSession,
        job_id: str,
        error_message: str,
    ) -> RenderJobRead:
        return await self.update_job_status(
            db=db,
            job_id=job_id,
            status='failed',
            error_message=error_message,
        )

    async def dispatch_job(
        self,
        *,
        job_id: str,
        upload_to_oss: bool = True,
    ) -> None:
        asyncio.create_task(self._execute_job_task(job_id=job_id, upload_to_oss=upload_to_oss))

    async def _execute_job_task(self, *, job_id: str, upload_to_oss: bool) -> None:
        try:
            async with async_db_session() as db:
                await self.execute_job(db=db, job_id=job_id, upload_to_oss=upload_to_oss)
                await db.commit()
        except Exception as exc:
            log.exception(f'[render_book] 后台执行任务失败 job_id={job_id}: {exc!s}')
            # 注意：这里如果不显式写回 failed，外部看到的任务状态会一直停留在 accepted。
            try:
                async with async_db_session() as db:
                    await self.mark_job_failed(db=db, job_id=job_id, error_message=str(exc))
                    await db.commit()
            except Exception as update_exc:
                log.exception(f'[render_book] 回写任务失败状态异常 job_id={job_id}: {update_exc!s}')

    async def get_job_file(
        self,
        *,
        db: AsyncSession,
        job_id: str,
        file_kind: RenderFileKind,
        render_variant: RenderVariant | None = None,
    ) -> RenderJobFileRead:
        job = await self.get_job(job_id, db=db)
        if job is None:
            raise errors.NotFoundError(msg='渲染任务不存在')

        matched = next(
            (
                item
                for item in job.files
                if item.status == 'available'
                and item.file_kind == file_kind
                and (render_variant is None or item.render_variant == render_variant)
            ),
            None,
        )
        if matched is None:
            raise errors.NotFoundError(msg='当前任务的目标文件尚未生成')
        return matched

    async def get_job_artifact_path(
        self,
        *,
        db: AsyncSession,
        job_id: str,
        render_variant: RenderVariant,
        artifact_kind: RenderArtifactKind,
    ) -> Path:
        job = await self.get_job(job_id, db=db)
        if job is None:
            raise errors.NotFoundError(msg='渲染任务不存在')

        artifact_path = self._artifact_local_path(
            job_id=job_id,
            render_variant=render_variant,
            artifact_kind=artifact_kind,
        )
        if not artifact_path.exists() or not artifact_path.is_file():
            raise errors.NotFoundError(msg=f'{artifact_kind} 产物不存在，请先执行渲染任务')
        return artifact_path

    async def register_output_file(
        self,
        *,
        db: AsyncSession,
        job_id: str,
        file_kind: RenderFileKind,
        local_path: str | Path,
        render_variant: RenderVariant | None = None,
        filename: str | None = None,
        content_type: str | None = None,
        upload_to_oss: bool = True,
    ) -> RenderJobFileRead:
        job = await render_book_job_dao.get_by_job_id(db, job_id)
        if job is None:
            raise errors.NotFoundError(msg='渲染任务不存在')

        output_file = Path(local_path)
        async_output_file = anyio.Path(output_file)
        if not await async_output_file.exists() or not await async_output_file.is_file():
            raise errors.RequestError(msg=f'输出文件不存在: {output_file}')

        resolved_filename = filename or output_file.name
        resolved_content_type = content_type or mimetypes.guess_type(output_file.name)[0] or 'application/pdf'
        size_bytes = (await async_output_file.stat()).st_size
        storage_type = 'local'
        status = 'available'
        object_key = None
        url = None
        error_message = None

        if upload_to_oss:
            storage_type = 'oss'
            try:
                url, object_key = await self._upload_local_file_to_oss(
                    db=db,
                    job_id=job_id,
                    output_file=output_file,
                    filename=resolved_filename,
                )
            except Exception as exc:
                status = 'failed'
                error_message = str(exc)
                job.status = 'failed'
                job.error_message = error_message

        file_data = {
            'render_job_id': job.id,
            'file_kind': file_kind,
            'render_variant': render_variant,
            'storage_type': storage_type,
            'status': status,
            'filename': resolved_filename,
            'content_type': resolved_content_type,
            'size_bytes': size_bytes,
            'local_path': str(output_file),
            'object_key': object_key,
            'url': url,
            'error_message': error_message,
        }

        existing = await render_book_job_file_dao.get_by_identity(
            db,
            render_job_id=job.id,
            file_kind=file_kind,
            render_variant=render_variant,
        )
        if existing is None:
            file_record = await render_book_job_file_dao.create_file(db, data=file_data)
        else:
            file_record = await render_book_job_file_dao.update_file(db, file_record=existing, data=file_data)

        if status == 'available':
            preferred_output_path = url or str(output_file)
            if self._should_replace_output_path(job.output_path, file_kind):
                job.output_path = preferred_output_path

        await db.flush()

        latest = await render_book_job_dao.get_by_job_id(db, job_id, with_files=True)
        if latest is None:
            raise errors.NotFoundError(msg='渲染任务不存在')
        self._sync_job_snapshot(self._job_to_read(latest))
        return self._file_to_read(file_record)

    async def execute_job(
        self,
        *,
        db: AsyncSession,
        job_id: str,
        upload_to_oss: bool = True,
    ) -> RenderJobRead:
        if str(getattr(settings, 'RENDER_BOOK_EXECUTOR_MODE', 'external')).strip().lower() != 'external':
            raise errors.ServerError(msg='当前仅支持 external 模式的渲染执行器。')

        job = await render_book_job_dao.get_by_job_id(db, job_id, with_files=True)
        if job is None:
            raise errors.NotFoundError(msg='渲染任务不存在')

        payload_context = self._load_payload_context(job)
        render_variants = list(job.render_variants or [])
        if not render_variants:
            raise errors.RequestError(msg='当前任务缺少 render_variants，无法执行渲染。')

        quota_user_id = self._coerce_positive_int(job.user_id) or self._coerce_positive_int(
            (job.metadata_json or {}).get('user_id')
        )
        quota_source_ref = f'render_job:{job.job_id}'
        quota_decision = None

        try:
            if quota_user_id is not None:
                quota_decision = await render_book_quota_service.consume_quota(
                    db=db,
                    user_id=quota_user_id,
                    source_ref=quota_source_ref,
                )

            await self.mark_job_running(db=db, job_id=job_id)

            for variant in render_variants:
                executor_result = await self._call_render_executor(
                    template_key=job.template_key,
                    job_id=job.job_id,
                    render_variant=variant,
                    context=payload_context,
                )
                downloaded_pdf = await self._download_executor_artifact(
                    job_id=job.job_id,
                    render_variant=variant,
                    artifact_kind='pdf',
                    artifact_path=executor_result.get('pdf_download_path'),
                )
                await self._download_executor_artifact(
                    job_id=job.job_id,
                    render_variant=variant,
                    artifact_kind='log',
                    artifact_path=executor_result.get('log_download_path'),
                    required=False,
                )

                file_record = await self.register_output_file(
                    db=db,
                    job_id=job.job_id,
                    file_kind=self._variant_to_file_kind(variant),
                    local_path=downloaded_pdf,
                    render_variant=variant,
                    filename=downloaded_pdf.name,
                    upload_to_oss=upload_to_oss,
                )
                if file_record.status != 'available':
                    raise errors.ServerError(msg=file_record.error_message or f'{variant} 产物登记失败')

                preview_paths = executor_result.get('preview_download_paths', [])
                if preview_paths and variant in ('questions_only', 'combined_inline', 'combined_appendix'):
                    preview_urls = []
                    preview_object_keys = []
                    preview_local_paths = []
                    for idx, artifact_path in enumerate(preview_paths):
                        try:
                            downloaded_preview = await self._download_executor_artifact(
                                job_id=job.job_id,
                                render_variant=variant,
                                artifact_kind=f'preview_{idx + 1}',
                                artifact_path=artifact_path,
                                required=False,
                            )
                            if downloaded_preview and downloaded_preview.exists():
                                preview_local_paths.append(str(downloaded_preview))
                                if upload_to_oss:
                                    url, object_key = await self._upload_local_file_to_oss(
                                        db=db,
                                        job_id=job.job_id,
                                        output_file=downloaded_preview,
                                        filename=downloaded_preview.name,
                                    )
                                    if object_key:
                                        preview_object_keys.append(object_key)
                                    preview_urls.append(url if url else str(downloaded_preview))
                                else:
                                    preview_urls.append(str(downloaded_preview))
                        except Exception as e:
                            log.warning(f'Failed to process preview image: {e}')

                    if preview_urls:
                        # Append preview URLs to job metadata
                        meta = dict(job.metadata_json or {})
                        meta['preview_urls'] = preview_urls
                        if preview_object_keys:
                            meta['preview_object_keys'] = preview_object_keys
                        if preview_local_paths:
                            meta['preview_local_paths'] = preview_local_paths
                        job.metadata_json = meta
                        await db.flush()

            latest = await self.get_job(job_id, db=db)
            if latest is None:
                raise errors.NotFoundError(msg='渲染任务不存在')
            await self.mark_job_succeeded(
                db=db,
                job_id=job_id,
                output_path=latest.output_path,
            )
            final_job = await self.get_job(job_id, db=db)
            if final_job is None:
                raise errors.NotFoundError(msg='渲染任务不存在')
            return final_job
        except Exception as exc:
            if quota_user_id is not None and quota_decision is not None:
                await render_book_quota_service.refund_quota(
                    db=db,
                    user_id=quota_user_id,
                    decision=quota_decision,
                    source_ref=quota_source_ref,
                )
            await self.mark_job_failed(db=db, job_id=job_id, error_message=str(exc))
            raise

    async def _persist_job(self, *, db: AsyncSession, record: RenderJobRead) -> RenderBookJob:
        return await render_book_job_dao.create_job(
            db,
            data={
                'job_id': record.job_id,
                'user_id': self._coerce_positive_int(record.metadata.get('user_id')),
                'template_key': record.template_key,
                'mode': record.mode,
                'status': record.status,
                'title': record.title,
                'subtitle': record.subtitle,
                'subject': record.subject,
                'book_kind': record.book_kind,
                'solution_mode': record.solution_mode,
                'filters': record.filters or None,
                'options': record.options.model_dump(mode='json'),
                'output_targets': record.output_targets.model_dump(mode='json'),
                'render_variants': record.render_variants or None,
                'metadata_json': record.metadata or None,
                'payload_path': record.payload_path,
                'question_count': record.question_count,
                'material_count': record.material_count,
                'output_path': record.output_path,
                'error_message': record.error_message,
            },
        )

    async def _upload_local_file_to_oss(
        self,
        *,
        db: AsyncSession,
        job_id: str,
        output_file: Path,
        filename: str,
    ) -> tuple[str, str]:
        try:
            from backend.plugin.oss.service.storage_service import storage_service
        except Exception as exc:
            raise errors.ServerError(msg=f'OSS 插件不可用: {exc!s}') from exc

        upload_path = self._build_oss_path(job_id)
        with output_file.open('rb') as file_obj:
            upload_file = UploadFile(file=file_obj, filename=filename)
            return await storage_service.upload_with_filename(
                db=db,
                file=upload_file,
                filename=filename,
                path=upload_path,
            )

    async def _call_render_executor(
        self,
        *,
        template_key: str,
        job_id: str,
        render_variant: str,
        context: dict,
    ) -> dict:
        executor_url = self._executor_base_url()
        timeout_seconds = self._executor_timeout_seconds()
        request_payload = {
            'template_key': template_key,
            'job_id': job_id,
            'render_variant': render_variant,
            'compile_pdf': True,
            'keep_workdir': True,
            'context': context,
        }
        async with httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=True) as client:
            response = await client.post(f'{executor_url}/api/v1/render', json=request_payload)
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                # 把执行器返回的 detail 带出来，方便排查模板/环境问题。
                detail = response.text
                if detail:
                    raise ValueError(f'渲染执行器返回错误: {detail}') from exc
                raise
            return response.json()

    async def _download_executor_artifact(
        self,
        *,
        job_id: str,
        render_variant: str,
        artifact_kind: str,
        artifact_path: str | None,
        required: bool = True,
    ) -> Path | None:
        if not artifact_path:
            if required:
                raise errors.ServerError(msg=f'执行器未返回 {artifact_kind} 下载地址。')
            return None

        executor_url = self._executor_base_url()
        artifact_url = f'{executor_url}{artifact_path}'
        timeout_seconds = self._executor_timeout_seconds()
        async with httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=True) as client:
            response = await client.get(artifact_url)
            if response.status_code == 404 and not required:
                return None
            response.raise_for_status()
            content = response.content

        artifact_file = self._artifact_local_path(
            job_id=job_id, render_variant=render_variant, artifact_kind=artifact_kind
        )
        artifact_file.parent.mkdir(parents=True, exist_ok=True)
        artifact_file.write_bytes(content)
        return artifact_file

    def _load_payload_context(self, job: RenderBookJob) -> dict:
        if job.payload_path:
            payload_file = Path(job.payload_path)
            if payload_file.exists():
                return json.loads(payload_file.read_text(encoding='utf-8'))

        request_path = self.jobs_root / job.job_id / 'request.json'
        if not request_path.exists():
            raise errors.RequestError(msg='任务缺少 payload.json 或 request.json，无法执行渲染。')

        request_payload = json.loads(request_path.read_text(encoding='utf-8'))
        render_job = RenderJobCreate.model_validate(request_payload)
        raise errors.RequestError(
            msg=f'任务 {job.job_id} 缺少 payload.json，请重新创建任务后再执行。模板：{render_job.template_key}'
        )

    def _artifact_local_path(self, *, job_id: str, render_variant: str, artifact_kind: str) -> Path:
        job_dir = self.jobs_root / job_id / 'artifacts'
        if artifact_kind == 'pdf':
            return job_dir / f'{render_variant}.pdf'
        if artifact_kind == 'log':
            return job_dir / f'{render_variant}.log'
        if artifact_kind.startswith('preview_'):
            return job_dir / f'{render_variant}_{artifact_kind}.jpg'
        return job_dir / f'{render_variant}_{artifact_kind}'

    def _resolve_executor_artifact_url(self, artifact_path: str | None) -> str | None:
        if not artifact_path:
            return None
        if artifact_path.startswith('http://') or artifact_path.startswith('https://'):
            return artifact_path
        return f'{self._executor_base_url()}{artifact_path}'

    @staticmethod
    def _variant_to_file_kind(render_variant: str) -> RenderFileKind:
        mapping: dict[str, RenderFileKind] = {
            'questions_only': 'question_pdf',
            'solutions_only': 'solution_pdf',
            'combined_inline': 'combined_pdf',
            'combined_appendix': 'combined_pdf',
        }
        try:
            return mapping[render_variant]
        except KeyError as exc:
            raise errors.RequestError(msg=f'不支持的渲染变体: {render_variant}') from exc

    @staticmethod
    def _executor_timeout_seconds() -> float:
        value = getattr(settings, 'RENDER_BOOK_EXECUTOR_TIMEOUT_SECONDS', 600)
        try:
            timeout = float(value)
        except Exception:
            timeout = 600.0
        return timeout if timeout > 0 else 600.0

    @staticmethod
    def _executor_base_url() -> str:
        executor_url = str(getattr(settings, 'RENDER_BOOK_EXECUTOR_URL', '') or '').strip().rstrip('/')
        if not executor_url:
            raise errors.ServerError(msg='未配置 RENDER_BOOK_EXECUTOR_URL。')
        return executor_url

    def _job_to_read(self, job: RenderBookJob) -> RenderJobRead:
        file_records = [self._file_to_read(item) for item in (job.files or [])]
        output_targets = RenderOutputTargets.model_validate(job.output_targets or {})
        content_mode, answer_layout, delivery_mode = render_payload_service.resolve_export_config_from_legacy(
            solution_mode=job.solution_mode,
            output_targets=output_targets,
        )
        metadata = dict(job.metadata_json or {})
        if metadata.get('user_id') is None and job.user_id is not None:
            metadata['user_id'] = job.user_id

        return RenderJobRead(
            job_id=job.job_id,
            status=job.status,
            mode=job.mode,
            template_key=job.template_key,
            title=job.title,
            subtitle=job.subtitle,
            subject=job.subject,
            book_kind=job.book_kind,
            content_mode=content_mode,
            answer_layout=answer_layout,
            delivery_mode=delivery_mode,
            solution_mode=job.solution_mode,
            filters=job.filters or {},
            options=RenderOptions.model_validate(job.options or {}),
            output_targets=output_targets,
            render_variants=list(job.render_variants or []),
            metadata=metadata,
            payload_path=job.payload_path,
            question_count=job.question_count,
            material_count=job.material_count,
            output_path=job.output_path or self._pick_output_path(file_records),
            error_message=job.error_message,
            files=file_records,
            created_at=job.created_time,
            updated_at=job.updated_time or job.created_time,
        )

    @staticmethod
    def _file_to_read(file_record: RenderBookJobFile) -> RenderJobFileRead:
        return RenderJobFileRead(
            file_kind=file_record.file_kind,
            render_variant=file_record.render_variant,
            storage_type=file_record.storage_type,
            status=file_record.status,
            filename=file_record.filename,
            content_type=file_record.content_type,
            size_bytes=file_record.size_bytes,
            local_path=file_record.local_path,
            object_key=file_record.object_key,
            url=file_record.url,
            error_message=file_record.error_message,
            created_at=file_record.created_time,
            updated_at=file_record.updated_time or file_record.created_time,
        )

    def _sync_job_snapshot(self, record: RenderJobRead) -> None:
        job_dir = self.jobs_root / record.job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        self._write_json(job_dir / 'job.json', record.model_dump(mode='json'))

    @staticmethod
    def _pick_output_path(files: list[RenderJobFileRead]) -> str | None:
        if not files:
            return None

        preferred_order = {
            'combined_pdf': 3,
            'question_pdf': 2,
            'solution_pdf': 1,
        }
        sorted_files = sorted(
            files,
            key=lambda item: preferred_order.get(item.file_kind, 0),
            reverse=True,
        )
        for item in sorted_files:
            if item.url:
                return item.url
            if item.local_path:
                return item.local_path
        return None

    @staticmethod
    def _should_replace_output_path(current_output_path: str | None, file_kind: RenderFileKind) -> bool:
        if current_output_path is None:
            return True
        return file_kind in {'combined_pdf', 'question_pdf'}

    @staticmethod
    def _build_oss_path(job_id: str) -> str:
        prefix = str(getattr(settings, 'RENDER_BOOK_OSS_PATH_PREFIX', 'render-book') or 'render-book')
        normalized = prefix.replace('\\', '/').strip('/')
        if not normalized:
            return job_id
        return f'{normalized}/{job_id}'

    @staticmethod
    def _coerce_positive_int(value: object) -> int | None:
        if isinstance(value, int) and value > 0:
            return value
        if isinstance(value, str) and value.strip().isdigit():
            parsed = int(value.strip())
            if parsed > 0:
                return parsed
        return None

    @staticmethod
    def _merge_preview_metadata(
        *,
        base_metadata: dict,
        request_metadata: dict,
        layout_params: dict,
    ) -> dict:
        resolved_metadata = {**(base_metadata or {}), **(request_metadata or {})}
        for key, value in (layout_params or {}).items():
            if value is None:
                continue
            if isinstance(value, str) and not value.strip():
                continue
            resolved_metadata[key] = value
        return resolved_metadata

    @staticmethod
    def _validate_positive_integer(filters: dict, key: str, issues: list[RenderValidationIssue]) -> None:
        value = filters.get(key)
        if value is None:
            return
        if not isinstance(value, int) or value <= 0:
            issues.append(RenderValidationIssue(field=f'filters.{key}', level='error', message=f'{key} 必须是正整数。'))

    @staticmethod
    def _validate_list_of_type(
        filters: dict, key: str, expected_type: type, issues: list[RenderValidationIssue]
    ) -> None:
        value = filters.get(key)
        if value is None:
            return
        if not isinstance(value, list) or any(not isinstance(item, expected_type) or not item for item in value):
            issues.append(
                RenderValidationIssue(
                    field=f'filters.{key}',
                    level='error',
                    message=f'{key} 必须是非空 {expected_type.__name__} 列表。',
                )
            )

    @staticmethod
    def _validate_question_ids(value: object, issues: list[RenderValidationIssue]) -> None:
        if value is None:
            return
        if isinstance(value, str):
            if not any(item.strip().isdigit() for item in value.split(',')):
                issues.append(
                    RenderValidationIssue(
                        field='filters.question_ids',
                        level='error',
                        message='question_ids 需要是逗号分隔的正整数列表。',
                    )
                )
            return
        if isinstance(value, list):
            normalized = []
            for item in value:
                if isinstance(item, int) and item > 0:
                    normalized.append(item)
                elif isinstance(item, str) and item.strip().isdigit() and int(item.strip()) > 0:
                    normalized.append(int(item.strip()))
            if not normalized:
                issues.append(
                    RenderValidationIssue(
                        field='filters.question_ids',
                        level='error',
                        message='question_ids 列表中至少要包含一个正整数。',
                    )
                )
            return
        issues.append(
            RenderValidationIssue(
                field='filters.question_ids',
                level='error',
                message='question_ids 必须是逗号分隔字符串或正整数列表。',
            )
        )

    @staticmethod
    def _write_json(path: Path, payload: dict) -> None:
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding='utf-8')


render_service = RenderService()
