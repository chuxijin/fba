import asyncio

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, NoReturn
from unittest.mock import AsyncMock

import pytest

from backend.app.question_bank_v2.crud.crud_review import question_review_dao
from backend.app.question_bank_v2.schema.review import (
    REVIEW_THOUGHT_REQUIRED_MESSAGE,
    CreateExternalWrongQuestionParam,
    CreateQuestionReviewParam,
)
from backend.app.question_bank_v2.service import review_schedule_service as schedule_module
from backend.app.question_bank_v2.service import wrong_review_service as wrong_review_module
from backend.app.question_bank_v2.service.practice_schedule_service import (
    PRACTICE_LADDER_MINUTES,
    derive_rating,
    next_practice_level,
    next_practice_time,
)
from backend.app.question_bank_v2.service.review_schedule_service import ReviewScheduleService
from backend.app.question_bank_v2.service.wrong_review_service import WrongReviewService
from backend.common.exception import errors


class MappingResult:
    """模拟 SQLAlchemy mappings() 结果"""

    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows

    def mappings(self) -> 'MappingResult':
        return self

    def all(self) -> list[dict[str, Any]]:
        return self.rows


class _EmptyResult:
    """db.execute 的空结果桩：供无数据依赖的单元测试使用"""

    rowcount = 0

    def scalars(self) -> '_EmptyResult':
        return self

    def mappings(self) -> '_EmptyResult':
        return self

    def all(self) -> list[Any]:
        return []

    def first(self) -> None:
        return None

    def scalar(self) -> None:
        return None

    def scalar_one_or_none(self) -> None:
        return None

    def __iter__(self) -> 'Any':
        return iter([])


class DummyDB:
    """提供服务单元测试所需的最小异步会话接口"""

    def __init__(self) -> None:
        self.flush_count = 0
        self.added: list[object] = []

    async def flush(self) -> None:
        self.flush_count += 1

    def add(self, instance: object) -> None:
        self.added.append(instance)

    async def execute(self, *_args: object, **_kwargs: object) -> _EmptyResult:
        # 默认返回空结果：掌握度快照这类依赖真实数据的副作用在单元测试中不参与断言
        return _EmptyResult()


def _new_mastery() -> SimpleNamespace:
    """创建一份新的掌握度投影"""
    return SimpleNamespace(
        state='learning',
        mastery_score=Decimal('0.0000'),
        attempt_count=0,
        correct_count=0,
        last_attempt_time=None,
    )


def _new_wrong_state(**overrides: Any) -> SimpleNamespace:
    """创建一份错题本状态投影"""
    data: dict[str, Any] = {
        'id': 31,
        'status': 'active',
        'resolved_time': None,
        'wrong_count': 1,
        'correct_streak': 0,
        'review_count': 0,
        'practice_level': 0,
        'last_rating': None,
        'last_duration_ms': None,
        'next_practice_time': None,
        'is_pinned': False,
        'pinned_time': None,
        'question_id': 11,
        'source_attempt_id': None,
        'source_bank_item_id': None,
        'last_wrong_time': None,
        'last_practice_time': None,
        'last_wrong_response': None,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


# --- 客观派生调度：纯函数，无需数据库 ---


@pytest.mark.parametrize(
    ('is_correct', 'duration_ms', 'expected'),
    [
        (True, 500, 4),  # 又快又对
        (True, 1000, 3),  # 对但用时相当
        (True, 2000, 3),  # 对但更慢
        (False, 2000, 2),  # 慢且错，仍在调动记忆
        (False, 1000, 1),  # 错且没变快也没变慢，按最差处理
        (False, 500, 1),  # 又快又错，蒙或放弃
    ],
)
def test_derive_rating_covers_correctness_by_duration_matrix(
    *,
    is_correct: bool,
    duration_ms: int,
    expected: int,
) -> None:
    """对错与用时的 2×2 组合必须稳定映射到 1-4 级"""
    assert derive_rating(is_correct=is_correct, duration_ms=duration_ms, baseline_ms=1000) == expected


def test_derive_rating_degrades_without_baseline_or_duration() -> None:
    """缺基线或缺用时时退化为对 3 错 1，主观题待批不参与调度"""
    assert derive_rating(is_correct=True, duration_ms=None, baseline_ms=1000) == 3
    assert derive_rating(is_correct=False, duration_ms=800, baseline_ms=None) == 1
    assert derive_rating(is_correct=None, duration_ms=800, baseline_ms=1000) is None


def test_practice_ladder_is_monotonic_and_clamped() -> None:
    """阶梯必须单调递增，等级推进不越界"""
    assert list(PRACTICE_LADDER_MINUTES) == sorted(PRACTICE_LADDER_MINUTES)
    top = len(PRACTICE_LADDER_MINUTES) - 1
    assert next_practice_level(level=3, rating=1) == 0
    assert next_practice_level(level=0, rating=2) == 0
    assert next_practice_level(level=3, rating=3) == 4
    assert next_practice_level(level=top, rating=4) == top

    now = datetime(2026, 7, 27, 12, tzinfo=UTC)
    assert next_practice_time(level=0, now=now) == now + timedelta(minutes=PRACTICE_LADDER_MINUTES[0])
    assert next_practice_time(level=top + 5, now=now) == now + timedelta(minutes=PRACTICE_LADDER_MINUTES[top])


def test_ensure_mastery_initializes_only_on_demand(monkeypatch: pytest.MonkeyPatch) -> None:
    """首次接触题目时才创建掌握度，不能预生成全量用户题目笛卡尔积"""
    created_data: dict = {}

    async def fake_get_by_question(*_args: object, **_kwargs: object) -> None:
        await asyncio.sleep(0)

    async def fake_create(_db: object, data: dict[str, Any]) -> SimpleNamespace:
        await asyncio.sleep(0)
        created_data.update(data)
        return SimpleNamespace(**data)

    monkeypatch.setattr(schedule_module.user_question_mastery_dao, 'get_by_question', fake_get_by_question)
    monkeypatch.setattr(schedule_module.user_question_mastery_dao, 'create', fake_create)

    mastery = asyncio.run(ReviewScheduleService.ensure_mastery(db=None, user_id=7, question_id=11))

    assert mastery.state == 'learning'
    assert created_data == {'user_id': 7, 'question_id': 11, 'state': 'learning'}


# --- 作答驱动错题本状态 ---


class AttemptHarness:
    """作答同步错题本状态的依赖桩"""

    def __init__(self, *, existing: SimpleNamespace | None = None) -> None:
        self.mastery = _new_mastery()
        self.state = existing
        self.created: dict[str, Any] | None = None
        self.progress_attempt_ids: list[int] = []

    def patch(self, monkeypatch: pytest.MonkeyPatch) -> None:
        async def fake_ensure_mastery(**_kwargs: object) -> SimpleNamespace:
            await asyncio.sleep(0)
            return self.mastery

        async def fake_get_by_question(*_args: object, **_kwargs: object) -> SimpleNamespace | None:
            await asyncio.sleep(0)
            return self.state

        async def fake_create(_db: object, data: dict[str, Any]) -> SimpleNamespace:
            await asyncio.sleep(0)
            self.created = data
            self.state = _new_wrong_state(**{k: v for k, v in data.items() if k != 'created_by'})
            return self.state

        async def fake_apply_progress(_db: object, *, attempt: SimpleNamespace, bank_item_id: int | None) -> None:
            await asyncio.sleep(0)
            self.progress_attempt_ids.append(attempt.id)

        monkeypatch.setattr(ReviewScheduleService, 'ensure_mastery', fake_ensure_mastery)
        monkeypatch.setattr(schedule_module.wrong_question_state_dao, 'get_by_question', fake_get_by_question)
        monkeypatch.setattr(schedule_module.wrong_question_state_dao, 'create', fake_create)
        monkeypatch.setattr(schedule_module.user_bank_item_progress_dao, 'apply_attempt', fake_apply_progress)

    @staticmethod
    def attempt(*, attempt_id: int, is_correct: bool, duration_ms: int, now: datetime) -> SimpleNamespace:
        return SimpleNamespace(
            id=attempt_id,
            user_id=7,
            question_id=11,
            is_correct=is_correct,
            duration_ms=duration_ms,
            submitted_time=now,
            response_data='A' if is_correct else 'B',
        )


def test_wrong_answer_creates_state_and_schedules_first_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    """首次答错建立错题本状态，并记录用时基线与首次重练时间"""
    now = datetime(2026, 7, 27, 12, tzinfo=UTC)
    harness = AttemptHarness()
    harness.patch(monkeypatch)

    asyncio.run(
        ReviewScheduleService.apply_attempt(
            db=DummyDB(),
            attempt=harness.attempt(attempt_id=101, is_correct=False, duration_ms=9000, now=now),
            session_item=SimpleNamespace(bank_item_id=17, max_score=Decimal('1.00')),
        )
    )

    assert harness.created is not None
    assert harness.created['entry_source'] == 'attempt'
    assert harness.created['wrong_count'] == 1
    assert harness.created['last_wrong_response'] == 'B'
    assert harness.created['last_duration_ms'] == 9000
    assert harness.created['next_practice_time'] == next_practice_time(level=0, now=now)
    assert harness.mastery.attempt_count == 1
    assert harness.mastery.state == 'learning'


def test_wrong_answer_stores_original_module_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """首次答错时把原试卷模块路径写进错题状态，供章节内按题型聚拢"""
    now = datetime(2026, 7, 27, 12, tzinfo=UTC)
    harness = AttemptHarness()
    harness.patch(monkeypatch)

    asyncio.run(
        ReviewScheduleService.apply_attempt(
            db=DummyDB(),
            attempt=harness.attempt(attempt_id=102, is_correct=False, duration_ms=9000, now=now),
            session_item=SimpleNamespace(
                bank_item_id=17,
                max_score=Decimal('1.00'),
                display_config={
                    'section_name': '判断推理',
                    'external_practice': {'module_path': ['判断推理', '图形推理', '数量规律']},
                },
            ),
        )
    )

    assert harness.created is not None
    assert harness.created['entry_metadata'] == {
        'section_name': '判断推理',
        'module_path': ['判断推理', '图形推理', '数量规律'],
    }


def test_unreviewed_question_needs_full_streak_to_leave_wrong_book(monkeypatch: pytest.MonkeyPatch) -> None:
    """未复盘的题必须连对到偏好阈值才移出，中途答错清零"""
    now = datetime(2026, 7, 27, 12, tzinfo=UTC)
    harness = AttemptHarness(existing=_new_wrong_state(last_duration_ms=9000))
    harness.patch(monkeypatch)
    db = DummyDB()

    for index in range(2):
        asyncio.run(
            ReviewScheduleService.apply_attempt(
                db=db,
                attempt=harness.attempt(attempt_id=200 + index, is_correct=True, duration_ms=4000, now=now),
                session_item=SimpleNamespace(bank_item_id=17, max_score=Decimal('1.00')),
                resolve_threshold=3,
            )
        )
    assert harness.state.correct_streak == 2
    assert harness.state.status == 'active'

    asyncio.run(
        ReviewScheduleService.apply_attempt(
            db=db,
            attempt=harness.attempt(attempt_id=210, is_correct=True, duration_ms=3000, now=now),
            session_item=SimpleNamespace(bank_item_id=17, max_score=Decimal('1.00')),
            resolve_threshold=3,
        )
    )
    assert harness.state.correct_streak == 3
    assert harness.state.status == 'resolved'
    assert harness.state.resolved_time == now
    assert harness.state.next_practice_time is None
    assert harness.mastery.state == 'mastered'


def test_reviewed_question_leaves_wrong_book_after_single_correct(monkeypatch: pytest.MonkeyPatch) -> None:
    """复盘过的题已想清楚错因，做对一次即移出，无需连对到阈值"""
    now = datetime(2026, 7, 27, 12, tzinfo=UTC)
    harness = AttemptHarness(existing=_new_wrong_state(review_count=1, last_duration_ms=9000))
    harness.patch(monkeypatch)

    asyncio.run(
        ReviewScheduleService.apply_attempt(
            db=DummyDB(),
            attempt=harness.attempt(attempt_id=300, is_correct=True, duration_ms=4000, now=now),
            session_item=SimpleNamespace(bank_item_id=17, max_score=Decimal('1.00')),
            resolve_threshold=3,
        )
    )

    assert harness.state.correct_streak == 1
    assert harness.state.status == 'resolved'
    assert harness.mastery.state == 'mastered'


def test_relapse_reactivates_state_and_clears_resolved_time(monkeypatch: pytest.MonkeyPatch) -> None:
    """已移出的题再次答错要回到错题本，并清掉过期的解决时间"""
    now = datetime(2026, 7, 27, 12, tzinfo=UTC)
    harness = AttemptHarness(
        existing=_new_wrong_state(
            status='resolved',
            resolved_time=now - timedelta(days=1),
            correct_streak=3,
            review_count=1,
            practice_level=4,
            last_duration_ms=4000,
        )
    )
    harness.patch(monkeypatch)

    asyncio.run(
        ReviewScheduleService.apply_attempt(
            db=DummyDB(),
            attempt=harness.attempt(attempt_id=400, is_correct=False, duration_ms=2000, now=now),
            session_item=SimpleNamespace(bank_item_id=17, max_score=Decimal('1.00')),
        )
    )

    assert harness.state.status == 'active'
    assert harness.state.resolved_time is None
    assert harness.state.correct_streak == 0
    assert harness.state.wrong_count == 2
    # 又快又错派生为 1 级，阶梯归零重来
    assert harness.state.last_rating == 1
    assert harness.state.practice_level == 0
    assert harness.state.next_practice_time == next_practice_time(level=0, now=now)


def test_wrong_retry_without_bank_context_preserves_original_source(monkeypatch: pytest.MonkeyPatch) -> None:
    """自定义重练再次答错时不能清空原题库归属"""
    now = datetime(2026, 7, 27, 12, tzinfo=UTC)
    harness = AttemptHarness(existing=_new_wrong_state(source_bank_item_id=17, last_duration_ms=4000))
    harness.patch(monkeypatch)

    asyncio.run(
        ReviewScheduleService.apply_attempt(
            db=DummyDB(),
            attempt=harness.attempt(attempt_id=450, is_correct=False, duration_ms=2000, now=now),
            session_item=SimpleNamespace(bank_item_id=None, max_score=Decimal('1.00')),
        )
    )

    assert harness.state.source_bank_item_id == 17


def test_external_question_without_bank_context_still_syncs(monkeypatch: pytest.MonkeyPatch) -> None:
    """自主录入的错题没有题库上下文，也必须能正常重练并推进状态"""
    now = datetime(2026, 7, 27, 12, tzinfo=UTC)
    harness = AttemptHarness(existing=_new_wrong_state(review_count=1, last_duration_ms=8000))
    harness.patch(monkeypatch)

    asyncio.run(
        ReviewScheduleService.apply_attempt(
            db=DummyDB(),
            attempt=harness.attempt(attempt_id=500, is_correct=True, duration_ms=3000, now=now),
            session_item=SimpleNamespace(bank_item_id=None, max_score=Decimal('1.00')),
            resolve_threshold=3,
        )
    )

    assert harness.progress_attempt_ids == [500]
    assert harness.state.status == 'resolved'


# --- 外部错题录入 ---


class CaptureHarness:
    """外部错题录入服务依赖桩"""

    def __init__(self) -> None:
        self.question_create: dict[str, Any] = {}
        self.answer_upserts = 0
        self.knowledge_point_ids: list[int] = []
        self.review_events: list[dict[str, Any]] = []
        self.wrong_state_data: dict[str, Any] = {}
        self.expected = SimpleNamespace(id=31)
        # 录入时所在的领域：None 表示账号还没设过领域
        self.domain_category_id: int | None = 1400
        # 内容指纹命中的已有私有题：非空时不应再新建题目
        self.reusable: SimpleNamespace | None = None
        self.answer_question_ids: list[int] = []

    async def resolve_domain_category_id(self, **_kwargs: object) -> int | None:
        await asyncio.sleep(0)
        return self.domain_category_id

    async def no_op(self, *_args: object, **_kwargs: object) -> None:
        await asyncio.sleep(0)

    async def create_question(self, _db: object, **kwargs: Any) -> SimpleNamespace:
        await asyncio.sleep(0)
        self.question_create.update(kwargs)
        return SimpleNamespace(id=11)

    async def upsert_answer(self, *_args: object, **kwargs: Any) -> None:
        await asyncio.sleep(0)
        self.answer_upserts += 1
        self.answer_question_ids.append(kwargs['question_id'])

    async def find_reusable_question(self, *_args: object, **_kwargs: object) -> SimpleNamespace | None:
        await asyncio.sleep(0)
        return self.reusable

    async def replace_knowledge_points(self, _db: object, **kwargs: Any) -> None:
        await asyncio.sleep(0)
        self.knowledge_point_ids = [item.knowledge_point_id for item in kwargs['items']]

    async def ensure_mastery(self, **_kwargs: object) -> SimpleNamespace:
        await asyncio.sleep(0)
        return _new_mastery()

    async def create_wrong_state(self, _db: object, data: dict[str, Any]) -> SimpleNamespace:
        await asyncio.sleep(0)
        self.wrong_state_data = data
        return SimpleNamespace(id=31, **data)

    async def create_review(self, _db: object, data: dict[str, Any]) -> SimpleNamespace:
        await asyncio.sleep(0)
        self.review_events.append(data)
        return SimpleNamespace(id=41, **data)

    async def get_detail(self, **_kwargs: object) -> SimpleNamespace:
        await asyncio.sleep(0)
        return self.expected

    def patch(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """替换外部错题录入所需的数据库依赖"""
        monkeypatch.setattr(WrongReviewService, '_validate_links', self.no_op)
        monkeypatch.setattr(WrongReviewService, '_validate_assets', self.no_op)
        monkeypatch.setattr(WrongReviewService, 'get_detail', self.get_detail)
        monkeypatch.setattr(wrong_review_module.question_dao, 'create', self.create_question)
        monkeypatch.setattr(
            wrong_review_module.external_practice_dao,
            'find_reusable_question',
            self.find_reusable_question,
        )
        monkeypatch.setattr(wrong_review_module.question_answer_dao, 'upsert', self.upsert_answer)
        monkeypatch.setattr(wrong_review_module.question_explanation_dao, 'replace', self.no_op)
        monkeypatch.setattr(
            wrong_review_module.question_knowledge_point_dao,
            'replace',
            self.replace_knowledge_points,
        )
        monkeypatch.setattr(wrong_review_module.review_schedule_service, 'ensure_mastery', self.ensure_mastery)
        monkeypatch.setattr(wrong_review_module.wrong_question_state_dao, 'create', self.create_wrong_state)
        monkeypatch.setattr(wrong_review_module.question_review_dao, 'create', self.create_review)
        monkeypatch.setattr(wrong_review_module.question_review_dao, 'create_links', self.no_op)
        monkeypatch.setattr(
            wrong_review_module.knowledge_service,
            'resolve_optional_domain_category_id',
            self.resolve_domain_category_id,
        )

    @staticmethod
    def build_param() -> CreateExternalWrongQuestionParam:
        """构建可直接进入刷题系统的外部题录入参数"""
        return CreateExternalWrongQuestionParam(
            idempotency_key='capture-0001',
            entry_source='manual',
            entry_metadata={'source': '测试来源'},
            stem='Which option is correct?',
            knowledge_point_ids=[88],
            options=[
                {'option_code': 'A', 'content': 'Answer A'},
                {'option_code': 'B', 'content': 'Answer B'},
            ],
            answer={'answer_data': {'correct': 'A'}},
            explanations=[{'content': 'A is correct.', 'is_default': True}],
        )


def test_external_capture_is_private_and_practiceable(monkeypatch: pytest.MonkeyPatch) -> None:
    """外部题归用户私有，必须落权威答案才能进刷题系统，并立即排入重练"""
    harness = CaptureHarness()
    harness.patch(monkeypatch)

    result = asyncio.run(
        WrongReviewService.capture_external(
            db=DummyDB(),
            user_id=7,
            obj=harness.build_param(),
        )
    )

    assert result is harness.expected
    assert harness.question_create['owner_id'] == 7
    assert harness.question_create['visibility'] == 'private'
    assert harness.question_create['status'] == 'active'
    assert harness.answer_upserts == 1
    assert harness.knowledge_point_ids == [88]
    assert harness.wrong_state_data['next_practice_time'] is not None
    # 该参数包含知识点，属于录入时同步完成复盘
    assert [event['event_type'] for event in harness.review_events] == ['capture', 'review']


def test_external_capture_reuses_existing_question_by_content(monkeypatch: pytest.MonkeyPatch) -> None:
    """内容一致的题已存在时直接复用，错题导入与刷题记录共用同一份题目"""
    harness = CaptureHarness()
    harness.reusable = SimpleNamespace(id=77)
    harness.patch(monkeypatch)

    asyncio.run(WrongReviewService.capture_external(db=DummyDB(), user_id=7, obj=harness.build_param()))

    assert harness.question_create == {}
    assert harness.answer_question_ids == [77]
    assert harness.wrong_state_data['question_id'] == 77


def test_external_capture_reuse_with_existing_state_returns_detail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """同内容题已在错题本里时返回原状态，但补齐本次导入带来的答案内容"""
    harness = CaptureHarness()
    harness.reusable = SimpleNamespace(id=77)
    harness.patch(monkeypatch)

    async def find_state(*_args: object, **_kwargs: object) -> SimpleNamespace:
        await asyncio.sleep(0)
        return SimpleNamespace(id=31)

    async def get_state(*_args: object, **_kwargs: object) -> SimpleNamespace:
        await asyncio.sleep(0)
        return SimpleNamespace(id=31, question_id=77, entry_metadata={})

    async def get_question(*_args: object, **_kwargs: object) -> SimpleNamespace:
        await asyncio.sleep(0)
        return SimpleNamespace(id=77)

    monkeypatch.setattr(wrong_review_module.wrong_question_state_dao, 'get_by_question', find_state)
    monkeypatch.setattr(wrong_review_module.wrong_question_state_dao, 'get', get_state)
    monkeypatch.setattr(wrong_review_module.question_dao, 'get', get_question)

    result = asyncio.run(WrongReviewService.capture_external(db=DummyDB(), user_id=7, obj=harness.build_param()))

    assert result is harness.expected
    assert harness.question_create == {}
    assert harness.wrong_state_data == {}
    assert harness.answer_question_ids == [77]


def test_external_capture_keeps_user_wrong_response(monkeypatch: pytest.MonkeyPatch) -> None:
    """导入时必须把用户当时作答落进错题快照，详情页才能回显上次错答"""
    harness = CaptureHarness()
    harness.patch(monkeypatch)
    obj = harness.build_param().model_copy(update={'wrong_response': ['B', 'D']})

    asyncio.run(WrongReviewService.capture_external(db=DummyDB(), user_id=7, obj=obj))

    assert harness.wrong_state_data['last_wrong_response'] == ['B', 'D']


@pytest.mark.parametrize(('stored', 'expected'), [(None, 'B'), ('A', 'A')])
def test_external_reimport_backfills_only_missing_wrong_response(
    monkeypatch: pytest.MonkeyPatch,
    stored: str | None,
    expected: str,
) -> None:
    """重复导入只补旧版本缺失的作答快照，不能覆盖已有作答记录"""
    harness = CaptureHarness()
    harness.reusable = SimpleNamespace(id=77)
    harness.patch(monkeypatch)
    state = SimpleNamespace(id=31, question_id=77, entry_metadata={}, last_wrong_response=stored)

    async def find_state(*_args: object, **_kwargs: object) -> SimpleNamespace:
        await asyncio.sleep(0)
        return SimpleNamespace(id=31)

    async def get_state(*_args: object, **_kwargs: object) -> SimpleNamespace:
        await asyncio.sleep(0)
        return state

    async def get_question(*_args: object, **_kwargs: object) -> SimpleNamespace:
        await asyncio.sleep(0)
        return SimpleNamespace(id=77)

    monkeypatch.setattr(wrong_review_module.wrong_question_state_dao, 'get_by_question', find_state)
    monkeypatch.setattr(wrong_review_module.wrong_question_state_dao, 'get', get_state)
    monkeypatch.setattr(wrong_review_module.question_dao, 'get', get_question)
    obj = harness.build_param().model_copy(update={'wrong_response': 'B'})

    asyncio.run(WrongReviewService.capture_external(db=DummyDB(), user_id=7, obj=obj))

    assert state.last_wrong_response == expected


def test_external_capture_records_entry_domain(monkeypatch: pytest.MonkeyPatch) -> None:
    """自主录入没有题库归属，必须把录入时的领域写进 entry_metadata 才能按领域复盘"""
    harness = CaptureHarness()
    harness.patch(monkeypatch)

    asyncio.run(WrongReviewService.capture_external(db=DummyDB(), user_id=7, obj=harness.build_param()))

    assert harness.wrong_state_data['entry_metadata']['domain_category_id'] == 1400
    assert harness.wrong_state_data['entry_metadata']['source'] == '测试来源'


def test_external_capture_without_domain_keeps_metadata_clean(monkeypatch: pytest.MonkeyPatch) -> None:
    """账号还没设过领域时不写领域键，避免把错题错误地归到某个领域下"""
    harness = CaptureHarness()
    harness.domain_category_id = None
    harness.patch(monkeypatch)

    asyncio.run(WrongReviewService.capture_external(db=DummyDB(), user_id=7, obj=harness.build_param()))

    assert 'domain_category_id' not in harness.wrong_state_data['entry_metadata']


def test_external_capture_rejects_client_declared_domain() -> None:
    """领域由服务端按当前领域写入，客户端同名键必须被丢弃"""
    obj = CreateExternalWrongQuestionParam(
        idempotency_key='capture-0003',
        entry_source='manual',
        entry_metadata={'source': '测试来源', 'domain_category_id': 999},
        stem='Which option is correct?',
        options=[
            {'option_code': 'A', 'content': 'Answer A'},
            {'option_code': 'B', 'content': 'Answer B'},
        ],
        answer={'answer_data': {'correct': 'A'}},
    )

    assert 'domain_category_id' not in obj.entry_metadata


def test_external_capture_requires_authoritative_answer() -> None:
    """缺答案的外部题无法判分，参数层就要拦住"""
    with pytest.raises(ValueError, match='answer'):
        CreateExternalWrongQuestionParam(
            idempotency_key='capture-0002',
            entry_source='manual',
            stem='Missing answer',
        )


def test_external_capture_with_review_content_is_reviewed(monkeypatch: pytest.MonkeyPatch) -> None:
    """录入时填写复盘内容应同时形成正式复盘事件并离开待复盘队列"""
    harness = CaptureHarness()
    harness.patch(monkeypatch)
    obj = harness.build_param().model_copy(
        update={
            'summary': '没有核对题干条件',
            'tag_ids': [9],
        }
    )

    asyncio.run(WrongReviewService.capture_external(db=DummyDB(), user_id=7, obj=obj))

    assert [event['event_type'] for event in harness.review_events] == ['capture', 'review']
    assert harness.review_events[0]['summary'] is None
    assert harness.review_events[1]['summary'] == '没有核对题干条件'


def test_external_capture_without_review_content_stays_pending(monkeypatch: pytest.MonkeyPatch) -> None:
    """只录题目不填写反思时仅保留采集事件，继续留在待复盘队列"""
    harness = CaptureHarness()
    harness.patch(monkeypatch)
    obj = harness.build_param().model_copy(update={'knowledge_point_ids': []})

    asyncio.run(WrongReviewService.capture_external(db=DummyDB(), user_id=7, obj=obj))

    assert [event['event_type'] for event in harness.review_events] == ['capture']


# --- 复盘事件 ---


@pytest.mark.parametrize(
    ('summary', 'review_data'),
    [(None, {}), (' \n ', {'prevention': '\t '}), (None, {'prevention': 123}), ('', {'note': '其他内容'})],
)
def test_review_requires_at_least_one_thought(summary: str | None, review_data: dict[str, Any]) -> None:
    """标签、知识点和其他扩展字段不能替代错误思路或正确解法。"""
    with pytest.raises(ValueError, match=REVIEW_THOUGHT_REQUIRED_MESSAGE):
        CreateQuestionReviewParam(
            idempotency_key='review-empty',
            summary=summary,
            review_data=review_data,
            tag_ids=[1],
            knowledge_point_ids=[88],
        )


async def test_review_service_rejects_empty_thought_before_writing(monkeypatch: pytest.MonkeyPatch) -> None:
    """内部调用绕过 Schema 构造时，服务也不能追加没有思路的复盘。"""
    lookup = AsyncMock()
    monkeypatch.setattr(WrongReviewService, '_get_idempotent_review_result', lookup)
    obj = CreateQuestionReviewParam.model_construct(idempotency_key='review-empty', tag_ids=[1])
    with pytest.raises(errors.RequestError, match=REVIEW_THOUGHT_REQUIRED_MESSAGE):
        await WrongReviewService.submit_review(db=DummyDB(), user_id=7, wrong_state_id=31, obj=obj)
    lookup.assert_not_awaited()


@pytest.mark.parametrize(
    ('initial_count', 'status', 'summary', 'review_data'),
    [
        (0, 'active', '选项混淆', {}),
        (0, 'active', None, {'prevention': '先记录正确解法'}),
        (0, 'active', '错误步骤', {'prevention': '正确步骤'}),
        (1, 'active', None, {'prevention': '先列出题干约束，再排除不满足条件的选项'}),
        (2, 'resolved', None, {'prevention': '补充一个更简洁的解法'}),
    ],
)
def test_review_does_not_touch_wrong_book_or_schedule(
    monkeypatch: pytest.MonkeyPatch,
    initial_count: int,
    status: str,
    summary: str | None,
    review_data: dict[str, Any],
) -> None:
    """首次与多次复盘均可任选一种思路，追加记录且不改变已掌握状态或排期。"""
    wrong_state = _new_wrong_state(
        review_count=initial_count,
        status=status,
        next_practice_time=datetime(2026, 7, 30, tzinfo=UTC),
        practice_level=2,
    )
    created: dict[str, Any] = {}

    async def fake_no_existing(**_kwargs: object) -> None:
        await asyncio.sleep(0)

    async def fake_no_op(*_args: object, **_kwargs: object) -> None:
        await asyncio.sleep(0)

    async def fake_get(*_args: object, **_kwargs: object) -> SimpleNamespace:
        await asyncio.sleep(0)
        return wrong_state

    async def fake_create(_db: object, data: dict[str, Any]) -> SimpleNamespace:
        await asyncio.sleep(0)
        created.update(data)
        return SimpleNamespace(id=41, **data)

    async def fake_link_ids(*_args: object, **_kwargs: object) -> tuple[list[int], list[int]]:
        await asyncio.sleep(0)
        return [], []

    monkeypatch.setattr(WrongReviewService, '_get_idempotent_review_result', fake_no_existing)
    monkeypatch.setattr(WrongReviewService, '_validate_links', fake_no_existing)
    monkeypatch.setattr(wrong_review_module.wrong_question_state_dao, 'get', fake_get)
    monkeypatch.setattr(wrong_review_module.question_review_dao, 'create', fake_create)
    monkeypatch.setattr(wrong_review_module.question_review_dao, 'create_links', fake_no_op)
    monkeypatch.setattr(wrong_review_module.question_review_dao, 'get_link_ids', fake_link_ids)

    result = asyncio.run(
        WrongReviewService.submit_review(
            db=DummyDB(),
            user_id=7,
            wrong_state_id=31,
            obj=CreateQuestionReviewParam(
                idempotency_key='review-00001', summary=summary, review_data=review_data, tag_ids=[]
            ),
        )
    )

    assert created['event_type'] == 'review'
    assert created['summary'] == summary
    assert created['review_data'] == review_data
    assert wrong_state.review_count == initial_count + 1
    assert wrong_state.last_reviewed_time is not None
    assert wrong_state.status == status
    assert wrong_state.practice_level == 2
    assert result.next_practice_time == datetime(2026, 7, 30, tzinfo=UTC)
    assert result.review_count == initial_count + 1


@pytest.mark.parametrize('event_type', [None, 'capture', 'review'])
def test_review_history_filter_keeps_owner_and_stable_pagination(event_type: str | None) -> None:
    """完整时间线仍兼容录入事件；只看复盘时过滤在服务端分页前完成，不改变归属和稳定倒序"""
    stmt = question_review_dao.get_by_wrong_state_select(user_id=7, wrong_state_id=31, event_type=event_type)
    sql = str(stmt.compile(compile_kwargs={'literal_binds': True}))
    assert 'qbank_v2_question_review.user_id = 7' in sql
    assert 'qbank_v2_question_review.wrong_state_id = 31' in sql
    assert 'qbank_v2_question_review.deleted = 0' in sql
    assert 'ORDER BY qbank_v2_question_review.reviewed_time DESC, qbank_v2_question_review.id DESC' in sql
    if event_type is None:
        assert 'qbank_v2_question_review.event_type =' not in sql
    else:
        assert f"qbank_v2_question_review.event_type = '{event_type}'" in sql


def test_resolved_question_still_accepts_review(monkeypatch: pytest.MonkeyPatch) -> None:
    """已移出错题本的题考前仍可补记复盘，只有暂停的题被拦住"""
    suspended = _new_wrong_state(status='suspended')

    async def fake_no_existing(**_kwargs: object) -> None:
        await asyncio.sleep(0)

    async def fake_get(*_args: object, **_kwargs: object) -> SimpleNamespace:
        await asyncio.sleep(0)
        return suspended

    monkeypatch.setattr(WrongReviewService, '_get_idempotent_review_result', fake_no_existing)
    monkeypatch.setattr(wrong_review_module.wrong_question_state_dao, 'get', fake_get)

    with pytest.raises(errors.ConflictError, match='已暂停的错题不能提交复盘'):
        asyncio.run(
            WrongReviewService.submit_review(
                db=DummyDB(),
                user_id=7,
                wrong_state_id=31,
                obj=CreateQuestionReviewParam(idempotency_key='review-00002', summary='补记错误思路'),
            )
        )


def test_review_retry_is_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    """同一复盘幂等键重试直接复用结果，不重复写入事件"""
    expected = SimpleNamespace(review_count=1)

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
            obj=CreateQuestionReviewParam(idempotency_key='review-00001', summary='同一份思路'),
        )
    )

    assert result is expected


def test_review_idempotency_key_rejects_different_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    """复盘幂等键不能以不同内容重放，避免静默覆盖已有反思"""
    existing = SimpleNamespace(
        event_type='review',
        wrong_state_id=31,
        source_attempt_id=None,
        duration_ms=0,
        summary='原来的总结',
        review_data={},
    )

    async def fake_get_by_key(*_args: object, **_kwargs: object) -> SimpleNamespace:
        await asyncio.sleep(0)
        return existing

    monkeypatch.setattr(wrong_review_module.question_review_dao, 'get_by_idempotency_key', fake_get_by_key)

    with pytest.raises(errors.ConflictError, match='复盘提交幂等键已被其他请求使用'):
        asyncio.run(
            WrongReviewService._get_idempotent_review_result(
                db=None,
                user_id=7,
                wrong_state_id=31,
                obj=CreateQuestionReviewParam(idempotency_key='review-00001', summary='换了内容'),
            )
        )


def test_manual_resolve_and_resume_keep_mastery_in_sync(monkeypatch: pytest.MonkeyPatch) -> None:
    """手动移出与恢复必须同步掌握状态和重练排期"""
    wrong_state = _new_wrong_state(practice_level=3, next_practice_time=datetime(2026, 7, 30, tzinfo=UTC))
    mastery = _new_mastery()

    async def fake_get(*_args: object, **_kwargs: object) -> SimpleNamespace:
        await asyncio.sleep(0)
        return wrong_state

    async def fake_ensure_mastery(**_kwargs: object) -> SimpleNamespace:
        await asyncio.sleep(0)
        return mastery

    async def fake_get_wrong_item(**_kwargs: object) -> SimpleNamespace:
        await asyncio.sleep(0)
        return SimpleNamespace(id=31)

    monkeypatch.setattr(wrong_review_module.wrong_question_state_dao, 'get', fake_get)
    monkeypatch.setattr(wrong_review_module.review_schedule_service, 'ensure_mastery', fake_ensure_mastery)
    monkeypatch.setattr(WrongReviewService, '_get_wrong_item', fake_get_wrong_item)

    asyncio.run(
        WrongReviewService.update_state(
            db=DummyDB(),
            user_id=7,
            wrong_state_id=31,
            obj=wrong_review_module.UpdateWrongStateParam(action='resolve'),
        )
    )
    assert wrong_state.status == 'resolved'
    assert wrong_state.next_practice_time is None
    assert mastery.state == 'mastered'

    asyncio.run(
        WrongReviewService.update_state(
            db=DummyDB(),
            user_id=7,
            wrong_state_id=31,
            obj=wrong_review_module.UpdateWrongStateParam(action='reopen'),
        )
    )
    assert wrong_state.status == 'active'
    assert wrong_state.resolved_time is None
    assert wrong_state.next_practice_time is not None
    assert mastery.state == 'learning'


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


def test_wrong_statistics_scopes_knowledge_groups_to_default_system(monkeypatch: pytest.MonkeyPatch) -> None:
    """错题知识点分组必须把解析出的体系传给 DAO，按题库分组不受影响，且计数与分组同领域口径"""
    captured: list[tuple[object, str, list[int], list[int] | None]] = []
    statistics_scopes: list[list[int] | None] = []

    async def fake_resolve_domain(**_: object) -> int:
        await asyncio.sleep(0)
        return 1400

    async def fake_resolve_system_ids(**_: object) -> list[int]:
        await asyncio.sleep(0)
        return [2]

    async def fake_domain_scope(**_: object) -> list[int]:
        await asyncio.sleep(0)
        return [1400, 1365]

    async def fake_statistics(_db: object, **kwargs: object) -> dict[str, Any]:
        await asyncio.sleep(0)
        statistics_scopes.append(kwargs.get('domain_category_ids'))
        return {
            'total_count': 5,
            'active_count': 3,
            'resolved_count': 2,
            'wrong_occurrence_count': 6,
            'due_count': 2,
            'reviewed_count': 1,
            'pending_review_count': 2,
        }

    async def fake_group_counts(
        _db: object,
        *,
        user_id: int,
        group_by: str,
        knowledge_system_ids: list[int],
        domain_category_ids: list[int] | None = None,
    ) -> list[dict[str, Any]]:
        await asyncio.sleep(0)
        captured.append((user_id, group_by, list(knowledge_system_ids), domain_category_ids))
        return []

    monkeypatch.setattr(wrong_review_module.knowledge_service, 'resolve_domain_category_id', fake_resolve_domain)
    monkeypatch.setattr(wrong_review_module.knowledge_service, 'resolve_system_ids', fake_resolve_system_ids)
    monkeypatch.setattr(WrongReviewService, 'resolve_domain_scope', fake_domain_scope)
    monkeypatch.setattr(wrong_review_module.wrong_question_state_dao, 'get_statistics', fake_statistics)
    monkeypatch.setattr(wrong_review_module.wrong_question_state_dao, 'get_group_counts', fake_group_counts)

    asyncio.run(
        WrongReviewService.get_statistics(
            db=DummyDB(),
            user_id=7,
            group_by='knowledge_point',
        )
    )
    assert captured == [(7, 'knowledge_point', [2], [1400, 1365])]

    captured.clear()
    asyncio.run(
        WrongReviewService.get_statistics(
            db=DummyDB(),
            user_id=7,
            group_by='bank',
        )
    )
    # 按题库分组不解析知识体系，DAO 收到空列表；两种分组都带上同一份领域范围
    assert captured == [(7, 'bank', [], [1400, 1365])]
    assert statistics_scopes == [[1400, 1365], [1400, 1365]]


def test_wrong_statistics_builds_knowledge_tree_and_keeps_external_flat(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """题库来源的错题补知识体系父链，自主录入仍平铺挂在「自主录入」下"""

    async def fake_domain_scope(**_: object) -> list[int]:
        await asyncio.sleep(0)
        return [1400, 1365]

    async def fake_resolve_domain(**_: object) -> int:
        await asyncio.sleep(0)
        return 1400

    async def fake_resolve_system_ids(**_: object) -> list[int]:
        await asyncio.sleep(0)
        return [2]

    async def fake_statistics(_db: object, **_: object) -> dict[str, Any]:
        await asyncio.sleep(0)
        return {
            'total_count': 2,
            'active_count': 2,
            'resolved_count': 0,
            'wrong_occurrence_count': 2,
            'due_count': 0,
            'reviewed_count': 0,
            'pending_review_count': 0,
        }

    async def fake_group_counts(_db: object, **_: object) -> list[dict[str, Any]]:
        await asyncio.sleep(0)
        return [
            {'id': 3, 'name': '唯物论', 'count': 1, 'question_ids': [101], 'entry_scope': 'bank'},
            {'id': 9, 'name': '手工录入点', 'count': 1, 'question_ids': [901], 'entry_scope': 'external'},
        ]

    monkeypatch.setattr(WrongReviewService, 'resolve_domain_scope', fake_domain_scope)
    monkeypatch.setattr(wrong_review_module.knowledge_service, 'resolve_domain_category_id', fake_resolve_domain)
    monkeypatch.setattr(wrong_review_module.knowledge_service, 'resolve_system_ids', fake_resolve_system_ids)
    monkeypatch.setattr(wrong_review_module.wrong_question_state_dao, 'get_statistics', fake_statistics)
    monkeypatch.setattr(wrong_review_module.wrong_question_state_dao, 'get_group_counts', fake_group_counts)

    db = AsyncMock()
    db.execute.side_effect = [
        MappingResult([{'id': 3, 'name': '唯物论', 'parent_id': 2, 'path': '/1/2/3/', 'sort_order': 0}]),
        MappingResult([
            {'id': 1, 'name': '政治', 'parent_id': None, 'path': '/1/', 'sort_order': 0},
            {'id': 2, 'name': '马原', 'parent_id': 1, 'path': '/1/2/', 'sort_order': 0},
        ]),
    ]

    statistics = asyncio.run(WrongReviewService.get_statistics(db=db, user_id=7, group_by='knowledge_point'))

    assert [group.name for group in statistics.groups] == ['马原', '自主录入']
    assert statistics.groups[0].children[0].question_ids == [101]
    assert statistics.groups[1].children[0].question_ids == [901]


def test_get_latest_module_path_query_structure() -> None:
    """验证获取错题原试卷模块路径的 SQL 能正确识别主表并生成合法 JOIN"""
    from sqlalchemy import and_, select
    from sqlalchemy.dialects import postgresql
    from backend.app.question_bank_v2.model.practice import QbPracticeSessionItem, QbQuestionAttempt
    from backend.app.question_bank_v2.crud.crud_practice import question_attempt_dao

    module_path = QbPracticeSessionItem.display_config['external_practice']['module_path']
    stmt = (
        select(module_path)
        .select_from(QbQuestionAttempt)
        .join(
            QbPracticeSessionItem,
            and_(
                QbPracticeSessionItem.id == QbQuestionAttempt.session_item_id,
                QbPracticeSessionItem.deleted == 0,
            ),
        )
        .where(
            QbQuestionAttempt.user_id == 1,
            QbQuestionAttempt.question_id == 2,
            QbQuestionAttempt.deleted == 0,
            module_path.is_not(None),
        )
    )
    compiled = str(stmt.compile(dialect=postgresql.dialect()))
    assert 'FROM qbank_v2_question_attempt JOIN qbank_v2_practice_session_item' in compiled

