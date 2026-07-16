#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Iterable
from dataclasses import replace
from pathlib import PurePosixPath
from typing import Any

from backend.app.mydrive.service.drives.baidu.client import BaiduRequest, BaiduRequestError
from backend.app.mydrive.service.drives.baidu.types import build_baidu_file
from backend.app.mydrive.service.filesystem.models import FileObject, ShareLink, SpaceLocator, SpaceType
from backend.app.mydrive.service.filesystem.spaces import ShareableFileSpace
from backend.common.log import log


class BaiduPersonalSpace(ShareableFileSpace):
    """百度个人文件空间。"""

    def __init__(
        self,
        account_id: int,
        cookie: str,
        root_id: str | None = None,
        root_path: str = '/',
        client: BaiduRequest | None = None,
    ) -> None:
        """
        初始化百度个人文件空间。

        :param account_id: MyDrive 账户 ID
        :param cookie: 百度网盘 Cookie
        :param root_id: 根目录 ID
        :param root_path: 根目录路径
        :param client: 百度请求封装
        """
        self._locator = SpaceLocator(
            provider='baidu',
            space_type=SpaceType.PERSONAL,
            account_id=str(account_id),
            root_id=root_id,
            root_path=root_path,
        )
        self._client = client or BaiduRequest(cookie)
        self._files: dict[str, FileObject] = {}

    @property
    def locator(self) -> SpaceLocator:
        """获取百度个人文件空间定位信息。"""
        return self._locator

    async def aclose(self) -> None:
        """关闭百度个人文件空间资源。"""
        await self._client.aclose()

    async def list(self, directory: FileObject | None = None) -> list[FileObject]:
        """
        列出百度个人目录内容。

        :param directory: 待列出的目录，为空时列出空间根目录
        :return:
        """
        path = directory.path if directory is not None else self.locator.root_path
        try:
            items = await self._client.list_files(path)
        except BaiduRequestError as exc:
            should_retry_root = directory is None and exc.error_code == -9 and bool(self.locator.root_id)
            log.warning(
                '百度个人盘目录读取失败 path={} directory_id={} root_id={} error_code={} retry_root={}',
                path,
                directory.file_id if directory is not None else '',
                self.locator.root_id or '',
                exc.error_code,
                should_retry_root,
            )
            if not should_retry_root:
                raise
            items = await self._list_current_root_files()
        files = [build_baidu_file(self.locator, item) for item in items]
        self._files.update({file.file_id: file for file in files})
        return files

    async def _list_current_root_files(self) -> list[dict[str, Any]]:
        """通过根目录 ID 重新解析百度个人空间路径。"""
        root = await self._client.get_file_metadata(self.locator.root_id or '')
        if root is None or not bool(root.get('isdir', 0)):
            raise BaiduRequestError('百度个人空间根目录不存在或已变更')
        root_path = str(root.get('path') or '').strip()
        if not root_path:
            raise BaiduRequestError('未能解析百度个人空间根目录路径')
        self._locator = replace(self._locator, root_path=root_path)
        return await self._client.list_files(root_path)

    async def get(self, file_id: str) -> FileObject | None:
        """
        获取已读取的百度文件对象。

        :param file_id: 文件唯一标识
        :return:
        """
        return self._files.get(file_id)

    async def search(self, keyword: str, path: str, recursive: bool = False) -> list[FileObject]:
        """
        搜索百度个人空间文件。

        :param keyword: 搜索关键词
        :param path: 搜索目录路径
        :param recursive: 是否递归搜索
        :return:
        """
        files = [build_baidu_file(self.locator, item) for item in await self._client.search_files(keyword, path, recursive)]
        self._files.update({file.file_id: file for file in files})
        return files

    async def resolve_transferred_files(
        self,
        source_files: Iterable[FileObject],
        directory: FileObject | None = None,
    ) -> list[FileObject]:
        """
        获取刚转存到根目录的文件对象。

        :param source_files: 已转存的源文件
        :param directory: 转存目标目录
        :return:
        """
        file_names = {file.name for file in source_files}
        return [file for file in await self.list(directory) if file.name in file_names]

    async def make_directory(self, name: str, parent: FileObject | None = None) -> FileObject:
        """
        创建百度个人目录。

        :param name: 目录名称
        :param parent: 父目录，为空时在空间根目录创建
        :return:
        """
        parent_path = parent.path if parent is not None else self.locator.root_path
        path = str(PurePosixPath(parent_path) / name)
        directory = build_baidu_file(self.locator, await self._client.make_directory(path))
        self._files[directory.file_id] = directory
        return directory

    async def copy(self, files: Iterable[FileObject], target: FileObject | None = None) -> None:
        """
        在百度个人空间内复制文件。

        :param files: 待复制对象
        :param target: 目标目录，为空时使用空间根目录
        :return:
        """
        paths = [file.path for file in files]
        if paths:
            await self._client.copy_files(paths, target.path if target is not None else self.locator.root_path)

    async def move(self, files: Iterable[FileObject], target: FileObject | None = None) -> None:
        """
        在百度个人空间内移动文件。

        :param files: 待移动对象
        :param target: 目标目录，为空时使用空间根目录
        :return:
        """
        paths = [file.path for file in files]
        if paths:
            await self._client.move_files(paths, target.path if target is not None else self.locator.root_path)

    async def rename(self, file: FileObject, new_name: str) -> FileObject:
        """
        重命名百度文件或目录。

        :param file: 待重命名对象
        :param new_name: 新名称
        :return:
        """
        new_path = str(PurePosixPath(file.path).with_name(new_name))
        await self._client.rename_file(file.path, new_path)
        renamed_file = FileObject(
            space=file.space,
            file_id=file.file_id,
            name=new_name,
            path=new_path,
            is_directory=file.is_directory,
            size=file.size,
            parent_id=file.parent_id,
            created_at=file.created_at,
            modified_at=file.modified_at,
            hash_value=file.hash_value,
            extra=file.extra,
        )
        self._files[file.file_id] = renamed_file
        return renamed_file

    async def remove(self, files: Iterable[FileObject]) -> None:
        """
        删除百度文件或目录。

        :param files: 待删除对象
        :return:
        """
        file_list = list(files)
        if not file_list:
            return
        await self._client.remove_files([file.path for file in file_list])
        for file in file_list:
            self._files.pop(file.file_id, None)

    async def create_share(
        self,
        files: Iterable[FileObject],
        title: str,
        expires_in_days: int,
        password: str = '',
    ) -> ShareLink:
        """
        创建百度网盘分享链接。

        :param files: 待分享文件
        :param title: 分享标题
        :param expires_in_days: 有效期天数
        :param password: 分享提取码
        :return:
        """
        file_ids = [file.file_id for file in files]
        return await self._client.create_share(file_ids, title, expires_in_days, password)

    async def list_shares(self, page: int, per_page: int) -> tuple[list[ShareLink], int]:
        """获取百度网盘分享列表。"""
        return await self._client.list_shares(page, per_page)

    async def get_share(self, share_id: str) -> ShareLink | None:
        """获取百度网盘分享详情。"""
        return await self._client.get_share(share_id)

    async def cancel_shares(self, share_ids: Iterable[str]) -> None:
        """取消百度网盘分享链接。"""
        await self._client.cancel_shares(list(share_ids))
