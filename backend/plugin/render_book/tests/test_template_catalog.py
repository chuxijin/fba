#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio

from backend.plugin.render_book.schema.render import RenderJobCreate
from backend.plugin.render_book.service.render_service import render_service
from backend.plugin.render_book.utils import get_template_catalog, resolve_template_manifest


def test_template_catalog_loads_versioned_templates() -> None:
    """模板目录应加载全部已发布版本并生成摘要"""
    catalog = get_template_catalog()

    assert set(catalog) == {'basic_calculation', 'exam_paper', 'hanyu', 'practice', 'wrong_question'}
    assert all('1.0.0' in versions for versions in catalog.values())
    assert all(len(versions['1.0.0'].digest) == 64 for versions in catalog.values())


def test_resolve_template_manifest_defaults_to_latest_enabled_version() -> None:
    """未指定版本时应选择最新启用版本"""
    catalog = get_template_catalog()

    manifest = resolve_template_manifest(catalog, 'practice')

    assert manifest is not None
    assert manifest.version == '1.0.1'


def test_validate_job_rejects_unknown_template_version() -> None:
    """不存在的模板版本应在任务创建前被拒绝"""
    payload = RenderJobCreate(
        template_key='practice',
        template_version='9.9.9',
        title='版本校验',
        filters={'question_ids': '1'},
    )

    result = asyncio.run(render_service.validate_job(payload))

    assert result.valid is False
    assert any(issue.field == 'template_version' and issue.level == 'error' for issue in result.issues)


def test_validate_job_returns_resolved_template_identity() -> None:
    """有效任务应返回固定模板版本和内容摘要"""
    payload = RenderJobCreate(
        template_key='practice',
        title='版本校验',
        filters={'question_ids': '1'},
    )

    result = asyncio.run(render_service.validate_job(payload))

    assert result.valid is True
    assert result.template is not None
    assert result.template.version == '1.0.1'
    assert len(result.template.digest) == 64
