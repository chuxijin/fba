import asyncio

from types import SimpleNamespace
from typing import Any

import pytest

from backend.app.question_bank_v2.crud.crud_external_practice import CRUDExternalPractice, external_practice_dao
from backend.app.question_bank_v2.crud.crud_question import question_dao
from backend.app.question_bank_v2.schema.external_practice import ImportPracticeQuestionParam
from backend.app.question_bank_v2.utils.external_practice import import_digest


def _item() -> ImportPracticeQuestionParam:
    return ImportPracticeQuestionParam(
        source_question_key='fb-1001',
        position=1,
        module_path=['常识判断'],
        stem='Which option is correct?',
        options=[
            {'option_code': 'A', 'content': 'Answer A'},
            {'option_code': 'B', 'content': 'Answer B'},
        ],
        answer={'answer_data': {'correct': 'A'}},
        status='correct',
        response_data='A',
    )


def test_ensure_question_reuses_private_question_with_same_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """同用户下内容一致的私有题直接复用，不再按来源键重复建题"""
    captured: dict[str, Any] = {}
    existing = SimpleNamespace(id=9, owner_id=7, visibility='private')

    async def find_reusable(_db: object, *, user_id: int, content_hash: str) -> SimpleNamespace:
        await asyncio.sleep(0)
        captured.update(user_id=user_id, content_hash=content_hash)
        return existing

    async def fail_code(*_args: object, **_kwargs: object) -> None:
        await asyncio.sleep(0)
        raise AssertionError('复用命中后不应再按 code 查询')

    async def get_question(_db: object, question_id: int, **_kwargs: object) -> SimpleNamespace:
        await asyncio.sleep(0)
        assert question_id == 9
        return existing

    monkeypatch.setattr(external_practice_dao, 'find_reusable_question', find_reusable)
    monkeypatch.setattr(question_dao, 'get_by_code', fail_code)
    monkeypatch.setattr(question_dao, 'get', get_question)

    item = _item()
    question = asyncio.run(CRUDExternalPractice.ensure_question(object(), user_id=7, platform='fenbi', item=item))

    assert question is existing
    assert captured['user_id'] == 7
    assert captured['content_hash'] == import_digest(
        item.model_dump(mode='json', include={'stem', 'content_format', 'question_type', 'options'})
    )


def test_question_content_digest_normalizes_html_tags_and_whitespace() -> None:
    """验证题干与选项带有 <b>/<strong>/<u>/&nbsp; 与不带时计算出的内容指纹完全一致"""
    from backend.app.question_bank_v2.utils.external_practice import question_content_digest

    raw_stem = '<p>2026年1月，全会举行。下列说法不正确的是（\xa0 \xa0 ）。</p>'
    bold_stem = '<p>2026年1月，全会举行。下列说法<b>不正确</b>的是（&nbsp; &nbsp; ）。</p>'
    options = [
        {'option_code': 'A', 'content': '选项内容 A'},
        {'option_code': 'B', 'content': '选项内容 <strong>B</strong>'},
    ]
    options_clean = [
        {'option_code': 'A', 'content': '选项内容 A'},
        {'option_code': 'B', 'content': '选项内容 B'},
    ]

    hash1 = question_content_digest(
        stem=raw_stem,
        content_format='html',
        question_type='single_choice',
        options=options_clean,
    )
    hash2 = question_content_digest(
        stem=bold_stem,
        content_format='html',
        question_type='single_choice',
        options=options,
    )
    assert hash1 == hash2


def test_question_content_digest_normalizes_underlines_and_images() -> None:
    """验证填空题 <u> 占位符与 ______、图片 style/域名差异时计算出的内容指纹完全一致"""
    from backend.app.question_bank_v2.utils.external_practice import question_content_digest

    raw_stem = '<p>发展生态。<u>\xa0 \xa0 \xa0 \xa0\xa0</u>。有<img flag="tex" src="//fb.fenbike.cn/formulas?latex=123"></p>'
    norm_stem = '<p>发展生态。______。有<img flag="tex" src="//fb.fbstatic.cn/formulas?latex=123" data-image-layout="inline" style="max-width:100%;height:auto;display:inline-block;"></p>'
    options = [{'option_code': 'A', 'content': '选项 A'}]

    hash1 = question_content_digest(
        stem=raw_stem,
        content_format='html',
        question_type='single_choice',
        options=options,
    )
    hash2 = question_content_digest(
        stem=norm_stem,
        content_format='html',
        question_type='single_choice',
        options=options,
    )
    assert hash1 == hash2


