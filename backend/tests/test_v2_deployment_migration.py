import importlib.util

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from alembic.script import ScriptDirectory


def migration():
    path = Path(__file__).parents[1] / 'alembic/versions/2026-11-13-23_30_00-c5d6e7f8a9b0_upstream_v2_deployment.py'
    spec = importlib.util.spec_from_file_location('v2_deployment_migration', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_revision_extends_production_head_without_another_branch():
    script = ScriptDirectory(str(Path(__file__).parents[1] / 'alembic'))
    assert script.get_heads() == ['c5d6e7f8a9b0']
    assert script.get_revision('c5d6e7f8a9b0').down_revision == 'b4c5d6e7f8a9'


@pytest.mark.parametrize('direction', ['upgrade', 'downgrade'])
def test_migration_is_transactional_postgresql_with_bounded_lock_wait(monkeypatch, direction):
    module = migration()
    fake = SimpleNamespace(get_bind=lambda: SimpleNamespace(dialect=SimpleNamespace(name='postgresql')), execute=Mock())
    monkeypatch.setattr(module, 'op', fake)
    getattr(module, direction)()
    assert fake.execute.call_args_list[0].args == ("SET LOCAL lock_timeout = '5s'",)
    assert fake.execute.call_args_list[1].args == ("SET LOCAL statement_timeout = '5min'",)
    assert fake.execute.call_args_list[2].args == (getattr(module, direction.upper() + '_SQL'),)


def test_non_postgresql_stops_without_writing(monkeypatch):
    module = migration()
    fake = SimpleNamespace(get_bind=lambda: SimpleNamespace(dialect=SimpleNamespace(name='sqlite')), execute=Mock())
    monkeypatch.setattr(module, 'op', fake)
    with pytest.raises(RuntimeError, match='PostgreSQL'):
        module.upgrade()
    fake.execute.assert_not_called()
