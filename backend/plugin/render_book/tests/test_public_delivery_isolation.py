"""公开题本交付隔离单元测试：仅 mock DAO/微信/渲染，不触碰真实数据库。"""

import hashlib
import re
import time

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from sqlalchemy.dialects import postgresql

from backend.common.exception import errors
from backend.plugin.render_book.service import public_delivery_service as service
from backend.plugin.render_book.service.docx_engine import docx_render_engine
from backend.plugin.render_book.service.quota_service import render_book_quota_service

VALID_TOKEN = 'abc-DEF_0123456789xyzABC'
FUTURE = 3600


class FakeResult:
    def __init__(self, job: SimpleNamespace | None) -> None:
        self._job = job

    def scalars(self) -> 'FakeResult':
        return self

    def first(self) -> SimpleNamespace | None:
        return self._job


class FakeSession:
    """只记录执行语句并返回固定结果，绝不连接数据库。"""

    def __init__(self, job: SimpleNamespace | None) -> None:
        self.job = job
        self.statements: list = []
        self.flush = AsyncMock()

    async def execute(self, statement: object) -> FakeResult:
        self.statements.append(statement)
        return FakeResult(self.job)


def _job(*, user_id: int | None = None, expires_in: int = FUTURE, token: str = VALID_TOKEN) -> SimpleNamespace:
    return SimpleNamespace(
        user_id=user_id,
        job_id='job_001',
        title='测试题本',
        metadata_json={
            'delivery_hash': hashlib.sha256(token.encode()).hexdigest(),
            'delivery_expires_at': int(time.time()) + expires_in,
        },
    )


@pytest.mark.parametrize('token', [VALID_TOKEN, 'A' * 24, '_' * 24, '-' * 24, '0' * 24])
def test_delivery_digest_hashes_valid_token(token: str) -> None:
    digest = service.delivery_digest(token)

    assert digest == hashlib.sha256(token.encode()).hexdigest()
    assert re.fullmatch(r'[0-9a-f]{64}', digest)


@pytest.mark.parametrize(
    'token',
    ['', 'short', 'a' * 23, 'a' * 25, 'bad space token 12345678', 'abc$DEF0123456789xyzABCD'],
)
def test_delivery_digest_rejects_invalid_token(token: str) -> None:
    with pytest.raises(errors.NotFoundError, match='领取码无效'):
        service.delivery_digest(token)


@pytest.mark.asyncio
async def test_register_public_book_registers_existing_separated_docx(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    question_file = tmp_path / 'questions.docx'
    question_file.write_bytes(b'question-bytes')
    solution_file = tmp_path / 'solutions.docx'
    solution_file.write_bytes(b'solution-bytes')

    create_job = AsyncMock(return_value=SimpleNamespace(id=99))
    create_file = AsyncMock()
    monkeypatch.setattr(service.render_book_job_dao, 'create_job', create_job)
    monkeypatch.setattr(service.render_book_job_file_dao, 'create_file', create_file)

    before = int(time.time())
    token = await service.register_public_book(
        db=AsyncMock(),
        job_id='job_register_01',
        user_id=7,
        title='超长标题' * 60,
        question_count=3,
        is_mistake=True,
        answer_placement='separate',
        files=[(question_file, '试题册.docx'), (solution_file, '答案解析册.docx')],
    )

    assert re.fullmatch(r'[A-Za-z0-9_-]{24}', token)
    job_data = create_job.await_args.kwargs['data']
    assert job_data['job_id'] == 'job_register_01'
    assert job_data['user_id'] == 7
    assert len(job_data['title']) == 200
    assert job_data['template_key'] == 'gongkao_practice'
    assert job_data['book_kind'] == 'wrong'
    assert job_data['solution_mode'] == 'separate'
    assert job_data['metadata_json']['delivery_hash'] == hashlib.sha256(token.encode()).hexdigest()
    assert (
        before + service.DELIVERY_TTL
        <= job_data['metadata_json']['delivery_expires_at']
        <= before + service.DELIVERY_TTL + 5
    )

    assert create_file.await_count == 2
    first_data = create_file.await_args_list[0].kwargs['data']
    second_data = create_file.await_args_list[1].kwargs['data']
    assert (first_data['file_kind'], first_data['render_variant']) == ('question_pdf', 'questions_only')
    assert (second_data['file_kind'], second_data['render_variant']) == ('solution_pdf', 'solutions_only')
    assert first_data['filename'] == '试题册.docx'
    assert second_data['filename'] == '答案解析册.docx'
    assert first_data['local_path'] == str(question_file.resolve())
    assert second_data['local_path'] == str(solution_file.resolve())
    assert first_data['size_bytes'] == len(b'question-bytes')
    assert first_data['content_type'] == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'


@pytest.mark.asyncio
async def test_register_public_book_single_pdf_uses_combined_appendix(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    pdf_file = tmp_path / 'exam.pdf'
    pdf_file.write_bytes(b'%PDF-1.4')

    create_job = AsyncMock(return_value=SimpleNamespace(id=5))
    create_file = AsyncMock()
    monkeypatch.setattr(service.render_book_job_dao, 'create_job', create_job)
    monkeypatch.setattr(service.render_book_job_file_dao, 'create_file', create_file)

    await service.register_public_book(
        db=AsyncMock(),
        job_id='job_register_02',
        user_id=None,
        title='考点速记',
        question_count=10,
        is_mistake=False,
        answer_placement='merged',
        files=[(pdf_file, '考点速记.pdf')],
    )

    job_data = create_job.await_args.kwargs['data']
    file_data = create_file.await_args.kwargs['data']
    assert job_data['template_key'] == 'gongkao_xingce'
    assert job_data['book_kind'] == 'exam'
    assert job_data['solution_mode'] == 'appendix'
    assert (file_data['file_kind'], file_data['render_variant']) == ('combined_pdf', 'combined_appendix')
    assert file_data['content_type'] == 'application/pdf'


@pytest.mark.asyncio
async def test_register_public_book_missing_file_fails_before_file_record(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    create_job = AsyncMock(return_value=SimpleNamespace(id=3))
    create_file = AsyncMock()
    monkeypatch.setattr(service.render_book_job_dao, 'create_job', create_job)
    monkeypatch.setattr(service.render_book_job_file_dao, 'create_file', create_file)

    with pytest.raises(errors.ServerError, match='排版产物未生成'):
        await service.register_public_book(
            db=AsyncMock(),
            job_id='job_register_03',
            user_id=1,
            title='缺失产物',
            question_count=1,
            is_mistake=False,
            answer_placement='merged',
            files=[(tmp_path / 'missing.docx', 'missing.docx')],
        )

    create_file.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_delivery_job_applies_soft_delete_filter_and_row_lock() -> None:
    session = FakeSession(_job(user_id=7))

    await service.get_delivery_job(db=session, token=VALID_TOKEN, for_update=True)

    assert len(session.statements) == 1
    statement = session.statements[0]
    assert statement._for_update_arg is not None
    sql = str(statement.compile(dialect=postgresql.dialect()))
    assert 'FOR UPDATE' in sql
    assert 'del_flag' in sql
    assert 'false' in sql.lower()


@pytest.mark.asyncio
async def test_get_delivery_job_reads_without_lock_when_not_requested() -> None:
    session = FakeSession(_job())

    await service.get_delivery_job(db=session, token=VALID_TOKEN)

    assert session.statements[0]._for_update_arg is None


@pytest.mark.asyncio
async def test_get_delivery_job_rejects_expired_token() -> None:
    session = FakeSession(_job(expires_in=-1))

    with pytest.raises(errors.NotFoundError, match='已过期'):
        await service.get_delivery_job(db=session, token=VALID_TOKEN)


@pytest.mark.asyncio
async def test_get_delivery_job_rejects_soft_deleted_missing_row() -> None:
    session = FakeSession(None)

    with pytest.raises(errors.NotFoundError, match='已过期或题本已删除'):
        await service.get_delivery_job(db=session, token=VALID_TOKEN)


@pytest.mark.asyncio
async def test_get_delivery_job_rejects_malformed_token_before_query() -> None:
    session = FakeSession(_job())

    with pytest.raises(errors.NotFoundError, match='领取码无效'):
        await service.get_delivery_job(db=session, token='bad-token')

    assert session.statements == []


@pytest.mark.asyncio
async def test_receive_public_book_same_account_is_idempotent_without_render_or_quota(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job = _job(user_id=7)
    session = FakeSession(job)
    get_job = AsyncMock(return_value=job)
    create_job = AsyncMock()
    create_file = AsyncMock()
    consume = AsyncMock()
    ensure = AsyncMock()
    render_all = AsyncMock()

    monkeypatch.setattr(service, 'get_delivery_job', get_job)
    monkeypatch.setattr(service.render_book_job_dao, 'create_job', create_job)
    monkeypatch.setattr(service.render_book_job_file_dao, 'create_file', create_file)
    monkeypatch.setattr(render_book_quota_service, 'consume_quota', consume)
    monkeypatch.setattr(render_book_quota_service, 'ensure_quota', ensure)
    monkeypatch.setattr(docx_render_engine, 'render_all', render_all)

    result = await service.receive_public_book(db=session, token=VALID_TOKEN, user_id=7)

    assert result == {'job_id': 'job_001', 'title': '测试题本', 'cat_id': 1400}
    assert job.user_id == 7
    assert job.metadata_json['user_id'] == 7
    session.flush.assert_awaited_once()
    get_job.assert_awaited_once_with(db=session, token=VALID_TOKEN, for_update=True)
    create_job.assert_not_awaited()
    create_file.assert_not_awaited()
    consume.assert_not_awaited()
    ensure.assert_not_awaited()
    render_all.assert_not_awaited()


@pytest.mark.asyncio
async def test_receive_public_book_claims_unowned_job(monkeypatch: pytest.MonkeyPatch) -> None:
    job = _job(user_id=None)
    session = FakeSession(job)
    monkeypatch.setattr(service, 'get_delivery_job', AsyncMock(return_value=job))

    result = await service.receive_public_book(db=session, token=VALID_TOKEN, user_id=9)

    assert result['job_id'] == 'job_001'
    assert job.user_id == 9
    assert job.metadata_json['user_id'] == 9
    session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_receive_public_book_rejects_other_account(monkeypatch: pytest.MonkeyPatch) -> None:
    job = _job(user_id=8)
    session = FakeSession(job)
    monkeypatch.setattr(service, 'get_delivery_job', AsyncMock(return_value=job))

    with pytest.raises(errors.AuthorizationError, match='其他账号'):
        await service.receive_public_book(db=session, token=VALID_TOKEN, user_id=7)

    assert job.user_id == 8
    session.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_delivery_minicode_uses_mocked_wechat_gateway(monkeypatch: pytest.MonkeyPatch) -> None:
    job = _job(expires_in=500)
    create_code = AsyncMock(return_value='data:image/png;base64,abc')
    monkeypatch.setattr(service, 'get_delivery_job', AsyncMock(return_value=job))
    monkeypatch.setattr(service, 'create_miniapp_code', create_code)

    result = await service.delivery_minicode(db=FakeSession(job), token=VALID_TOKEN)

    assert result == 'data:image/png;base64,abc'
    kwargs = create_code.await_args.kwargs
    assert kwargs['page'] == service.DELIVERY_PAGE
    assert kwargs['scene'] == f'rb_{VALID_TOKEN}'
    assert 0 < kwargs['ttl'] <= 500
