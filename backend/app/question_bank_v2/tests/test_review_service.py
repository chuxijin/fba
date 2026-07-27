import asyncio

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, NoReturn

import pytest

from backend.app.question_bank_v2.schema.review import (
    CreateExternalWrongQuestionParam,
    CreateQuestionReviewParam,
)
from backend.app.question_bank_v2.service import review_schedule_service as schedule_module
from backend.app.question_bank_v2.service import wrong_review_service as wrong_review_module
from backend.app.question_bank_v2.service.review_schedule_service import ReviewScheduleService
from backend.app.question_bank_v2.service.wrong_review_service import WrongReviewService
from backend.common.exception import errors
from backend.common.fsrs import NEW_CARD_STATE


class DummyDB:
    """提供服务单元测试所需的最小异步会话接口"""

    def __init__(self) -> None:
        self.flush_count = 0

    async def flush(self) -> None:
        self.flush_count += 1


def _new_mastery(*, now: datetime) -> SimpleNamespace:
    """创建一份新的 FSRS 掌握度投影"""
    return SimpleNamespace(
        algorithm_name='fsrs',
        algorithm_version='test',
        algorithm_state={'state': NEW_CARD_STATE, 'step': 0, 'stability': None, 'difficulty': None},
        state='learning',
        mastery_score=Decimal('0.0000'),
        attempt_count=0,
        correct_count=0,
        review_count=0,
        lapse_count=0,
        last_attempt_time=None,
        last_review_time=None,
        next_review_time=now,
    )


def test_ensure_mastery_initializes_fsrs_only_on_demand(monkeypatch: pytest.MonkeyPatch) -> None:
    """首次接触题目时才创建到期状态，不能预生成全量用户题目笛卡尔积"""
    now = datetime(2026, 7, 27, 12, tzinfo=UTC)
    created_data: dict = {}

    async def fake_get_by_question(*_args: object, **_kwargs: object) -> None:
        await asyncio.sleep(0)

    async def fake_create(_db: object, data: dict[str, Any]) -> SimpleNamespace:
        await asyncio.sleep(0)
        created_data.update(data)
        return SimpleNamespace(**data)

    monkeypatch.setattr(schedule_module.user_question_mastery_dao, 'get_by_question', fake_get_by_question)
    monkeypatch.setattr(schedule_module.user_question_mastery_dao, 'create', fake_create)

    mastery = asyncio.run(
        ReviewScheduleService.ensure_mastery(
            db=None,
            user_id=7,
            question_id=11,
            question_revision_id=13,
            now=now,
        )
    )

    assert mastery.next_review_time == now
    assert created_data['algorithm_name'] == 'fsrs'
    assert created_data['algorithm_state'] == {
        'state': NEW_CARD_STATE,
        'step': 0,
        'stability': None,
        'difficulty': None,
    }


def test_fsrs_supports_again_hard_good_and_easy() -> None:
    """四级评分均应推进一次 FSRS，且新卡片间隔按评分单调增加"""
    now = datetime(2026, 7, 27, 12, tzinfo=UTC)
    due_times = []

    for rating in range(1, 5):
        mastery = _new_mastery(now=now)
        _, result, _ = asyncio.run(
            ReviewScheduleService.schedule_review(
                db=DummyDB(),
                mastery=mastery,
                rating=rating,
                reviewed_time=now,
            )
        )
        due_times.append(result.next_due)
        assert result.next_due > now
        assert mastery.review_count == 1
        assert mastery.last_review_time == now
        assert mastery.mastery_score == (Decimal(rating - 1) / Decimal(10)).quantize(Decimal('0.0001'))

    assert due_times == sorted(due_times)


def test_attempts_update_mastery_and_wrong_projection(monkeypatch: pytest.MonkeyPatch) -> None:
    """答错创建错题，随后答对只更新当前投影，不伪造复盘事件"""
    now = datetime(2026, 7, 27, 12, tzinfo=UTC)
    mastery = _new_mastery(now=now)
    mastery.state = 'review'
    created_state: SimpleNamespace | None = None
    lookup_count = 0

    async def fake_ensure_mastery(**_kwargs: object) -> SimpleNamespace:
        await asyncio.sleep(0)
        return mastery

    async def fake_get_by_question(*_args: object, **_kwargs: object) -> SimpleNamespace | None:
        nonlocal lookup_count
        await asyncio.sleep(0)
        lookup_count += 1
        return None if lookup_count == 1 else created_state

    async def fake_create(_db: object, data: dict[str, Any]) -> SimpleNamespace:
        nonlocal created_state
        await asyncio.sleep(0)
        created_state = SimpleNamespace(correct_streak=0, **data)
        return created_state

    monkeypatch.setattr(ReviewScheduleService, 'ensure_mastery', fake_ensure_mastery)
    monkeypatch.setattr(schedule_module.wrong_question_state_dao, 'get_by_question', fake_get_by_question)
    monkeypatch.setattr(schedule_module.wrong_question_state_dao, 'create', fake_create)

    wrong_attempt = SimpleNamespace(
        id=101,
        user_id=7,
        question_id=11,
        question_revision_id=13,
        is_correct=False,
        submitted_time=now,
        response_data='B',
    )
    session_item = SimpleNamespace(bank_item_id=17)
    db = DummyDB()
    asyncio.run(ReviewScheduleService.apply_attempt(db=db, attempt=wrong_attempt, session_item=session_item))

    assert created_state is not None
    assert created_state.entry_source == 'attempt'
    assert created_state.wrong_count == 1
    assert created_state.last_wrong_response == 'B'
    assert mastery.attempt_count == 1
    assert mastery.lapse_count == 1
    assert mastery.state == 'learning'

    correct_attempt = SimpleNamespace(
        id=102,
        user_id=7,
        question_id=11,
        question_revision_id=13,
        is_correct=True,
        submitted_time=now,
        response_data='A',
    )
    asyncio.run(ReviewScheduleService.apply_attempt(db=db, attempt=correct_attempt, session_item=session_item))

    assert created_state.correct_streak == 1
    assert created_state.wrong_count == 1
    assert mastery.attempt_count == 2
    assert mastery.correct_count == 1


class CaptureHarness:
    """外部错题录入服务依赖桩"""

    def __init__(self) -> None:
        self.now = datetime(2026, 7, 27, 12, tzinfo=UTC)
        self.question_create: dict[str, Any] = {}
        self.revision_create: dict[str, Any] = {}
        self.published: list[tuple[int, int]] = []
        self.expected = SimpleNamespace(id=31)

    async def none_result(self, **_kwargs: object) -> None:
        await asyncio.sleep(0)

    async def no_op(self, *_args: object, **_kwargs: object) -> None:
        await asyncio.sleep(0)

    async def create_question(self, _db: object, **kwargs: Any) -> SimpleNamespace:
        await asyncio.sleep(0)
        self.question_create.update(kwargs)
        return SimpleNamespace(id=11)

    async def create_revision(self, _db: object, **kwargs: Any) -> SimpleNamespace:
        await asyncio.sleep(0)
        self.revision_create.update(kwargs)
        return SimpleNamespace(id=21)

    async def publish(self, **kwargs: Any) -> SimpleNamespace:
        await asyncio.sleep(0)
        self.published.append((kwargs['question_id'], kwargs['revision_id']))
        return SimpleNamespace(id=kwargs['revision_id'])

    async def ensure_mastery(self, **_kwargs: object) -> SimpleNamespace:
        await asyncio.sleep(0)
        return SimpleNamespace(algorithm_name='fsrs', algorithm_version='test', next_review_time=self.now)

    async def create_wrong_state(self, _db: object, data: dict[str, Any]) -> SimpleNamespace:
        await asyncio.sleep(0)
        return SimpleNamespace(id=31, **data)

    async def create_review(self, _db: object, data: dict[str, Any]) -> SimpleNamespace:
        await asyncio.sleep(0)
        return SimpleNamespace(id=41, **data)

    async def get_wrong_item(self, **_kwargs: object) -> SimpleNamespace:
        await asyncio.sleep(0)
        return self.expected

    async def fail_schedule(self, **_kwargs: object) -> NoReturn:
        await asyncio.sleep(0)
        raise AssertionError('capture event must not advance FSRS')

    def patch(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """替换外部错题录入所需的数据库和发布依赖"""
        monkeypatch.setattr(WrongReviewService, '_get_idempotent_capture', self.none_result)
        monkeypatch.setattr(WrongReviewService, '_validate_links', self.no_op)
        monkeypatch.setattr(WrongReviewService, '_validate_assets', self.no_op)
        monkeypatch.setattr(WrongReviewService, '_get_wrong_item', self.get_wrong_item)
        monkeypatch.setattr(wrong_review_module.question_dao, 'create', self.create_question)
        monkeypatch.setattr(wrong_review_module.question_revision_dao, 'create_data', self.create_revision)
        monkeypatch.setattr(wrong_review_module.question_answer_dao, 'upsert', self.no_op)
        monkeypatch.setattr(wrong_review_module.question_explanation_dao, 'replace', self.no_op)
        monkeypatch.setattr(wrong_review_module.question_external_ref_dao, 'create', self.no_op)
        monkeypatch.setattr(wrong_review_module.question_service, 'publish_revision', self.publish)
        monkeypatch.setattr(wrong_review_module.review_schedule_service, 'ensure_mastery', self.ensure_mastery)
        monkeypatch.setattr(wrong_review_module.review_schedule_service, 'schedule_review', self.fail_schedule)
        monkeypatch.setattr(wrong_review_module.wrong_question_state_dao, 'create', self.create_wrong_state)
        monkeypatch.setattr(wrong_review_module.question_review_dao, 'create', self.create_review)
        monkeypatch.setattr(wrong_review_module.question_review_dao, 'create_links', self.no_op)

    @staticmethod
    def build_param(*, case: str) -> CreateExternalWrongQuestionParam:
        """构建完整或不完整的外部题录入参数"""
        data: dict[str, Any] = {
            'idempotency_key': 'capture-0001',
            'entry_source': 'manual',
            'stem': 'Which option is correct?',
        }
        if case == 'complete':
            data.update(
                {
                    'options': [
                        {'option_code': 'A', 'content': 'Answer A'},
                        {'option_code': 'B', 'content': 'Answer B'},
                    ],
                    'answer': {'answer_data': {'correct': 'A'}},
                    'explanations': [{'content': 'A is correct.', 'is_default': True}],
                }
            )
        return CreateExternalWrongQuestionParam(**data)


@pytest.mark.parametrize('case', ['draft', 'complete'])
def test_external_capture_is_private_and_does_not_advance_fsrs(
    monkeypatch: pytest.MonkeyPatch,
    case: str,
) -> None:
    """外部题始终归用户私有；完整题发布，不完整题保留草稿，录入事件不推进 FSRS"""
    harness = CaptureHarness()
    harness.patch(monkeypatch)

    result = asyncio.run(
        WrongReviewService.capture_external(
            db=DummyDB(),
            user_id=7,
            obj=harness.build_param(case=case),
        )
    )

    assert result is harness.expected
    assert harness.question_create['owner_id'] == 7
    assert harness.question_create['visibility'] == 'private'
    assert harness.revision_create['data']['status'] == 'draft'
    assert harness.published == ([(11, 21)] if case == 'complete' else [])


def test_review_retry_is_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    """同一复习幂等键重试直接复用结果，不重复推进 FSRS"""
    expected = SimpleNamespace(next_review_time=datetime(2026, 7, 28, tzinfo=UTC))

    async def fake_existing(**_kwargs: object) -> SimpleNamespace:
        await asyncio.sleep(0)
        return expected

    async def fail_get(*_args: object, **_kwargs: object) -> NoReturn:
        await asyncio.sleep(0)
        raise AssertionError('idempotent retry must not lock or mutate state')

    monkeypatch.setattr(WrongReviewService, '_get_idempotent_review_result', fake_existing)
    monkeypatch.setattr(wrong_review_module.wrong_question_state_dao, 'get', fail_get)

    result = asyncio.run(
        WrongReviewService.submit_review(
            db=DummyDB(),
            user_id=7,
            wrong_state_id=31,
            obj=CreateQuestionReviewParam(idempotency_key='review-00001', rating=3),
        )
    )

    assert result is expected


def test_capture_idempotency_key_rejects_different_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    """录入幂等键与规范化请求绑定，不能复用到另一道外部题"""
    capture_ref = SimpleNamespace(metadata_json={'request_hash': 'different-request'})

    async def fake_get_by_source(*_args: object, **_kwargs: object) -> SimpleNamespace:
        await asyncio.sleep(0)
        return capture_ref

    monkeypatch.setattr(wrong_review_module.question_external_ref_dao, 'get_by_source', fake_get_by_source)
    obj = CreateExternalWrongQuestionParam(
        idempotency_key='capture-0001',
        entry_source='manual',
        stem='new payload',
    )

    with pytest.raises(errors.ConflictError, match='错题录入幂等键已被其他请求使用'):
        asyncio.run(WrongReviewService._get_idempotent_capture(db=None, user_id=7, obj=obj))


def test_review_idempotency_key_rejects_different_rating(monkeypatch: pytest.MonkeyPatch) -> None:
    """复盘幂等键不能以不同评分重放，避免静默重复调度"""
    existing = SimpleNamespace(event_type='review', wrong_state_id=31, rating=4)

    async def fake_get_by_key(*_args: object, **_kwargs: object) -> SimpleNamespace:
        await asyncio.sleep(0)
        return existing

    monkeypatch.setattr(wrong_review_module.question_review_dao, 'get_by_idempotency_key', fake_get_by_key)
    obj = CreateQuestionReviewParam(idempotency_key='review-00001', rating=3)

    with pytest.raises(errors.ConflictError, match='复习提交幂等键已被其他请求使用'):
        asyncio.run(
            WrongReviewService._get_idempotent_review_result(
                db=None,
                user_id=7,
                wrong_state_id=31,
                obj=obj,
            )
        )


def test_mastered_review_suspends_due_projection() -> None:
    """错题标记已掌握时同步停止掌握度到期扫描"""
    wrong_state = SimpleNamespace(status='active', resolved_time=None)
    mastery = SimpleNamespace(state='review')
    reviewed_time = datetime(2026, 7, 27, 12, tzinfo=UTC)

    WrongReviewService._apply_review_outcome(
        wrong_state=wrong_state,
        mastery=mastery,
        outcome='mastered',
        rating=4,
        reviewed_time=reviewed_time,
    )

    assert wrong_state.status == 'resolved'
    assert wrong_state.resolved_time == reviewed_time
    assert mastery.state == 'mastered'


def test_review_links_reject_other_users_tags(monkeypatch: pytest.MonkeyPatch) -> None:
    """复盘关联只允许系统标签和当前用户自己的标签"""

    async def fake_valid_tags(*_args: object, **_kwargs: object) -> set[int]:
        await asyncio.sleep(0)
        return {1}

    async def fail_knowledge(*_args: object, **_kwargs: object) -> NoReturn:
        await asyncio.sleep(0)
        raise AssertionError('invalid tags must fail before knowledge point lookup')

    monkeypatch.setattr(wrong_review_module.review_reference_dao, 'get_valid_tag_ids', fake_valid_tags)
    monkeypatch.setattr(
        wrong_review_module.review_reference_dao,
        'get_valid_knowledge_point_ids',
        fail_knowledge,
    )

    with pytest.raises(errors.NotFoundError, match='复盘标签不存在或不可用'):
        asyncio.run(
            WrongReviewService._validate_links(
                db=None,
                user_id=7,
                tag_ids=[1, 2],
                knowledge_point_ids=[],
            )
        )
