"""统计审计只读核对回归：事实重算期望值，与物化统计逐字段比较。

全部用例用内存行与 AsyncMock 模拟 db.execute/get_by_question，不连接任何真实数据库。
"""

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

from backend.app.question_bank_v2.service import statistics_audit_service as audit_module
from backend.app.question_bank_v2.service.statistics_audit_service import audit_question_statistics


class _Result:
    def __init__(self, rows: list[tuple[Any, Any]]) -> None:
        self._rows = rows

    def all(self) -> list[tuple[Any, Any]]:
        return list(self._rows)


class _AuditDB:
    """只实现 execute，模拟只读审计数据库；不提供任何写入方法。"""

    def __init__(self, rows: list[tuple[Any, Any]]) -> None:
        self.rows = rows
        self.executed = 0

    async def execute(self, statement: Any, *args: Any, **kwargs: Any) -> _Result:
        self.executed += 1
        return _Result(self.rows)


def _attempt(
    *,
    attempt_id: int,
    session_item_id: int = 21,
    attempt_no: int = 1,
    answer: str = 'A',
    is_correct: bool | None = True,
    grading_result: dict[str, Any] | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=attempt_id,
        session_item_id=session_item_id,
        attempt_no=attempt_no,
        response_data={'answer': answer},
        is_correct=is_correct,
        grading_result={} if grading_result is None else grading_result,
    )


def _session(*, mode: str = 'practice', status: str = 'in_progress') -> SimpleNamespace:
    return SimpleNamespace(mode=mode, status=status)


def _statistics(
    *,
    attempt_count: int,
    graded_count: int,
    correct_count: int,
    distribution: dict[str, int],
) -> SimpleNamespace:
    return SimpleNamespace(
        attempt_count=attempt_count,
        graded_count=graded_count,
        correct_count=correct_count,
        response_distribution=distribution,
    )


async def _run_audit(
    monkeypatch: pytest.MonkeyPatch,
    *,
    rows: list[tuple[Any, Any]],
    actual: SimpleNamespace,
    question_ids: tuple[int, ...] = (31,),
) -> tuple[list[dict[str, Any]], _AuditDB, AsyncMock]:
    db = _AuditDB(rows)
    get_by_question = AsyncMock(return_value=actual)
    monkeypatch.setattr(audit_module.question_statistics_dao, 'get_by_question', get_by_question)
    reports = await audit_question_statistics(db=db, question_ids=list(question_ids))
    return reports, db, get_by_question


async def test_practice_multiple_attempts_are_all_counted(monkeypatch: pytest.MonkeyPatch) -> None:
    """普通练习的历次提交都计入样本，期望值与统计事实一致。"""
    rows = [
        (_attempt(attempt_id=1, attempt_no=2, answer='A', is_correct=True), _session()),
        (_attempt(attempt_id=2, attempt_no=1, answer='B', is_correct=False), _session()),
    ]
    actual = _statistics(attempt_count=2, graded_count=2, correct_count=1, distribution={'A': 1, 'B': 1})

    reports, db, get_by_question = await _run_audit(monkeypatch, rows=rows, actual=actual)

    assert db.executed == 1
    get_by_question.assert_awaited_once_with(db, 31)
    report = reports[0]
    assert report['expected'] == {
        'attempt_count': 2,
        'graded_count': 2,
        'correct_count': 1,
        'response_distribution': {'A': 1, 'B': 1},
    }
    assert report['actual'] == report['expected']
    assert report['matches'] is True
    assert report['uncertain_attempt_ids'] == []


async def test_exam_only_latest_attempt_per_item_is_counted(monkeypatch: pytest.MonkeyPatch) -> None:
    """考试/模考只取每题最高 attempt_no，早期修改不进入期望样本。"""
    rows = [
        (
            _attempt(
                attempt_id=2,
                attempt_no=2,
                answer='B',
                grading_result={'_projection': {'submitted': True, 'graded': True}},
            ),
            _session(mode='exam', status='submitted'),
        ),
        (
            _attempt(
                attempt_id=1,
                attempt_no=1,
                answer='A',
                is_correct=False,
                grading_result={'_projection': {'submitted': True, 'graded': True}},
            ),
            _session(mode='exam', status='submitted'),
        ),
    ]
    actual = _statistics(attempt_count=1, graded_count=1, correct_count=1, distribution={'B': 1})

    reports, _, _ = await _run_audit(monkeypatch, rows=rows, actual=actual)

    report = reports[0]
    assert report['expected'] == {
        'attempt_count': 1,
        'graded_count': 1,
        'correct_count': 1,
        'response_distribution': {'B': 1},
    }
    assert report['matches'] is True


async def test_unsubmitted_exam_attempt_is_not_counted(monkeypatch: pytest.MonkeyPatch) -> None:
    """考试未交卷且未投影的作答不进入统计样本。"""
    rows = [(_attempt(attempt_id=1, answer='A', grading_result={}), _session(mode='exam', status='in_progress'))]
    actual = _statistics(attempt_count=0, graded_count=0, correct_count=0, distribution={})

    reports, _, _ = await _run_audit(monkeypatch, rows=rows, actual=actual)

    report = reports[0]
    assert report['expected']['attempt_count'] == 0
    assert report['expected']['response_distribution'] == {}
    assert report['matches'] is True
    assert report['uncertain_attempt_ids'] == []


async def test_cancelled_unsettled_attempt_is_reported_uncertain(monkeypatch: pytest.MonkeyPatch) -> None:
    """已取消会话的旧作答无法判断是否结算过，单独列出且整体标记不匹配。"""
    rows = [(_attempt(attempt_id=5, answer='A', grading_result={}), _session(mode='exam', status='cancelled'))]
    actual = _statistics(attempt_count=0, graded_count=0, correct_count=0, distribution={})

    reports, _, _ = await _run_audit(monkeypatch, rows=rows, actual=actual)

    report = reports[0]
    assert report['expected']['attempt_count'] == 0
    assert report['uncertain_attempt_ids'] == [5]
    assert report['matches'] is False


async def test_external_import_attempt_is_excluded(monkeypatch: pytest.MonkeyPatch) -> None:
    """外部导入的历史作答不属于在线统计事实。"""
    rows = [
        (
            _attempt(attempt_id=9, answer='A', grading_result={'origin': 'external_practice'}),
            _session(mode='exam', status='submitted'),
        ),
    ]
    actual = _statistics(attempt_count=0, graded_count=0, correct_count=0, distribution={})

    reports, _, _ = await _run_audit(monkeypatch, rows=rows, actual=actual)

    report = reports[0]
    assert report['expected']['attempt_count'] == 0
    assert report['matches'] is True
    assert report['uncertain_attempt_ids'] == []


async def test_distribution_difference_marks_report_as_not_matching(monkeypatch: pytest.MonkeyPatch) -> None:
    """计数一致但分布不同也必须判定不匹配。"""
    rows = [(_attempt(attempt_id=1, answer='A', is_correct=True), _session())]
    actual = _statistics(attempt_count=1, graded_count=1, correct_count=1, distribution={'B': 1})

    reports, _, _ = await _run_audit(monkeypatch, rows=rows, actual=actual)

    report = reports[0]
    assert report['expected']['response_distribution'] == {'A': 1}
    assert report['actual']['response_distribution'] == {'B': 1}
    assert report['matches'] is False


async def test_audit_sorts_dedupes_question_ids_and_never_writes(monkeypatch: pytest.MonkeyPatch) -> None:
    """题目 ID 去重升序各读一次，审计链路只读不写。"""
    actual = _statistics(attempt_count=0, graded_count=0, correct_count=0, distribution={})

    reports, db, get_by_question = await _run_audit(
        monkeypatch,
        rows=[],
        actual=actual,
        question_ids=(33, 31, 33),
    )

    assert [report['question_id'] for report in reports] == [31, 33]
    assert db.executed == 2
    assert get_by_question.await_count == 2
    for name in ('add', 'add_all', 'flush', 'commit', 'delete'):
        assert not hasattr(db, name)
