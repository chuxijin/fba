import pickle

from types import SimpleNamespace

import pytest

from celery import Celery, states
from celery.result import AsyncResult, GroupResult
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from sqlalchemy.types import PickleType

from backend.app.task.database import DatabaseBackend
from backend.app.task.model.result import Task, TaskSet
from backend.core.conf import settings


@pytest.fixture
def backend(tmp_path):
    url = f'sqlite:///{tmp_path / "results.db"}'
    app = Celery('deployment-test', broker='memory://')
    app.conf.update(result_serializer='json', result_extended=True, database_create_tables_at_setup=False)
    instance = DatabaseBackend(app=app, url=url)
    engine = create_engine(url)
    Task.__table__.create(engine)
    TaskSet.__table__.create(engine)
    yield instance, engine
    engine.dispose()


@pytest.mark.parametrize('value', [{'answer': 7}, ('tuple', 2), None])
def test_new_result_is_readable_by_old_pickle_orm_and_new_backend(backend, monkeypatch, value):
    instance, engine = backend
    monkeypatch.setattr(settings, 'CELERY_RESULT_LEGACY_PICKLE_WRITE', True)
    instance.store_result('new-result', value, states.SUCCESS)
    with engine.connect() as conn:
        raw = conn.scalar(text('SELECT result FROM task_result'))
    old_orm_decode = PickleType().result_processor(engine.dialect, None)
    assert old_orm_decode(raw) == value
    assert instance._get_task_meta_for('new-result')['result'] == value


def test_legacy_and_modern_result_rows_are_readable(backend, monkeypatch):
    instance, engine = backend
    with engine.begin() as conn:
        conn.execute(text('INSERT INTO task_result(task_id,status,result) VALUES (:id,:status,:result)'), {
            'id': 'legacy', 'status': states.SUCCESS, 'result': pickle.dumps({'legacy': 1}, protocol=4),
        })
    assert instance._get_task_meta_for('legacy')['result'] == {'legacy': 1}
    monkeypatch.setattr(settings, 'CELERY_RESULT_LEGACY_PICKLE_WRITE', False)
    instance.store_result('modern', {'modern': 2}, states.SUCCESS)
    assert instance._get_task_meta_for('modern')['result'] == {'modern': 2}
    with engine.connect() as conn:
        assert not conn.scalar(text("SELECT result FROM task_result WHERE task_id='modern'")).startswith(b'\x80')


def test_group_storage_remains_readable_on_rollback(backend, monkeypatch):
    instance, engine = backend
    monkeypatch.setattr(settings, 'CELERY_RESULT_LEGACY_PICKLE_WRITE', True)
    result = GroupResult('group', [AsyncResult('child', app=instance.app)], app=instance.app).as_tuple()
    instance._save_group('group', result)
    with engine.connect() as conn:
        raw = conn.scalar(text('SELECT result FROM task_set_result'))
    assert PickleType().result_processor(engine.dialect, None)(raw) == instance.prepare_value(result)
    assert instance._restore_group('group')['result'].id == 'group'


def test_missing_optional_columns_fallback_does_not_lazy_query_or_abort_session(backend):
    instance, engine = backend
    with engine.begin() as conn:
        conn.execute(text('ALTER TABLE task_result DROP COLUMN children'))
        conn.execute(text('ALTER TABLE task_result DROP COLUMN stamps'))
        conn.execute(text("INSERT INTO task_result(task_id,status) VALUES ('old-table','SUCCESS')"))
    with Session(engine) as session:
        row = instance._query_task(session, 'old-table')
        assert row.to_dict()['children'] is None
        assert row.to_dict()['stamps'] is None
        assert session.scalar(text('SELECT 1')) == 1


def test_group_legacy_pickle_row_is_readable(backend):
    instance, engine = backend
    result = GroupResult('legacy-group', [AsyncResult('child', app=instance.app)], app=instance.app).as_tuple()
    with engine.begin() as conn:
        conn.execute(text('INSERT INTO task_set_result(taskset_id,result) VALUES (:id,:result)'), {
            'id': 'legacy-group', 'result': pickle.dumps(result, protocol=4),
        })
    assert instance._restore_group('legacy-group')['result'].id == 'legacy-group'


def test_legacy_rollout_reads_do_not_emit_serializer_warnings(backend, monkeypatch, caplog):
    instance, _ = backend
    monkeypatch.setattr(settings, 'CELERY_RESULT_LEGACY_PICKLE_WRITE', True)
    instance.store_result('quiet-result', {'answer': 7}, states.SUCCESS)
    assert instance._get_task_meta_for('quiet-result')['result'] == {'answer': 7}
    assert not [record for record in caplog.records if record.name == 'backend.app.task.database']


def test_failure_and_extended_metadata_are_rollback_readable(backend, monkeypatch):
    instance, engine = backend
    monkeypatch.setattr(settings, 'CELERY_RESULT_LEGACY_PICKLE_WRITE', True)
    request = SimpleNamespace(
        task='dummy.task', args=[7], kwargs={'dummy': True}, hostname='dummy-worker',
        retries=0, delivery_info={'routing_key': 'dummy'}, children=[], stamps=None,
    )
    instance.store_result('failure', ValueError('dummy failure'), states.FAILURE, request=request)
    meta = instance._get_task_meta_for('failure')
    assert isinstance(meta['result'], ValueError)
    assert str(meta['result']) == 'dummy failure'
    assert meta['args'] == [7]
    assert meta['kwargs'] == {'dummy': True}
    with engine.connect() as conn:
        raw = conn.scalar(text("SELECT result FROM task_result WHERE task_id='failure'"))
    assert PickleType().result_processor(engine.dialect, None)(raw)['exc_type'] == 'ValueError'
