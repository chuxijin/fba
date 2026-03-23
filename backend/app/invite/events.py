#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import secrets
import string

from sqlalchemy import event

from backend.app.admin.model.user import User
from backend.app.invite.model.invite_code import InviteCode
from backend.common.enums import PrimaryKeyType
from backend.common.log import log
from backend.core.conf import settings
from backend.utils.timezone import timezone

# 排除易混淆字符的字符集
_CHARSET = ''.join(c for c in string.ascii_uppercase + string.digits if c not in 'O0I1')


def _generate_code(length: int = 8) -> str:
    """生成邀请码"""
    return ''.join(secrets.choice(_CHARSET) for _ in range(length))


@event.listens_for(User, 'after_insert')
def auto_create_invite_code(mapper, connection, target) -> None:
    """
    用户创建后自动生成默认邀请码

    :param mapper: ORM 映射器
    :param connection: 当前数据库连接（同一事务）
    :param target: 刚插入的 User 实例
    :return:
    """
    values = {
        'user_id': target.id,
        'code': _generate_code(),
        'max_uses': 0,
        'used_count': 0,
        'status': 1,
        'created_time': timezone.now(),
    }

    # 雪花算法模式需要手动生成主键
    if settings.DATABASE_PK_MODE != PrimaryKeyType.autoincrement:
        from backend.utils.snowflake import snowflake

        values['id'] = snowflake.generate()

    try:
        connection.execute(InviteCode.__table__.insert().values(**values))
    except Exception as e:
        # 邀请码创建失败不应阻断用户注册
        log.warning(f'自动创建邀请码失败: user_id={target.id}, error={e}')
