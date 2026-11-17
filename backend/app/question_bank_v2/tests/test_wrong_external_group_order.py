"""自主录入来源组按实际录入时间排序，不按名称、作答日期或复盘时间。"""

import asyncio
import json
import sqlite3

from sqlalchemy.dialects import sqlite

from backend.app.question_bank_v2.crud.crud_review import wrong_question_state_dao
from backend.app.question_bank_v2.service.content_group_service import content_group_service
from backend.app.question_bank_v2.tests.test_wrong_domain_scope import _CapturingSession


def test_external_source_groups_order_by_latest_capture_not_title_or_wrong_time() -> None:
    db = _CapturingSession()
    asyncio.run(
        wrong_question_state_dao.get_group_counts(
            db, user_id=20, group_by='bank', knowledge_system_ids=[], domain_category_ids=None
        )
    )
    assert len(db.statements) == 2
    bank_sql = str(db.statements[0].compile(compile_kwargs={'literal_binds': True}))
    assert 'ORDER BY qbank_v2_bank_revision.name NULLS FIRST, qbank_v2_bank_section.name' in bank_sql
    # SQLite 不支持当前 SQLAlchemy 生成的双参数 DISTINCT group_concat；
    # 仅投影来源与计数，保留真实 WHERE / GROUP BY / ORDER BY 验证排序。
    external_stmt = db.statements[1].with_only_columns(*list(db.statements[1].selected_columns)[:2])
    external_sql = str(external_stmt.compile(dialect=sqlite.dialect(), compile_kwargs={'literal_binds': True}))
    with sqlite3.connect(':memory:') as connection:
        connection.row_factory = sqlite3.Row
        connection.execute(
            'CREATE TABLE qbank_v2_wrong_question_state ('
            'id INTEGER, user_id INTEGER, question_id INTEGER, status TEXT, deleted INTEGER, '
            'entry_source TEXT, entry_metadata TEXT, created_time TEXT, last_wrong_time TEXT, updated_time TEXT)'
        )
        rows = [
            # 名字最靠前、作答和复盘时间最新，但录入最旧，不能顶到上面。
            (1, 20, 101, 'active', 0, 'import', 'A旧组', '2026-01-01', '2026-12-01', '2026-12-02'),
            (2, 20, 102, 'active', 0, 'manual', 'Z新组', '2026-11-16', '2026-01-01', '2026-11-16'),
            (3, 20, 103, 'active', 0, 'ocr', '补充录入组', '2026-01-02', '2026-01-01', '2026-01-02'),
            (4, 20, 104, 'active', 0, 'ocr', '补充录入组', '2026-11-17', '2026-01-01', '2026-11-17'),
            # 录入时间相同则按记录 ID 倒序，重复请求也不会改变顺序。
            (5, 20, 105, 'active', 0, 'manual', '同日低ID组', '2026-11-16', None, '2026-11-16'),
            (6, 20, 106, 'active', 0, 'import', '同日高ID组', '2026-11-16', None, '2026-11-16'),
            (7, 20, 107, 'active', 0, 'manual', '', None, None, None),
            # 其他用户、删除和已掌握的数据不能影响活跃来源组的排序或计数。
            (8, 99, 108, 'active', 0, 'import', 'A旧组', '2027-01-01', None, None),
            (9, 20, 109, 'active', 1, 'import', 'A旧组', '2027-01-01', None, None),
            (10, 20, 110, 'resolved', 0, 'import', 'A旧组', '2027-01-01', None, None),
        ]
        connection.executemany(
            'INSERT INTO qbank_v2_wrong_question_state VALUES (?,?,?,?,?,?,?,?,?,?)',
            [(*row[:6], json.dumps({'source': row[6]}), *row[7:]) for row in rows],
        )
        groups = [dict(row) for row in connection.execute(external_sql).fetchall()]
    assert [row['external_source'] for row in groups] == [
        '补充录入组', '同日高ID组', '同日低ID组', 'Z新组', 'A旧组', '未填写来源',
    ]
    assert [row['count'] for row in groups] == [2, 1, 1, 1, 1, 1]


def test_bank_tree_preserves_external_group_order_and_question_ids() -> None:
    rows = [
        {'bank_id': None, 'external_source': 'Z最新组', 'count': 1, 'question_ids': [103]},
        {'bank_id': None, 'external_source': 'A旧组', 'count': 2, 'question_ids': [101, 102]},
    ]
    groups = asyncio.run(content_group_service.build_bank_tree(db=object(), rows=rows, ungrouped_name='自主录入'))
    assert len(groups) == 1
    assert groups[0].name == '自主录入'
    assert groups[0].count == 3
    assert [child.name for child in groups[0].children] == ['Z最新组', 'A旧组']
    assert [child.question_ids for child in groups[0].children] == [[103], [101, 102]]
