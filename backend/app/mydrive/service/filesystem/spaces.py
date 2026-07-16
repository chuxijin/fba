#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable

from backend.app.mydrive.service.filesystem.capabilities import FileCapability
from backend.app.mydrive.service.filesystem.models import FileObject, ShareLink, SpaceLocator


class FileSpace(ABC):
    """只读文件空间。"""

    @property
    @abstractmethod
    def locator(self) -> SpaceLocator:
        """获取文件空间定位信息。"""

    @property
    def capabilities(self) -> frozenset[FileCapability]:
        """获取文件空间能力。"""
        return frozenset({FileCapability.LIST, FileCapability.GET})

    def supports(self, capability: FileCapability) -> bool:
        """
        判断是否支持指定能力。

        :param capability: 文件空间能力
        :return: 是否支持
        """
        return capability in self.capabilities

    async def aclose(self) -> None:
        """关闭文件空间资源。"""

    @abstractmethod
    async def list(self, directory: FileObject | None = None) -> list[FileObject]:
        """
        列出目录内容。

        :param directory: 待列出的目录，为空时列出空间根目录
        :return: 文件对象列表
        """

    @abstractmethod
    async def get(self, file_id: str) -> FileObject | None:
        """
        获取文件对象。

        :param file_id: 文件唯一标识
        :return: 文件对象，不存在时返回空
        """


class TransferSource(FileSpace):
    """可单向转存的只读文件空间。"""

    @property
    def capabilities(self) -> frozenset[FileCapability]:
        """获取外部源能力。"""
        return super().capabilities | {FileCapability.TRANSFER_TO_TARGET}

    @abstractmethod
    async def transfer_to(
        self,
        files: Iterable[FileObject],
        target: WritableFileSpace,
        target_directory: FileObject | None = None,
    ) -> list[FileObject]:
        """
        将文件转存到个人文件空间。

        :param files: 待转存文件
        :param target: 可写目标空间
        :param target_directory: 目标目录，为空时使用空间根目录
        :return: 目标空间中的文件对象
        """


class WritableFileSpace(FileSpace):
    """可写个人文件空间。"""

    @property
    def capabilities(self) -> frozenset[FileCapability]:
        """获取可写空间能力。"""
        return super().capabilities | {
            FileCapability.MAKE_DIRECTORY,
            FileCapability.COPY,
            FileCapability.MOVE,
            FileCapability.RENAME,
            FileCapability.REMOVE,
        }

    @abstractmethod
    async def make_directory(self, name: str, parent: FileObject | None = None) -> FileObject:
        """
        创建目录。

        :param name: 目录名称
        :param parent: 父目录，为空时在空间根目录创建
        :return: 创建后的目录对象
        """

    @abstractmethod
    async def copy(self, files: Iterable[FileObject], target: FileObject | None = None) -> None:
        """
        在文件空间内复制文件或目录。

        :param files: 待复制对象
        :param target: 目标目录，为空时使用空间根目录
        :return:
        """

    @abstractmethod
    async def move(self, files: Iterable[FileObject], target: FileObject | None = None) -> None:
        """
        在文件空间内移动文件或目录。

        :param files: 待移动对象
        :param target: 目标目录，为空时使用空间根目录
        :return:
        """

    @abstractmethod
    async def rename(self, file: FileObject, new_name: str) -> FileObject:
        """
        重命名文件或目录。

        :param file: 待重命名对象
        :param new_name: 新名称
        :return: 重命名后的对象
        """

    @abstractmethod
    async def remove(self, files: Iterable[FileObject]) -> None:
        """
        删除文件或目录。

        :param files: 待删除对象
        :return:
        """


class ShareableFileSpace(WritableFileSpace):
    """可创建分享链接的个人文件空间。"""

    @property
    def capabilities(self) -> frozenset[FileCapability]:
        """获取可分享空间能力。"""
        return super().capabilities | {FileCapability.CREATE_SHARE, FileCapability.MANAGE_SHARES}

    @abstractmethod
    async def create_share(
        self,
        files: Iterable[FileObject],
        title: str,
        expires_in_days: int,
        password: str = '',
    ) -> ShareLink:
        """
        创建文件分享链接。

        :param files: 待分享文件
        :param title: 分享标题
        :param expires_in_days: 有效期天数，0 表示永久
        :param password: 分享提取码
        :return:
        """

    @abstractmethod
    async def list_shares(self, page: int, per_page: int) -> tuple[list[ShareLink], int]:
        """
        获取个人创建的分享链接。

        :param page: 页码
        :param per_page: 每页数量
        :return:
        """

    @abstractmethod
    async def get_share(self, share_id: str) -> ShareLink | None:
        """
        获取个人分享详情。

        :param share_id: 分享 ID
        :return:
        """

    @abstractmethod
    async def cancel_shares(self, share_ids: Iterable[str]) -> None:
        """
        取消个人分享链接。

        :param share_ids: 分享 ID 列表
        :return:
        """
