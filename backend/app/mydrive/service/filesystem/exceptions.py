#!/usr/bin/env python3
# -*- coding: utf-8 -*-


class MyDriveError(Exception):
    """MyDrive 领域异常。"""


class CapabilityNotSupportedError(MyDriveError):
    """文件空间不支持指定能力。"""

    def __init__(self, capability: str, space_key: str) -> None:
        """
        初始化能力不支持异常。

        :param capability: 所需能力
        :param space_key: 文件空间标识
        """
        super().__init__(f'文件空间 {space_key} 不支持能力: {capability}')


class InvalidTransferError(MyDriveError):
    """无效的文件转存。"""


class ShareExpiredError(MyDriveError):
    """分享链接已过期。"""


class SharePasswordRequiredError(MyDriveError):
    """分享链接需要提取码。"""


class ShareAccessDeniedError(MyDriveError):
    """分享链接访问被拒绝。"""


class AccountAuthExpiredError(MyDriveError):
    """网盘账户授权已失效。"""
