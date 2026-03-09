#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from backend.core.conf import settings
from backend.plugin.render_book.schema.render import (
    RenderJobCreate,
    RenderJobRead,
    RenderJobValidationResult,
    RenderTemplateDetail,
    RenderTemplateSummary,
    RenderValidationIssue,
)
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
            issues.append(RenderValidationIssue(field='template_key', level='error', message='模板不存在，请选择有效模板。'))
        if not normalized_title:
            issues.append(RenderValidationIssue(field='title', level='error', message='题本标题不能为空。'))

        self._validate_positive_integer(payload.filters, 'question_count', issues)
        self._validate_positive_integer(payload.filters, 'wrong_only_recent_days', issues)
        self._validate_list_of_type(payload.filters, 'question_types', str, issues)
        self._validate_list_of_type(payload.filters, 'material_types', str, issues)
        self._validate_list_of_type(payload.filters, 'regions', str, issues)
        self._validate_list_of_type(payload.filters, 'paper_types', str, issues)
        self._validate_list_of_type(payload.filters, 'subject_modules', str, issues)
        self._validate_years(payload.filters.get('years'), issues)

        if payload.mode == 'preview' and isinstance(payload.filters.get('question_count'), int) and payload.filters['question_count'] > 50:
            issues.append(RenderValidationIssue(field='filters.question_count', level='warning', message='预览模式建议题量不超过 50，以提升预览速度。'))

        if payload.options.include_analysis and not payload.options.include_answer:
            issues.append(RenderValidationIssue(field='options.include_analysis', level='warning', message='开启解析通常也建议同时展示答案。'))

        if payload.template_key == 'exam_paper' and not payload.filters.get('years'):
            issues.append(RenderValidationIssue(field='filters.years', level='warning', message='真题套卷通常建议至少指定年份。'))

        if payload.template_key == 'wrong_question' and not payload.metadata.get('user_id'):
            issues.append(RenderValidationIssue(field='metadata.user_id', level='error', message='错题重刷模板需要传入 metadata.user_id。'))

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

    async def create_job(self, payload: RenderJobCreate) -> RenderJobRead:
        validation = await self.validate_job(payload)
        errors = [issue.message for issue in validation.issues if issue.level == 'error']
        if errors:
            raise ValueError('；'.join(errors))

        template = await self.get_template(payload.template_key)
        now = datetime.now(timezone.utc)
        job_id = uuid4().hex
        job_dir = self.jobs_root / job_id
        job_dir.mkdir(parents=True, exist_ok=True)

        record = RenderJobRead(
            job_id=job_id,
            status='accepted',
            mode=payload.mode,
            template_key=payload.template_key,
            title=validation.normalized_title,
            subtitle=payload.subtitle,
            subject=payload.subject or (template.subject if template else None),
            filters=payload.filters,
            options=payload.options,
            metadata={
                **payload.metadata,
                'executor_mode': settings.RENDER_BOOK_EXECUTOR_MODE,
                'executor_url': settings.RENDER_BOOK_EXECUTOR_URL,
            },
            output_path=None,
            error_message=None,
            created_at=now,
            updated_at=now,
        )
        self._write_json(job_dir / 'job.json', record.model_dump(mode='json'))
        self._write_json(job_dir / 'request.json', payload.model_dump(mode='json'))
        return record

    async def get_job(self, job_id: str) -> RenderJobRead | None:
        job_file = self.jobs_root / job_id / 'job.json'
        if not job_file.exists():
            return None
        return RenderJobRead.model_validate_json(job_file.read_text(encoding='utf-8'))

    @staticmethod
    def _validate_positive_integer(filters: dict, key: str, issues: list[RenderValidationIssue]) -> None:
        value = filters.get(key)
        if value is None:
            return
        if not isinstance(value, int) or value <= 0:
            issues.append(RenderValidationIssue(field=f'filters.{key}', level='error', message=f'{key} 必须是正整数。'))

    @staticmethod
    def _validate_list_of_type(filters: dict, key: str, expected_type: type, issues: list[RenderValidationIssue]) -> None:
        value = filters.get(key)
        if value is None:
            return
        if not isinstance(value, list) or any(not isinstance(item, expected_type) or not item for item in value):
            issues.append(RenderValidationIssue(field=f'filters.{key}', level='error', message=f'{key} 必须是非空 {expected_type.__name__} 列表。'))

    @staticmethod
    def _validate_years(value: object, issues: list[RenderValidationIssue]) -> None:
        if value is None:
            return
        if not isinstance(value, list) or any(not isinstance(item, int) or item < 2000 or item > 2100 for item in value):
            issues.append(RenderValidationIssue(field='filters.years', level='error', message='years 必须是 2000-2100 之间的整数列表。'))

    @staticmethod
    def _write_json(path: Path, payload: dict) -> None:
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding='utf-8')


render_service = RenderService()
