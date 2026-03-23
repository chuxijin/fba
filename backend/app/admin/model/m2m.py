#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sqlalchemy as sa

from backend.common.model import MappedBase, TimeZone

# 用户角色表（含有效期字段）
user_role = sa.Table(
    'sys_user_role',
    MappedBase.metadata,
    sa.Column('id', sa.BigInteger, primary_key=True, unique=True, index=True, autoincrement=True, comment='主键 ID'),
    sa.Column('user_id', sa.BigInteger, primary_key=True, comment='用户 ID'),
    sa.Column('role_id', sa.BigInteger, primary_key=True, comment='角色 ID'),
    sa.Column('valid_from', TimeZone, nullable=True, comment='有效期开始'),
    sa.Column('valid_to', TimeZone, nullable=True, comment='有效期结束'),
    sa.Column(
        'status',
        sa.Integer,
        nullable=False,
        server_default=sa.text('1'),
        comment='状态(0禁用 1正常 2过期)',
    ),
)

# 角色菜单表
role_menu = sa.Table(
    'sys_role_menu',
    MappedBase.metadata,
    sa.Column('id', sa.BigInteger, primary_key=True, unique=True, index=True, autoincrement=True, comment='主键 ID'),
    sa.Column('role_id', sa.BigInteger, primary_key=True, comment='角色 ID'),
    sa.Column('menu_id', sa.BigInteger, primary_key=True, comment='菜单 ID'),
)

# 角色数据范围表
role_data_scope = sa.Table(
    'sys_role_data_scope',
    MappedBase.metadata,
    sa.Column('id', sa.BigInteger, primary_key=True, unique=True, index=True, autoincrement=True, comment='主键 ID'),
    sa.Column('role_id', sa.BigInteger, primary_key=True, comment='角色 ID'),
    sa.Column('data_scope_id', sa.BigInteger, primary_key=True, comment='数据范围 ID'),
)

# 数据范围规则表
data_scope_rule = sa.Table(
    'sys_data_scope_rule',
    MappedBase.metadata,
    sa.Column('id', sa.BigInteger, primary_key=True, unique=True, index=True, autoincrement=True, comment='主键 ID'),
    sa.Column('data_scope_id', sa.BigInteger, primary_key=True, comment='数据范围 ID'),
    sa.Column('data_rule_id', sa.BigInteger, primary_key=True, comment='数据规则 ID'),
)
