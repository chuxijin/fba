#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ruff: noqa: ANN001, ANN202, RUF029
from backend.app.sensitive_word.service import sensitive_word_service as module
from backend.app.sensitive_word.service.sensitive_word_service import sensitive_word_service
from backend.common.exception import errors

RULES = [
    {'id': 1, 'word': '政府', 'keywords': ['政府', 'zf', 'zhèngfǔ'], 'replacement': 'ZF', 'action': 'replace'},
    {'id': 2, 'word': '习近平', 'keywords': ['习近平', 'xi jin ping'], 'replacement': None, 'action': 'block'},
    {'id': 3, 'word': '法轮功', 'keywords': ['法轮功', 'falungong'], 'replacement': None, 'action': 'reject'},
]


async def _fake_rules(db):
    return RULES


async def test_sanitize_replaces_word_and_variants(monkeypatch) -> None:
    monkeypatch.setattr(module.SensitiveWordService, 'get_active_rules', _fake_rules)
    result = await sensitive_word_service.sanitize(None, '我是zf的人，政府很好')
    assert result.clean_text == '我是ZF的人，ZF很好'
    assert sorted(result.matched) == ['zf', '政府']


async def test_sanitize_reports_hit_detail(monkeypatch) -> None:
    monkeypatch.setattr(module.SensitiveWordService, 'get_active_rules', _fake_rules)
    result = await sensitive_word_service.sanitize(None, '政府zf政府')
    assert result.clean_text == 'ZFZFZF'
    by_keyword = {hit.keyword: hit for hit in result.hits}
    assert by_keyword['政府'].word_id == 1
    assert by_keyword['政府'].hit_count == 2
    assert by_keyword['zf'].hit_count == 1
    assert by_keyword['政府'].replacement == 'ZF'


async def test_sanitize_blocks_via_variant(monkeypatch) -> None:
    monkeypatch.setattr(module.SensitiveWordService, 'get_active_rules', _fake_rules)
    result = await sensitive_word_service.sanitize(None, '我爱xi jin ping')
    assert result.clean_text == '我爱**'
    assert result.hits[0].keyword == 'xi jin ping'
    assert result.hits[0].action == 'block'


async def test_sanitize_rejects_via_variant(monkeypatch) -> None:
    monkeypatch.setattr(module.SensitiveWordService, 'get_active_rules', _fake_rules)
    try:
        await sensitive_word_service.sanitize(None, 'falungong 内容')
        raise AssertionError('should raise')
    except errors.RequestError as exc:
        assert 'falungong' in exc.msg


async def test_sanitize_no_match_returns_unchanged(monkeypatch) -> None:
    monkeypatch.setattr(module.SensitiveWordService, 'get_active_rules', _fake_rules)
    result = await sensitive_word_service.sanitize(None, '无敏感内容')
    assert result.clean_text == '无敏感内容'
    assert result.matched == []
    assert result.hits == []


async def test_sanitize_collect_accumulates_hits(monkeypatch) -> None:
    monkeypatch.setattr(module.SensitiveWordService, 'get_active_rules', _fake_rules)
    payload = {
        'template': '政府好',
        'blanks': [
            {'id': 'b1', 'answers': ['zf', '好'], 'hint': '政府'},
        ],
        'nested': {'key': 'xi jin ping'},
    }
    cleaned, hits = await sensitive_word_service.sanitize_collect(None, payload)
    assert cleaned['template'] == 'ZF好'
    assert cleaned['blanks'][0]['answers'] == ['ZF', '好']
    assert cleaned['nested'] == {'key': '**'}
    keywords = sorted(hit.keyword for hit in hits)
    assert keywords == ['xi jin ping', 'zf', '政府', '政府']


async def test_log_hits_writes_bulk(monkeypatch) -> None:
    monkeypatch.setattr(module.SensitiveWordService, 'get_active_rules', _fake_rules)
    written: list[list[dict]] = []

    async def fake_create_bulk(db, items):
        written.append(items)

    monkeypatch.setattr(module.sensitive_hit_log_dao, 'create_bulk', fake_create_bulk)

    result = await sensitive_word_service.sanitize(None, '政府')
    await sensitive_word_service.log_hits(
        db=None,
        user_id=7,
        hits=result.hits,
        target_type='memory_card',
        target_id=42,
        snippet='ZF',
    )
    assert len(written) == 1
    assert written[0][0]['user_id'] == 7
    assert written[0][0]['word'] == '政府'
    assert written[0][0]['target_type'] == 'memory_card'
    assert written[0][0]['target_id'] == 42
