from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from backend.plugin.agent.schema.coach import CoachMessageParam, GenerateTrainingPlanParam
from backend.plugin.agent.service.coach_service import ShenlunCoachService


def test_coach_json_parser_accepts_markdown_wrapped_object() -> None:
    payload = ShenlunCoachService._parse_json('```json\n{"content":"继续练习"}\n```')
    assert payload == {'content': '继续练习'}


def test_fallback_plan_rows_are_bounded_and_alternate_review() -> None:
    rows = ShenlunCoachService._fallback_plan_rows(plan_id=3, user_id=9, days=4)
    assert len(rows) == 4
    assert [row['task_type'] for row in rows] == ['practice', 'practice', 'review', 'practice']
    assert all(row['plan_id'] == 3 and row['user_id'] == 9 for row in rows)


def test_training_plan_request_id_is_validated() -> None:
    params = GenerateTrainingPlanParam(request_id='request-123')
    assert params.request_id == 'request-123'
    with pytest.raises(ValueError):
        GenerateTrainingPlanParam(request_id='short')


def test_coach_message_accepts_yanshen_entrypoint_and_module() -> None:
    params = CoachMessageParam(
        content='推荐下一题',
        request_id='request-456',
        entrypoint='next_question',
        module='summary',
    )

    assert params.entrypoint == 'next_question'
    assert params.module == 'summary'


@pytest.mark.asyncio
async def test_start_message_run_reuses_existing_idempotent_run(monkeypatch: pytest.MonkeyPatch) -> None:
    service = ShenlunCoachService()
    session = SimpleNamespace(id=6, status='active')
    existing = SimpleNamespace(id=15, status='running')
    import backend.plugin.agent.service.coach_service as module

    monkeypatch.setattr(module.shenlun_coach_session_dao, 'get_owned_for_update', AsyncMock(return_value=session))
    monkeypatch.setattr(module.agent_run_dao, 'get_by_idempotency', AsyncMock(return_value=existing))

    result = await service.start_message_run(
        db=object(),
        session_id=6,
        user_id=9,
        params=CoachMessageParam(content='继续复盘', request_id='request-789'),
    )

    assert result.run_id == 15
    assert result.status == 'running'
    assert result.stream_url.endswith('/coach/runs/15/stream')


@pytest.mark.asyncio
async def test_get_run_rejects_non_coach_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    service = ShenlunCoachService()
    import backend.plugin.agent.service.coach_service as module

    monkeypatch.setattr(
        module.agent_run_dao,
        'get_owned',
        AsyncMock(return_value=SimpleNamespace(agent_key='shenlun.grading')),
    )

    with pytest.raises(Exception, match='教练运行不存在'):
        await service.get_run(db=object(), run_id=3, user_id=9)


@pytest.mark.asyncio
async def test_complete_item_marks_plan_completed_when_all_items_done(monkeypatch: pytest.MonkeyPatch) -> None:
    service = ShenlunCoachService()
    plan = SimpleNamespace(id=8, status='active')
    item = SimpleNamespace(id=12, plan_id=8, status='pending', completed_time=None)
    import backend.plugin.agent.service.coach_service as module

    monkeypatch.setattr(module.shenlun_training_plan_item_dao, 'get_owned', AsyncMock(return_value=item))
    monkeypatch.setattr(module.shenlun_training_plan_dao, 'get_owned', AsyncMock(return_value=plan))
    monkeypatch.setattr(module.shenlun_training_plan_item_dao, 'complete', AsyncMock(
        side_effect=lambda db, item, completed_time: setattr(item, 'status', 'completed')
    ))
    monkeypatch.setattr(
        module.shenlun_training_plan_item_dao,
        'list_plan',
        AsyncMock(return_value=[SimpleNamespace(status='completed')]),
    )
    monkeypatch.setattr(service, 'get_plan', AsyncMock(return_value='done'))
    db = SimpleNamespace(commit=AsyncMock())

    result = await service.complete_plan_item(db=db, item_id=12, user_id=9)

    assert result == 'done'
    assert plan.status == 'completed'
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_archive_session_marks_owned_session_archived(monkeypatch: pytest.MonkeyPatch) -> None:
    service = ShenlunCoachService()
    session = SimpleNamespace(id=6, status='active')
    import backend.plugin.agent.service.coach_service as module

    monkeypatch.setattr(module.shenlun_coach_session_dao, 'get_owned_for_update', AsyncMock(return_value=session))
    monkeypatch.setattr(service, 'get_session', AsyncMock(return_value='archived'))
    db = SimpleNamespace(commit=AsyncMock())

    result = await service.archive_session(db=db, session_id=6, user_id=9)

    assert result == 'archived'
    assert session.status == 'archived'
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_sessions_returns_user_session_summaries(monkeypatch: pytest.MonkeyPatch) -> None:
    service = ShenlunCoachService()
    session = SimpleNamespace(
        id=6,
        title='最近复盘',
        status='active',
        last_summary='优先补充材料依据',
        created_time=datetime(2026, 8, 21, tzinfo=UTC),
        updated_time=datetime(2026, 8, 21, 12, tzinfo=UTC),
    )
    import backend.plugin.agent.service.coach_service as module

    monkeypatch.setattr(module.shenlun_coach_session_dao, 'list_user', AsyncMock(return_value=[session]))

    result = await service.list_sessions(db=object(), user_id=9)

    assert result[0].id == 6
    assert result[0].last_summary == '优先补充材料依据'


@pytest.mark.asyncio
async def test_user_context_builds_stable_evidence_cards(monkeypatch: pytest.MonkeyPatch) -> None:
    service = ShenlunCoachService()
    memory = SimpleNamespace(
        memory_key='weakness.material',
        memory_type='weakness',
        content='材料依据不足',
        confidence=0.8,
    )
    run = SimpleNamespace(
        id=12,
        result_payload={
            'rubric': {'question_id': 33},
            'display_score': 10,
            'display_max_score': 20,
            'summary': {'weaknesses': ['材料依据不足']},
            'point_matches': [{'point_key': 'p1', 'status': 'missed'}],
        },
    )
    question = SimpleNamespace(id=33, code='Q-33', stem='根据材料概括主要做法。')
    note = SimpleNamespace(id=5, content='注意按主体分类。')
    import backend.plugin.agent.service.coach_service as module

    monkeypatch.setattr(module.shenlun_coach_memory_dao, 'list_user', AsyncMock(return_value=[memory]))
    db = SimpleNamespace(
        execute=AsyncMock(
            side_effect=[
                SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [run])),
                SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [question])),
                SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [note])),
            ]
        )
    )

    context = await service._build_user_context(db=db, user_id=9)

    evidence_ids = {item['evidence_id'] for item in context['evidence_cards']}
    assert 'grading_run:12:summary' in evidence_ids
    assert 'question:33' in evidence_ids
    assert 'note:5' in evidence_ids
    assert 'memory:weakness.material' in evidence_ids
