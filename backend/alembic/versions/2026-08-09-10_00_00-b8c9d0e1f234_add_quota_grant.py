"""add quota grant

Revision ID: b8c9d0e1f234
Revises: f7a8b9c0d123
Create Date: 2026-08-09 10:00:00.000000

"""

import hashlib

from datetime import datetime, timedelta

import sqlalchemy as sa

from alembic import op
from sqlalchemy.dialects import postgresql

revision = 'b8c9d0e1f234'
down_revision = 'f7a8b9c0d123'
branch_labels = None
depends_on = None


def _build_cycle_key(cycle_type: str, now: datetime) -> str:
    """生成周期键(与 access/engine/cycle.py 保持一致, 此处内联以固化迁移)"""
    if cycle_type == 'daily':
        return now.strftime('%Y-%m-%d')
    if cycle_type == 'weekly':
        return now.strftime('%G-W%V')
    if cycle_type == 'monthly':
        return now.strftime('%Y-%m')
    if cycle_type == 'yearly':
        return now.strftime('%Y')
    return 'lifetime'


def _build_cycle_end(cycle_type: str, now: datetime) -> datetime | None:
    """计算周期结束时刻(与 access/engine/cycle.py 保持一致)"""
    if cycle_type == 'lifetime':
        return None

    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if cycle_type == 'daily':
        return day_start + timedelta(days=1)
    if cycle_type == 'weekly':
        return day_start + timedelta(days=8 - day_start.isoweekday())
    if cycle_type == 'monthly':
        if day_start.month == 12:
            return day_start.replace(year=day_start.year + 1, month=1, day=1)
        return day_start.replace(month=day_start.month + 1, day=1)
    if cycle_type == 'yearly':
        return day_start.replace(year=day_start.year + 1, month=1, day=1)
    return None


def _refill_idempotency_key(
    *,
    user_id: int,
    entitlement_code: str,
    scope_key: str,
    cycle_type: str,
    cycle_key: str,
) -> str:
    """周期补账幂等键

    必须与 LedgerService._build_refill_idempotency_key 完全一致, 否则迁移生成的
    额度包不会被运行时识别为"本周期已补账", 首次访问会再补一次导致额度翻倍。
    """
    raw_key = f'{user_id}:{entitlement_code}:{scope_key}:{cycle_type}:{cycle_key}'
    digest = hashlib.sha256(raw_key.encode('utf-8')).hexdigest()
    return f'quota_refill:{digest}'


def _backfill_current_cycle_balances() -> None:
    """将当前周期的存量余额迁移为初始额度包

    只迁移"当前周期"的余额: 旧模型按 cycle_key 分桶, 过往周期的余额在新旧模型下
    都已不可用, 迁移它们反而会凭空复活过期额度。
    """
    bind = op.get_bind()
    now = datetime.now().astimezone()

    rows = bind.execute(
        sa.text("""
            SELECT DISTINCT ON (user_id, entitlement_code, scope_key, cycle_key)
                   user_id, entitlement_code, scope_key, cycle_key, cycle_type, balance_after
            FROM quota_ledger
            ORDER BY user_id, entitlement_code, scope_key, cycle_key, occurred_at DESC, id DESC
        """)
    ).fetchall()

    payload = []
    for row in rows:
        balance = int(row.balance_after or 0)
        if balance <= 0:
            continue

        cycle_type = str(row.cycle_type or 'monthly')
        if row.cycle_key != _build_cycle_key(cycle_type, now):
            continue

        payload.append({
            'user_id': int(row.user_id),
            'entitlement_code': str(row.entitlement_code),
            'granted_amount': balance,
            'remaining_amount': balance,
            'source': 'migration',
            'scope_key': str(row.scope_key or 'global'),
            'effective_at': now,
            'expires_at': _build_cycle_end(cycle_type, now),
            'priority': 0,
            'cycle_type': cycle_type,
            'cycle_key': str(row.cycle_key),
            'source_ref': f'{cycle_type}:{row.cycle_key}',
            'idempotency_key': _refill_idempotency_key(
                user_id=int(row.user_id),
                entitlement_code=str(row.entitlement_code),
                scope_key=str(row.scope_key or 'global'),
                cycle_type=cycle_type,
                cycle_key=str(row.cycle_key),
            ),
            'reason': 'migrate legacy cycle balance',
            'status': 'active',
            'created_time': now,
            'updated_time': now,
            'deleted': 0,
        })

    if not payload:
        return

    bind.execute(
        sa.text("""
            INSERT INTO quota_grant (
                user_id, entitlement_code, granted_amount, remaining_amount, source,
                scope_key, effective_at, expires_at, priority, cycle_type, cycle_key,
                source_ref, idempotency_key, reason, status, created_time, updated_time, deleted
            ) VALUES (
                :user_id, :entitlement_code, :granted_amount, :remaining_amount, :source,
                :scope_key, :effective_at, :expires_at, :priority, :cycle_type, :cycle_key,
                :source_ref, :idempotency_key, :reason, CAST(:status AS common_status),
                :created_time, :updated_time, :deleted
            )
            ON CONFLICT (idempotency_key) DO NOTHING
        """),
        payload,
    )


def upgrade() -> None:
    """新增额度包表, 并把配额余额的真相源从账本迁移到额度包。"""
    op.create_table(
        'quota_grant',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False, comment='主键 ID'),
        sa.Column('user_id', sa.BigInteger(), nullable=False, comment='用户 ID'),
        sa.Column('entitlement_code', sa.String(length=64), nullable=False, comment='权益编码'),
        sa.Column('granted_amount', sa.Integer(), nullable=False, comment='发放总量'),
        sa.Column('remaining_amount', sa.Integer(), nullable=False, comment='剩余可用量'),
        sa.Column('source', sa.String(length=32), nullable=False, comment='额度来源'),
        sa.Column(
            'scope_key',
            sa.String(length=64),
            server_default='global',
            nullable=False,
            comment='业务范围键',
        ),
        sa.Column('effective_at', sa.DateTime(timezone=True), nullable=False, comment='生效时间'),
        sa.Column(
            'expires_at',
            sa.DateTime(timezone=True),
            nullable=True,
            comment='过期时间, NULL 表示永不过期',
        ),
        sa.Column(
            'priority',
            sa.Integer(),
            server_default='0',
            nullable=False,
            comment='扣减优先级(同过期时间时越大越先扣)',
        ),
        sa.Column('cycle_type', sa.String(length=16), nullable=True, comment='来源周期类型'),
        sa.Column('cycle_key', sa.String(length=32), nullable=True, comment='来源周期键'),
        sa.Column('source_ref', sa.String(length=128), nullable=True, comment='来源引用'),
        sa.Column('idempotency_key', sa.String(length=128), nullable=True, comment='幂等键'),
        sa.Column('reason', sa.String(length=256), nullable=True, comment='发放原因'),
        sa.Column(
            'status',
            postgresql.ENUM('active', 'archived', 'draft', name='common_status', create_type=False),
            server_default='active',
            nullable=False,
            comment='状态',
        ),
        sa.Column('created_time', sa.DateTime(timezone=True), nullable=False, comment='创建时间'),
        sa.Column('updated_time', sa.DateTime(timezone=True), nullable=True, comment='更新时间'),
        sa.Column(
            'deleted',
            sa.BigInteger(),
            server_default='0',
            nullable=False,
            comment='是否已删除（0：否；id：是）',
        ),
        sa.Column('deleted_time', sa.DateTime(timezone=True), nullable=True, comment='删除时间'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('idempotency_key', name='uq_quota_grant_idempotency_key'),
        comment='配额额度包(配额余额的唯一真相源)',
    )
    op.create_index('ix_quota_grant_id', 'quota_grant', ['id'], unique=True)
    op.create_index(
        'idx_quota_grant_lookup',
        'quota_grant',
        ['user_id', 'entitlement_code', 'scope_key', 'status'],
    )
    op.create_index('idx_quota_grant_expires', 'quota_grant', ['expires_at'])

    op.add_column(
        'quota_ledger',
        sa.Column(
            'grant_breakdown',
            postgresql.JSONB(astext_type=sa.Text()),
            server_default='[]',
            nullable=False,
            comment='本次操作命中的额度包明细 [{"grant_id": .., "amount": ..}]',
        ),
    )

    _backfill_current_cycle_balances()


def downgrade() -> None:
    """回退到账本余额模型。"""
    op.drop_column('quota_ledger', 'grant_breakdown')
    op.drop_index('idx_quota_grant_expires', table_name='quota_grant')
    op.drop_index('idx_quota_grant_lookup', table_name='quota_grant')
    op.drop_index('ix_quota_grant_id', table_name='quota_grant')
    op.drop_table('quota_grant')
