#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from backend.app.mydrive.service.relationship_service import MyDriveRelationshipService


def test_serialize_friend_shares_builds_mount_references() -> None:
    """好友分享消息应转换为可挂载关系空间定位信息。"""
    shares = MyDriveRelationshipService._serialize_shares(
        [
            {
                'msg_id': 'message-1',
                'from_uk': 'friend-1',
                'filelist': {
                    'list': [
                        {'fs_id': 'root-1', 'server_filename': '课程资料', 'isdir': 1, 'size': 0},
                    ]
                },
            }
        ],
        'friend-1',
        'friend',
    )

    assert shares == [
        {
            'source_id': 'friend-1',
            'from_uk': 'friend-1',
            'message_id': 'message-1',
            'root_id': 'root-1',
            'name': '课程资料',
            'is_directory': True,
            'size': 0,
            'extra': {'space_type': 'friend'},
        }
    ]


def test_serialize_group_shares_builds_mount_references() -> None:
    """群组分享消息应转换为可挂载关系空间定位信息。"""
    shares = MyDriveRelationshipService._serialize_shares(
        [
            {
                'msg_id': 'message-1',
                'uk': 'author-1',
                'file_list': [
                    {'fs_id': 'root-1', 'server_filename': '群组资料', 'isdir': 0, 'size': 1},
                ],
            }
        ],
        'group-1',
        'group',
    )

    assert shares[0]['source_id'] == 'group-1'
    assert shares[0]['from_uk'] == 'author-1'
    assert shares[0]['is_directory'] is False
