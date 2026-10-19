"""邀请头像查询使用左连接，分页数据不因缺少用户或头像而丢失。"""

import asyncio

from datetime import datetime, timezone

from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine

from backend.app.invite.crud.crud_invite import invite_relation_dao
from backend.app.invite.model import InviteRelation
from backend.app.invite.schema.invite import GetInviteRelationDetail


def test_relation_query_preserves_records_and_returns_only_the_invitee_avatar() -> None:
    metadata = MetaData()
    relations = Table(
        'invite_relation',
        metadata,
        *(Column(column.name, column.type) for column in InviteRelation.__table__.columns),
    )
    users = Table('sys_user', metadata, Column('id', Integer), Column('avatar', String))
    engine = create_engine('sqlite://')
    try:
        metadata.create_all(engine)
        with engine.begin() as connection:
            connection.execute(
                users.insert(),
                [
                    {'id': 7, 'avatar': 'https://example.invalid/inviter.png'},
                    {'id': 8, 'avatar': 'https://example.invalid/friend.png'},
                    {'id': 9, 'avatar': None},
                ],
            )
            connection.execute(
                relations.insert(),
                [
                    {
                        'id': index,
                        'invite_code_id': 1,
                        'inviter_user_id': inviter,
                        'invitee_user_id': invitee,
                        'inviter_reward_status': 1,
                        'invitee_reward_status': 0,
                        'created_time': datetime(2026, 10, 17, tzinfo=timezone.utc),
                    }
                    for index, inviter, invitee in [(1, 7, 8), (2, 7, 9), (3, 7, 10), (4, 8, 7)]
                ],
            )
            statement = asyncio.run(invite_relation_dao.get_select(inviter_user_id=7))
            records = [GetInviteRelationDetail.model_validate(row._mapping) for row in connection.execute(statement)]
            assert [record.id for record in records] == [3, 2, 1]
            assert [record.invitee_avatar for record in records] == [None, None, 'https://example.invalid/friend.png']
            assert all(record.inviter_reward_status == 1 and record.invitee_reward_status == 0 for record in records)
            statement = asyncio.run(invite_relation_dao.get_select(inviter_user_id=7, invitee_user_id=8))
            assert [row.id for row in connection.execute(statement)] == [1]
    finally:
        engine.dispose()
