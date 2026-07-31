#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio

from types import SimpleNamespace

from backend.plugin.render_book.api.v1.render import (
    _bind_payload_user,
    _coerce_positive_int_list,
    _ensure_render_payload_access,
)
from backend.plugin.render_book.schema.render import RenderJobCreate
from backend.plugin.render_book.service.render_service import render_service


def test_coerce_positive_int_list_supports_csv_string() -> None:
    """question_ids 传逗号字符串时也应解析为正整数列表"""
    result = _coerce_positive_int_list('1, 2,foo, 2,0,-3')

    assert result == [1, 2]


def test_bind_payload_user_normalizes_superuser_bound_user() -> None:
    """超级管理员可绑定其他用户，且 metadata.user_id 应落为整数"""
    request = SimpleNamespace(user=SimpleNamespace(id=1, is_superuser=True))
    payload = RenderJobCreate(template_key='practice', title='测试题本', metadata={'user_id': '23'})

    bound_user_id = _bind_payload_user(request, payload)

    assert bound_user_id == 23
    assert payload.metadata['user_id'] == 23


def test_bind_payload_user_forces_current_user_for_normal_user() -> None:
    """普通用户应始终绑定自己，不能伪造其他 user_id"""
    request = SimpleNamespace(user=SimpleNamespace(id=9, is_superuser=False))
    payload = RenderJobCreate(template_key='practice', title='测试题本', metadata={'user_id': 77})

    bound_user_id = _bind_payload_user(request, payload)

    assert bound_user_id == 9
    assert payload.metadata['user_id'] == 9


def test_job_to_read_fills_legacy_metadata_user_id() -> None:
    """历史任务缺少 metadata.user_id 时，应回填库里的 user_id"""
    job = SimpleNamespace(
        job_id='job_001',
        status='accepted',
        mode='final',
        template_key='practice',
        title='测试题本',
        subtitle=None,
        subject=None,
        book_kind='custom',
        solution_mode='none',
        filters={},
        options={},
        output_targets={},
        render_variants=['questions_only'],
        metadata_json={},
        user_id=11,
        payload_path=None,
        question_count=10,
        material_count=0,
        output_path=None,
        error_message=None,
        created_time='2026-07-07T00:00:00',
        updated_time='2026-07-07T00:00:00',
        files=[],
    )

    result = render_service._job_to_read(job)

    assert result.metadata['user_id'] == 11
    assert result.template_version == '1.0.0'
    assert len(result.template_digest) == 64


def test_ensure_render_payload_access_skips_membership_checks(monkeypatch) -> None:
    """题本总配额准入时，不再额外触发题库会员校验"""

    async def fail_verify(*_args, **_kwargs):
        raise AssertionError('membership verify should not be called')

    monkeypatch.setattr(
        'backend.plugin.render_book.api.v1.render.membership_service.verify_question_ids_access',
        fail_verify,
    )
    monkeypatch.setattr(
        'backend.plugin.render_book.api.v1.render.membership_service.verify_bank_list_access',
        fail_verify,
    )
    monkeypatch.setattr(
        'backend.plugin.render_book.api.v1.render.membership_service.verify_filter_access',
        fail_verify,
    )
    monkeypatch.setattr(
        'backend.plugin.render_book.api.v1.render.membership_service.verify_knowledge_access',
        fail_verify,
    )

    request = SimpleNamespace(user=SimpleNamespace(id=9, is_superuser=False))
    payload = RenderJobCreate(
        template_key='practice',
        title='测试题本',
        filters={'bank_id': 123, 'question_ids': '1,2,3', 'cat_id': 5},
        metadata={},
    )

    result = asyncio.run(_ensure_render_payload_access(request=request, db=None, payload=payload))

    assert result == 9
    assert payload.metadata['user_id'] == 9


def test_ensure_render_payload_access_only_normalizes_chapter_context(monkeypatch) -> None:
    """篇章上下文归一化可以保留，但不应附带 user_id 权限判断"""
    captured: dict[str, object] = {}

    async def fake_resolve_bank_context_for_chapter(*_args, **kwargs):
        captured.update(kwargs)
        return 88

    monkeypatch.setattr(
        'backend.plugin.render_book.api.v1.render.membership_service.resolve_bank_context_for_chapter',
        fake_resolve_bank_context_for_chapter,
    )

    request = SimpleNamespace(user=SimpleNamespace(id=9, is_superuser=False))
    payload = RenderJobCreate(
        template_key='practice',
        title='测试题本',
        filters={'bank_id': 12, 'chapter_id': 34},
        metadata={},
    )

    result = asyncio.run(_ensure_render_payload_access(request=request, db=None, payload=payload))

    assert result == 9
    assert payload.filters['bank_id'] == 88
    assert captured == {'db': None, 'chapter_id': 34, 'bank_id': 12}


def test_ensure_v2_render_payload_checks_bank_access(monkeypatch) -> None:
    """V2 题库导出必须复用题库稳定身份的准入判断。"""
    captured: dict[str, object] = {}

    async def fake_ensure_bank_access(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(
        'backend.plugin.render_book.api.v1.render.bank_access_service.ensure_bank_access',
        fake_ensure_bank_access,
    )
    request = SimpleNamespace(user=SimpleNamespace(id=9, is_superuser=False))
    payload = RenderJobCreate(
        template_key='practice',
        title='V2 题本',
        filters={'bank_id': 123, 'question_ids': [1, 2]},
        metadata={'qbank_version': 'v2', 'source_type': 'placement'},
    )

    result = asyncio.run(_ensure_render_payload_access(request=request, db=None, payload=payload))

    assert result == 9
    assert captured == {'db': None, 'user_id': 9, 'bank_id': 123}
