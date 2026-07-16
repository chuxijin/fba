#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import pytest

from backend.app.mydrive.model.space import MyDriveSpace
from backend.app.mydrive.service.sync.policy import validate_sync_spaces
from backend.common.exception import errors


def _space(
    space_type: str,
    account_id: int,
    provider: str = 'baidu',
) -> MyDriveSpace:
    """
    构建测试文件空间。

    :param space_type: 文件空间类型
    :param account_id: 关联账户 ID
    :param provider: 网盘 Provider
    :return:
    """
    return MyDriveSpace(
        owner_id=1,
        provider=provider,
        space_type=space_type,
        name=f'{space_type}-{account_id}',
        source_key=f'{space_type}-{account_id}',
        account_id=account_id,
    )


def test_personal_source_allows_same_provider_target_account() -> None:
    """个人空间应允许同步至同 Provider 的其他个人账户。"""
    validate_sync_spaces(_space('personal', 1), _space('personal', 2))


def test_share_link_source_allows_same_provider_target_account() -> None:
    """分享链接应允许同步至同 Provider 的其他个人账户。"""
    validate_sync_spaces(_space('share_link', 1), _space('personal', 2))


@pytest.mark.parametrize('source_type', ['group', 'friend'])
def test_group_and_friend_sources_require_same_account(source_type: str) -> None:
    """群组和好友空间只允许同步至关联账户的个人空间。"""
    with pytest.raises(errors.ForbiddenError, match='关联账户'):
        validate_sync_spaces(_space(source_type, 1), _space('personal', 2))


def test_sync_target_must_be_personal_space() -> None:
    """同步目标只能是个人空间。"""
    with pytest.raises(errors.ForbiddenError, match='个人文件空间'):
        validate_sync_spaces(_space('personal', 1), _space('share_link', 1))


def test_sync_rejects_cross_provider_space() -> None:
    """同步不允许跨 Provider。"""
    with pytest.raises(errors.ForbiddenError, match='同一 Provider'):
        validate_sync_spaces(_space('personal', 1), _space('personal', 1, provider='quark'))
