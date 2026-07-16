#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""集中装配 MyDrive 驱动。"""

from backend.app.mydrive.service.filesystem.driver_registry import get_driver_registry
from backend.app.mydrive.service.drives.quark.personal_space import QuarkPersonalSpace


@get_driver_registry().register('quark')
def create_quark_personal_space(
    account_id: int,
    credential: dict[str, str],
    root_id: str = '0',
    root_path: str = '/',
) -> QuarkPersonalSpace:
    """
    创建夸克个人文件空间。

    :param account_id: MyDrive 账户 ID
    :param credential: 夸克授权凭证
    :param root_id: 根目录 ID
    :param root_path: 根目录路径
    :return:
    """
    cookie = str(credential.get('cookie') or '').strip()
    if not cookie:
        raise ValueError('夸克授权凭证缺少 Cookie')
    return QuarkPersonalSpace(account_id=account_id, cookie=cookie, root_id=root_id, root_path=root_path)


def load_drivers() -> None:
    """加载已启用的文件空间驱动。"""
