"""领域标签优先，题库归属只兼容未标注领域的旧题本。"""

import json

import pytest

from sqlalchemy import create_engine

from backend.plugin.render_book.crud.crud_job import render_book_job_dao
from backend.plugin.render_book.model import RenderBookJob


@pytest.mark.parametrize(
    'cat_id,kp_cat_id,expected',
    [
        (1, 10, {'gong', 'legacy'}),
        (2, 20, {'yan', 'legacy', 'kp_only', 'conflict'}),
        (3, 30, {'legacy'}),
    ],
)
def test_explicit_domain_wins_over_shared_bank(cat_id: int, kp_cat_id: int, expected: set[str]) -> None:
    engine = create_engine('sqlite://')
    with engine.connect() as db:
        db.exec_driver_sql(
            f'CREATE TABLE {RenderBookJob.__tablename__} '
            '(id INTEGER, job_id TEXT, user_id INTEGER, metadata JSON, created_time TEXT, del_flag BOOLEAN)'
        )
        records = [
            ('gong', {'cat_id': 1, 'kp_cat_id': 10, 'bank_id': 100}, 7, False),
            ('yan', {'cat_id': 2, 'kp_cat_id': 20, 'bank_id': 100}, 7, False),
            ('legacy', {'bank_id': 100}, 7, False),
            ('kp_only', {'kp_cat_id': 20, 'bank_id': 100}, 7, False),
            ('conflict', {'cat_id': 2, 'kp_cat_id': 10, 'bank_id': 100}, 7, False),
            ('unknown', {}, 7, False),
            ('other_user', {'cat_id': cat_id}, 8, False),
            ('deleted', {'cat_id': cat_id}, 7, True),
        ]
        db.exec_driver_sql(
            f'INSERT INTO {RenderBookJob.__tablename__} VALUES (?,?,?,?,?,?)',
            [
                (index, name, user_id, json.dumps(metadata), '2026-10-18', deleted)
                for index, (name, metadata, user_id, deleted) in enumerate(records)
            ],
        )
        statement = render_book_job_dao.build_list_stmt(
            user_id=7,
            cat_id=cat_id,
            kp_cat_id=kp_cat_id,
            bank_ids={100},
            with_files=False,
        ).with_only_columns(RenderBookJob.job_id)
        assert set(db.execute(statement).scalars().all()) == expected
    engine.dispose()
