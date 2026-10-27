from collections.abc import Iterator
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest

from backend.app.question_bank_v2.crud.crud_review import wrong_question_state_dao
from backend.app.question_bank_v2.service import wrong_review_service as review_module
from backend.app.question_bank_v2.service.wrong_review_service import WrongReviewService
from backend.app.question_bank_v2.tests.test_wrong_browse import BrowseDB
from backend.utils.timezone import timezone


class DashboardDB(BrowseDB):
    """执行真实层级汇总和下钻查询，复用错题浏览的内存数据。"""

    def __init__(self) -> None:
        super().__init__()
        self.connection.executescript("""
            CREATE TABLE qbank_v2_knowledge_system (id INTEGER, name TEXT, status TEXT, deleted INTEGER);
            CREATE TABLE qbank_v2_knowledge_point (
                id INTEGER, system_id INTEGER, name TEXT, parent_id INTEGER,
                sort_order INTEGER, path TEXT, deleted INTEGER
            );
            CREATE TABLE qbank_v2_question_review (
                id INTEGER, user_id INTEGER, wrong_state_id INTEGER, question_id INTEGER,
                event_type TEXT, reviewed_time TEXT, deleted INTEGER
            );
            CREATE TABLE qbank_v2_question_review_knowledge_point (
                id INTEGER, review_id INTEGER, knowledge_point_id INTEGER, deleted INTEGER
            );
            CREATE TABLE qbank_v2_question_review_tag (id INTEGER, review_id INTEGER, tag_id INTEGER, deleted INTEGER);
            CREATE TABLE qbank_v2_review_tag (id INTEGER, name TEXT, color TEXT, deleted INTEGER);
            INSERT INTO qbank_v2_knowledge_system VALUES (2,'行测','active',0), (3,'其他版本','active',0);
            INSERT INTO qbank_v2_knowledge_point VALUES
                (1,2,'行测',NULL,0,'/1/',0),
                (2,2,'政治理论',1,0,'/1/2/',0),
                (3,2,'常识判断',1,1,'/1/3/',0),
                (4,2,'言语理解',1,2,'/1/4/',0),
                (5,2,'数量关系',1,3,'/1/5/',0),
                (6,2,'判断推理',1,4,'/1/6/',0),
                (7,2,'资料分析',1,5,'/1/7/',0),
                (8,2,'图形推理',6,0,'/1/6/8/',0),
                (11,2,'逻辑判断',6,1,'/1/6/11/',0),
                (88,2,'位置规律',8,0,'1.6.8.88',0),
                (90,2,'已删除考点',6,2,'/1/6/90/',90),
                (300,3,'其他版本考点',NULL,0,'/300/',0);
        """)
        reviews = [
            (100, 7, 3, 103, 'review', '2026-10-25 12:00:00', 0),
            (101, 7, 4, 104, 'review', '2026-10-24 12:00:00', 0),
            (102, 7, 2, 102, 'review', '2026-10-23 12:00:00', 0),
            (103, 7, 1, 101, 'review', '2026-09-01 12:00:00', 0),
            (104, 8, 13, 113, 'review', '2026-10-25 12:00:00', 0),
            (105, 7, 7, 107, 'review', '2026-10-25 12:00:00', 105),
            (106, 7, 1, 101, 'capture', '2026-10-25 12:00:00', 0),
            (107, 7, 10, 110, 'review', '2026-10-25 12:00:00', 0),
            (108, 7, 9, 109, 'review', '2026-10-25 12:00:00', 0),
            (109, 7, 12, 112, 'review', '2026-10-25 12:00:00', 0),
        ]
        self.connection.executemany('INSERT INTO qbank_v2_question_review VALUES (?,?,?,?,?,?,?)', reviews)
        links = [(100, 6), (100, 8), (100, 88), (100, 300), (101, 11), (101, 90), (102, 7), (103, 5)]
        links.extend((review_id, 88) for review_id in range(104, 110))
        self.connection.executemany(
            'INSERT INTO qbank_v2_question_review_knowledge_point VALUES (?,?,?,0)',
            [(index, review_id, point_id) for index, (review_id, point_id) in enumerate(links, 1)],
        )
        self.connection.execute('INSERT INTO qbank_v2_question_review_knowledge_point VALUES (99,101,6,99)')


@pytest.fixture
def dashboard_db() -> Iterator[DashboardDB]:
    db = DashboardDB()
    yield db
    db.connection.close()


async def dashboard_rows(db: DashboardDB) -> tuple[int, list[dict[str, Any]], list[dict[str, Any]]]:
    return await wrong_question_state_dao.get_dashboard_rows(
        db,
        user_id=7,
        since=datetime(2026, 9, 26, tzinfo=timezone.tz_info),
        knowledge_system_ids=[2],
        domain_category_ids=[1400],
    )


async def test_dashboard_rolls_up_real_parent_chain_and_deduplicates_same_event(dashboard_db: DashboardDB) -> None:
    """同次复盘同时选父、子、孙只给祖先增加一次，旧记录和其他账号不混入。"""
    event_count, reasons, rows = await dashboard_rows(dashboard_db)
    assert event_count == 3
    assert reasons == []
    assert {row['id']: row['count'] for row in rows} == {1: 3, 6: 2, 7: 1, 8: 1, 11: 1, 88: 1}
    modules = WrongReviewService._build_knowledge_distribution(rows)
    assert [(item.name, item.count) for item in modules] == [('判断推理', 2), ('资料分析', 1)]
    assert [(item.name, item.count) for item in modules[0].children] == [('图形推理', 1), ('逻辑判断', 1)]
    assert modules[0].children[0].children[0].name == '位置规律'
    assert modules[1].children == []
    assert all(item.name not in {'行测', '图形推理', '位置规律'} for item in modules)


async def test_dashboard_keeps_long_tail_points_before_rollup(dashboard_db: DashboardDB) -> None:
    """不能先截取前20个细分考点再汇总，否则大模块统计会丢失长尾。"""
    for index in range(25):
        point_id = 400 + index
        dashboard_db.connection.execute(
            'INSERT INTO qbank_v2_knowledge_point VALUES (?,?,?,8,?,?,0)',
            (point_id, 2, f'细分考点 {index}', index + 1, f'/1/6/8/{point_id}/'),
        )
        dashboard_db.connection.execute(
            'INSERT INTO qbank_v2_question_review_knowledge_point VALUES (?,102,?,0)', (400 + index, point_id)
        )
    _, _, rows = await dashboard_rows(dashboard_db)
    modules = WrongReviewService._build_knowledge_distribution(rows)
    judgement = next(item for item in modules if item.id == 6)
    figures = next(item for item in judgement.children if item.id == 8)
    assert judgement.count == 3
    assert figures.count == 2
    assert len(figures.children) == 26
    assert all(item.count > 0 for item in figures.children)


@pytest.mark.parametrize(
    ('point_id', 'expected'), [(1, {2, 3, 4}), (6, {3, 4}), (8, {3}), (88, {3}), (999, set()), (90, set())]
)
async def test_reviewed_filter_contains_descendants_in_same_system(
    dashboard_db: DashboardDB, point_id: int, expected: set[int]
) -> None:
    """父模块包含所有子孙，点选考点可直接背题；已删、其他账号和领域不能命中。"""
    stmt = wrong_question_state_dao.get_reviewed_list_select(
        user_id=7,
        mastery_state=None,
        tag_id=None,
        knowledge_point_id=point_id,
        domain_category_ids=[1400],
    )
    assert {row['id'] for row in (await dashboard_db.execute(stmt)).all()} == expected


def test_native_module_root_is_not_unwrapped_when_only_one_module_has_records() -> None:
    modules = WrongReviewService._build_knowledge_distribution([
        {'id': 6, 'name': '判断推理', 'count': 2, 'parent_id': None, 'system_name': '判断推理'},
        {'id': 8, 'name': '图形推理', 'count': 2, 'parent_id': 6},
        {'id': 9, 'name': '定义判断', 'count': 0, 'parent_id': 6},
    ])
    assert [item.name for item in modules] == ['判断推理']
    assert [item.name for item in modules[0].children] == ['图形推理']
    assert modules[0].model_dump()['children'][0]['count'] == 2


async def test_dashboard_service_exposes_tree_with_same_domain_and_30_day_window(
    dashboard_db: DashboardDB, monkeypatch: pytest.MonkeyPatch
) -> None:
    now = datetime(2026, 10, 26, 12, tzinfo=timezone.tz_info)
    monkeypatch.setattr(review_module.timezone, 'now', lambda: now)
    monkeypatch.setattr(review_module.knowledge_service, 'resolve_domain_category_id', AsyncMock(return_value=1400))
    monkeypatch.setattr(review_module.knowledge_service, 'resolve_system_ids', AsyncMock(return_value=[2]))
    monkeypatch.setattr(WrongReviewService, 'get_domain_category_ids', AsyncMock(return_value=[1400]))
    result = await WrongReviewService.get_dashboard(db=dashboard_db, user_id=7)
    assert result.review_event_count == 3
    assert [item.name for item in result.knowledge_point_distribution] == ['判断推理', '资料分析']
    assert result.knowledge_point_distribution[0].children[0].children[0].id == 88
