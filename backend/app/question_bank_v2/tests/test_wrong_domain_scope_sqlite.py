"""跨领域错题回归：用真实 SQLite 执行 DAO 查询。

场景：同一用户同时有考公(1400)和考研(1)题库错题，题库作答的 entry_metadata
通常只有 {} 或 section_name，没有 domain_category_id。切到任一领域后，
列表、待复盘、章节、集合和计数都只能看到该领域；历史无领域的自主录入仍兼容。
"""

import json

from collections.abc import Iterator, Sequence
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest

from sqlalchemy import BigInteger, and_, cast, exists, or_, select

from backend.app.question_bank_v2.crud.crud_review import (
    CRUDWrongQuestionState,
    wrong_question_state_dao,
)
from backend.app.question_bank_v2.model.bank import (
    QbBank,
    QbBankItem,
    QbBankRevision,
)
from backend.app.question_bank_v2.model.catalog import QbBankCategory
from backend.app.question_bank_v2.schema.review import (
    ENTRY_METADATA_DOMAIN_KEY,
    UNSECTIONED_SECTION_NAME,
    WrongQuestionFilters,
)
from backend.app.question_bank_v2.service.wrong_review_service import WrongReviewService
from backend.app.question_bank_v2.tests.test_wrong_browse import BrowseDB

KAOGONG = 1400
KAOYAN = 1
USER_ID = 77

KAOGONG_PENDING = {101, 102, 108, 110, 111}
KAOYAN_PENDING = {104, 105, 109, 110, 111}


class CrossDomainBrowseDB(BrowseDB):
    """在 BrowseDB 基础上单独插入跨领域样例，不改动原有用户数据。"""

    def __init__(self) -> None:
        super().__init__()
        self._seed_cross_domain()

    def _add_state(
        self,
        state_id: int,
        *,
        question_id: int,
        source: str = 'attempt',
        item_id: int | None = None,
        metadata: dict[str, Any] | None = None,
        status: str = 'active',
        reviews: int = 0,
        user_id: int = USER_ID,
        deleted: int = 0,
    ) -> None:
        self.connection.execute(
            'INSERT INTO qbank_v2_question VALUES (?,?,?,?,0)',
            (question_id, f'题目 {question_id}', 'plain', 'single_choice'),
        )
        self.connection.execute(
            'INSERT INTO qbank_v2_wrong_question_state '
            '(id,user_id,question_id,source_bank_item_id,entry_source,entry_metadata,status,deleted,'
            'wrong_count,correct_streak,first_wrong_time,last_wrong_time,last_practice_time,is_pinned,'
            'review_count,last_reviewed_time,practice_level,last_rating,next_practice_time,resolved_time,created_time) '
            'VALUES (?,?,?,?,?,?,?,?,1,0,?,?,NULL,0,?,?,0,NULL,NULL,?,?)',
            (
                state_id,
                user_id,
                question_id,
                item_id,
                source,
                json.dumps(metadata or {}),
                status,
                deleted,
                '2026-10-01 12:00:00',
                '2026-10-02 12:00:00',
                reviews,
                '2026-10-03 12:00:00' if reviews else None,
                '2026-10-04 12:00:00' if status == 'resolved' else None,
                '2026-10-01 12:00:00',
            ),
        )

    def _seed_cross_domain(self) -> None:
        self.connection.executescript("""
            INSERT INTO qbank_v2_bank VALUES (3);
            INSERT INTO qbank_v2_bank_revision VALUES (3,3,'考研试卷',0);
            INSERT INTO qbank_v2_bank_section VALUES (3,'考研高数',0);
            INSERT INTO qbank_v2_bank_category VALUES (3,3,1,0);
        """)
        # 301-304 属于考公题库(1400)，401-404 属于考研题库(1)。
        for item_id, revision_id, question_id, section_id in [
            (301, 1, 201, 1),
            (302, 1, 202, 1),
            (303, 1, 203, 1),
            (304, 1, 204, 2),
            (305, 1, 214, 1),
            (306, 1, 215, 1),
            (401, 3, 205, 3),
            (402, 3, 206, 3),
            (403, 3, 207, 3),
            (404, 3, 208, 3),
        ]:
            self.connection.execute(
                'INSERT INTO qbank_v2_bank_item VALUES (?,?,?,?,0)',
                (item_id, revision_id, question_id, section_id),
            )

        # 题库作答都不写 domain 键，仅可能带 section_name。
        self._add_state(101, question_id=201, item_id=301, metadata={})
        self._add_state(102, question_id=202, item_id=302, metadata={'section_name': '数量关系'})
        self._add_state(103, question_id=203, item_id=303, metadata={}, reviews=1)
        self._add_state(114, question_id=204, item_id=304, metadata={'section_name': '政治理论'}, status='resolved')
        self._add_state(104, question_id=205, item_id=401, metadata={})
        self._add_state(105, question_id=206, item_id=402, metadata={'section_name': '考研高数'})
        self._add_state(106, question_id=207, item_id=403, metadata={'section_name': '考研高数'}, reviews=1)
        self._add_state(115, question_id=208, item_id=404, metadata={}, status='resolved')
        # attempt 既无来源题库也无记录领域：不能作为「未记录领域」兜底放进任何领域。
        self._add_state(107, question_id=209, metadata={})

        # 自主录入：有记录领域按记录筛选；历史无领域保持兼容。
        self._add_state(
            108, question_id=210, source='manual', metadata={'source': '手动录入', 'domain_category_id': KAOGONG}
        )
        self._add_state(
            109, question_id=211, source='ocr', metadata={'source': 'OCR 录入', 'domain_category_id': KAOYAN}
        )
        self._add_state(110, question_id=212, source='import', metadata={'source': '历史导入'})
        self._add_state(111, question_id=213, source='manual', metadata={'source': '历史手动'})

        # 其他用户和已删除记录不能混入。
        self._add_state(112, question_id=214, item_id=305, metadata={}, user_id=7)
        self._add_state(113, question_id=215, item_id=306, metadata={}, deleted=1)


@pytest.fixture
def db() -> Iterator[CrossDomainBrowseDB]:
    database = CrossDomainBrowseDB()
    yield database
    database.connection.close()


async def _list_ids(
    db: CrossDomainBrowseDB,
    *,
    status: str = 'active',
    review_state: str | None = None,
    domain: list[int] | None = None,
    view: str = 'full',
    section_name: str | None = None,
) -> set[int]:
    rows = (
        await db.execute(
            wrong_question_state_dao.get_list_select(
                user_id=USER_ID,
                filters=WrongQuestionFilters(status=status, review_state=review_state),
                domain_category_ids=domain,
                view=view,
                section_name=section_name,
            )
        )
    ).all()
    return {int(row['id']) for row in rows}


@pytest.mark.parametrize(
    ('status', 'review_state', 'domain', 'expected'),
    [
        ('active', 'pending', [KAOGONG], KAOGONG_PENDING),
        ('active', 'pending', [KAOYAN], KAOYAN_PENDING),
        ('active', 'reviewed', [KAOGONG], {103}),
        ('active', 'reviewed', [KAOYAN], {106}),
        ('resolved', None, [KAOGONG], {114}),
        ('resolved', None, [KAOYAN], {115}),
    ],
)
async def test_pending_reviewed_mastered_views_exclude_other_domain(
    db: CrossDomainBrowseDB,
    status: str,
    review_state: str | None,
    domain: list[int],
    expected: set[int],
) -> None:
    for view in ('full', 'summary', 'outline'):
        assert await _list_ids(db, status=status, review_state=review_state, domain=domain, view=view) == expected
    # 无来源题库也无记录领域的 attempt 不能靠旧兜底条件混入。
    assert 107 not in expected


async def test_switching_domain_filters_in_reverse(db: CrossDomainBrowseDB) -> None:
    kaogong = await _list_ids(db, review_state='pending', domain=[KAOGONG])
    kaoyan = await _list_ids(db, review_state='pending', domain=[KAOYAN])
    assert kaogong == KAOGONG_PENDING
    assert kaoyan == KAOYAN_PENDING
    assert not ({104, 105} & kaogong)
    assert not ({101, 102} & kaoyan)
    assert 107 not in kaogong | kaoyan


@pytest.mark.parametrize(
    ('status', 'review_state', 'domain', 'expected_sections'),
    [
        ('active', 'pending', [KAOGONG], {'数量关系': 2, UNSECTIONED_SECTION_NAME: 3}),
        ('active', 'pending', [KAOYAN], {'考研高数': 2, UNSECTIONED_SECTION_NAME: 3}),
        ('active', 'reviewed', [KAOGONG], {'数量关系': 1}),
        ('active', 'reviewed', [KAOYAN], {'考研高数': 1}),
        ('resolved', None, [KAOGONG], {'政治理论': 1}),
        ('resolved', None, [KAOYAN], {'考研高数': 1}),
    ],
)
async def test_section_counts_match_scoped_question_list(
    db: CrossDomainBrowseDB,
    status: str,
    review_state: str | None,
    domain: list[int],
    expected_sections: dict[str, int],
) -> None:
    params = {
        'user_id': USER_ID,
        'filters': WrongQuestionFilters(status=status, review_state=review_state),
        'domain_category_ids': domain,
    }
    total, rows = await wrong_question_state_dao.get_section_counts(db, **params)
    assert total == sum(expected_sections.values())
    assert {row['section_name']: row['total'] for row in rows} == expected_sections
    for section_name, count in expected_sections.items():
        scoped = await _list_ids(
            db, status=status, review_state=review_state, domain=domain, section_name=section_name
        )
        assert len(scoped) == count


@pytest.mark.parametrize(
    ('domain', 'expected_bank', 'expected_total'),
    [([KAOGONG], {'1'}, 5), ([KAOYAN], {'3'}, 5)],
)
async def test_collection_counts_keep_questions_and_statistics_consistent(
    db: CrossDomainBrowseDB,
    domain: list[int],
    expected_bank: set[str],
    expected_total: int,
) -> None:
    collections = await wrong_question_state_dao.get_collection_counts(
        db, user_id=USER_ID, status='active', domain_category_ids=domain
    )
    banks = {row['collection_id'] for row in collections if row['collection_type'] == 'bank'}
    assert banks == expected_bank
    assert sum(row['pending'] for row in collections) == expected_total
    assert sum(row['reviewed'] for row in collections) == 1
    # 集合总量与列表口径一致：待复盘 5 + 已复盘 1。
    assert sum(row['total'] for row in collections) == 6
    single = next(row for row in collections if row['collection_type'] == 'single')
    assert single['total'] == 3


@pytest.mark.parametrize(('domain', 'expected_bank'), [([KAOGONG], {'1'}), ([KAOYAN], {'3'})])
async def test_mastered_collections_are_scoped(
    db: CrossDomainBrowseDB, domain: list[int], expected_bank: set[str]
) -> None:
    collections = await wrong_question_state_dao.get_collection_counts(
        db, user_id=USER_ID, status='resolved', domain_category_ids=domain
    )
    assert {row['collection_id'] for row in collections if row['collection_type'] == 'bank'} == expected_bank
    assert sum(row['total'] for row in collections) == 1
    assert sum(row['mastered'] for row in collections) == 1


async def test_collection_page_and_browse_total_stay_in_selected_domain(
    db: CrossDomainBrowseDB, monkeypatch: pytest.MonkeyPatch
) -> None:
    for domain, expected_bank in [([KAOGONG], {'1'}), ([KAOYAN], {'3'})]:
        monkeypatch.setattr(WrongReviewService, 'resolve_domain_scope', AsyncMock(return_value=domain))
        page = await WrongReviewService.get_collections_page(db=db, user_id=USER_ID, mode='pending', size=1)
        groups = list(page.items)
        assert page.total == 5
        while page.has_more:
            page = await WrongReviewService.get_collections_page(
                db=db, user_id=USER_ID, mode='pending', size=1, cursor=page.next_cursor
            )
            groups.extend(page.items)
            assert page.total == 5
        assert {group.collection_id for group in groups if group.collection_type == 'bank'} == expected_bank
        assert sum(group.pending for group in groups) == 5


@pytest.mark.parametrize('domain', [[KAOGONG], [KAOYAN]])
async def test_statistics_use_the_same_domain_scope_as_lists(
    db: CrossDomainBrowseDB, domain: list[int]
) -> None:
    statistics = await wrong_question_state_dao.get_statistics(
        db, user_id=USER_ID, now=datetime(2026, 10, 26, tzinfo=UTC), domain_category_ids=domain
    )
    assert statistics == {
        'total_count': 7,
        'active_count': 6,
        'resolved_count': 1,
        'wrong_occurrence_count': 7,
        'reviewed_count': 1,
        'active_reviewed_count': 1,
        'pending_review_count': 5,
        'due_count': 0,
    }
    assert statistics['pending_review_count'] == len(
        await _list_ids(db, review_state='pending', domain=domain)
    )
    assert statistics['active_reviewed_count'] == len(
        await _list_ids(db, review_state='reviewed', domain=domain)
    )
    assert statistics['resolved_count'] == len(
        await _list_ids(db, status='resolved', review_state=None, domain=domain)
    )


async def test_recorded_external_domains_and_legacy_entries(db: CrossDomainBrowseDB) -> None:
    kaogong = await _list_ids(db, review_state='pending', domain=[KAOGONG])
    kaoyan = await _list_ids(db, review_state='pending', domain=[KAOYAN])

    # 有记录领域的自主录入只属于对应领域。
    assert {108} <= kaogong
    assert 109 not in kaogong
    assert {109} <= kaoyan
    assert 108 not in kaoyan
    # 历史 manual/ocr/import 无领域的录入保持兼容，两边都能看到。
    assert {110, 111} <= kaogong
    assert {110, 111} <= kaoyan
    # attempt 无题库无领域不享受兼容。
    assert 107 not in kaogong | kaoyan


async def test_domain_none_does_not_filter_and_empty_subtree_matches_nothing(
    db: CrossDomainBrowseDB,
) -> None:
    unscoped = await _list_ids(db, review_state='pending', domain=None)
    assert unscoped == {101, 102, 104, 105, 107, 108, 109, 110, 111}
    # 其他用户与删除记录始终不混入。
    assert not ({112, 113} & unscoped)

    empty = await _list_ids(db, review_state='pending', domain=[])
    assert empty == set()
    assert await _list_ids(db, status='resolved', review_state=None, domain=[]) == set()

    statistics = await wrong_question_state_dao.get_statistics(
        db, user_id=USER_ID, now=datetime(2026, 10, 26, tzinfo=UTC), domain_category_ids=[]
    )
    assert set(statistics.values()) == {0}
    assert await wrong_question_state_dao.get_collection_counts(
        db, user_id=USER_ID, status='active', domain_category_ids=[]
    ) == []


def _legacy_domain_condition(
    domain_category_ids: Sequence[int],
    *,
    question_id_column: Any,
    metadata_column: Any,
    entry_source_column: Any,
) -> Any:
    """修复前的条件：任何未记录领域的记录都无条件放行。"""
    category_ids = list(domain_category_ids)
    bank_in_domain = (
        select(QbBankItem.id)
        .join(QbBankRevision, QbBankRevision.id == QbBankItem.bank_revision_id)
        .join(QbBank, QbBank.id == QbBankRevision.bank_id)
        .join(
            QbBankCategory,
            and_(
                QbBankCategory.bank_id == QbBank.id,
                QbBankCategory.deleted == 0,
            ),
        )
        .where(
            QbBankItem.deleted == 0,
            QbBankItem.question_id == question_id_column,
            QbBankCategory.category_id.in_(category_ids),
        )
    )
    recorded_domain = cast(metadata_column[ENTRY_METADATA_DOMAIN_KEY].as_string(), BigInteger)
    domain_unrecorded = metadata_column[ENTRY_METADATA_DOMAIN_KEY].as_string().is_(None)
    return or_(exists(bank_in_domain), recorded_domain.in_(category_ids), domain_unrecorded)


async def test_legacy_condition_leaks_other_domain_and_new_condition_restores(
    db: CrossDomainBrowseDB, monkeypatch: pytest.MonkeyPatch
) -> None:
    fresh = await _list_ids(db, review_state='pending', domain=[KAOGONG])
    assert fresh == KAOGONG_PENDING

    with monkeypatch.context() as patcher:
        patcher.setattr(
            CRUDWrongQuestionState,
            '_domain_condition',
            staticmethod(_legacy_domain_condition),
        )
        leaked = await _list_ids(db, review_state='pending', domain=[KAOGONG])

    # 旧条件在考公范围里放行了考研的 104/105 和无领域的 attempt 107。
    assert {104, 105, 107} <= leaked
    assert leaked != fresh
    assert await _list_ids(db, review_state='pending', domain=[KAOGONG]) == fresh
