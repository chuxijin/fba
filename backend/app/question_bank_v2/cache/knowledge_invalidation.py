import asyncio

from typing import Any

from sqlalchemy import event
from sqlalchemy.orm import Session

from backend.app.question_bank_v2.cache.public_knowledge_cache import public_knowledge_cache
from backend.common.log import log

TABLES = frozenset({
    'qbank_v2_knowledge_system',
    'qbank_v2_knowledge_point',
    'qbank_v2_question_knowledge_point',
    'qbank_v2_bank_item',
    'qbank_v2_bank_revision',
})
PENDING = 'qbank_public_knowledge_invalidations'
tasks: set[asyncio.Task[None]] = set()


def mark_knowledge_changed(session: Session) -> None:
    """记录所属事务；保存点回滚不能导致误失效，批量写入只失效一次。"""
    transaction = session.get_nested_transaction() or session.get_transaction() or session.begin()
    if transaction is not None:
        session.info.setdefault(PENDING, set()).add(transaction)


@event.listens_for(Session, 'before_flush')
def track_knowledge_flush(session: Session, _context: Any, _instances: Any) -> None:
    for obj in (*session.new, *session.dirty, *session.deleted):
        table = getattr(obj, '__table__', None)
        if table is not None and table.name in TABLES:
            mark_knowledge_changed(session)
            break


@event.listens_for(Session, 'do_orm_execute')
def track_knowledge_statement(state: Any) -> None:
    if state.is_insert or state.is_update or state.is_delete:
        table = getattr(state.statement, 'table', None)
        if table is not None and table.name in TABLES:
            mark_knowledge_changed(state.session)


@event.listens_for(Session, 'after_commit')
def invalidate_committed_knowledge(session: Session) -> None:
    pending = session.info.get(PENDING, set())
    transaction = session.get_nested_transaction() or session.get_transaction()
    if transaction not in pending:
        return
    pending.remove(transaction)
    if session.get_nested_transaction() is not None:
        pending.add(transaction.parent)
        return
    session.info.pop(PENDING, None)
    try:
        task = asyncio.get_running_loop().create_task(public_knowledge_cache.invalidate())
    except RuntimeError:
        # 仅同步离线脚本走这里；正常 API 和异步导入均有事件循环。
        asyncio.run(public_knowledge_cache.invalidate())
        return
    tasks.add(task)

    def done(completed: asyncio.Task[None]) -> None:
        tasks.discard(completed)
        if not completed.cancelled() and completed.exception() is not None:
            log.warning(f'[KnowledgeCache] 提交后失效失败: {completed.exception()}')

    task.add_done_callback(done)


@event.listens_for(Session, 'after_soft_rollback')
def discard_rolled_back_knowledge(session: Session, previous_transaction: Any) -> None:
    pending = session.info.get(PENDING, set())
    pending.discard(previous_transaction)
    if not session.in_transaction():
        session.info.pop(PENDING, None)


@event.listens_for(Session, 'after_transaction_end')
def discard_ended_knowledge(session: Session, transaction: Any) -> None:
    """Session.close 同样清除未提交标记，避免复用会话后误失效。"""
    session.info.get(PENDING, set()).discard(transaction)
    if transaction.parent is None:
        session.info.pop(PENDING, None)
