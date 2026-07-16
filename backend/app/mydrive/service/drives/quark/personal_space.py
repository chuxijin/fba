#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Iterable

from backend.app.mydrive.service.filesystem.models import FileObject, ShareLink, SpaceLocator, SpaceType
from backend.app.mydrive.service.filesystem.spaces import ShareableFileSpace
from backend.app.mydrive.service.drives.quark.client import QuarkRequest
from backend.app.mydrive.service.drives.quark.types import build_quark_file


class QuarkPersonalSpace(ShareableFileSpace):
    """夸克个人文件空间。"""

    def __init__(
        self,
        account_id: int,
        cookie: str,
        root_id: str = '0',
        root_path: str = '/',
        client: QuarkRequest | None = None,
    ) -> None:
        """
        初始化夸克个人文件空间。

        :param account_id: MyDrive 账户 ID
        :param cookie: 夸克网盘 Cookie
        :param root_id: 根目录 ID
        :param root_path: 根目录路径
        :param client: 夸克请求封装
        """
        self._locator = SpaceLocator(
            provider='quark',
            space_type=SpaceType.PERSONAL,
            account_id=str(account_id),
            root_id=root_id,
            root_path=root_path,
        )
        self._client = client or QuarkRequest(cookie)
        self._files: dict[str, FileObject] = {}

    @property
    def locator(self) -> SpaceLocator:
        """获取夸克个人文件空间定位信息。"""
        return self._locator

    async def aclose(self) -> None:
        """关闭夸克个人文件空间资源。"""
        await self._client.aclose()

    async def list(self, directory: FileObject | None = None) -> list[FileObject]:
        """
        列出夸克目录内容。

        :param directory: 待列出的目录，为空时列出空间根目录
        :return:
        """
        parent_id = directory.file_id if directory is not None else self.locator.root_id or '0'
        parent_path = directory.path if directory is not None else self.locator.root_path
        items = await self._client.list_files(parent_id)
        files = [build_quark_file(self.locator, item, parent_path) for item in items]
        self._files.update({file.file_id: file for file in files})
        return files

    async def get(self, file_id: str) -> FileObject | None:
        """
        获取已读取的夸克文件对象。

        :param file_id: 文件唯一标识
        :return:
        """
        return self._files.get(file_id)

    async def search(self, keyword: str, path: str = '/', recursive: bool = False) -> list[FileObject]:
        """
        搜索夸克个人空间文件。

        :param keyword: 搜索关键词
        :param path: 搜索目录路径，夸克搜索接口暂不支持按路径限定
        :param recursive: 是否递归搜索，夸克搜索接口默认为全局搜索
        :return:
        """
        items = await self._client.search_files(keyword)
        files = [build_quark_file(self.locator, item, '/', extra=self._get_search_extra(item)) for item in items]
        self._files.update({file.file_id: file for file in files})
        return files

    @staticmethod
    def _get_search_extra(item: dict) -> dict:
        """提取夸克搜索结果扩展信息。"""
        return {
            'highlight_name': item.get('hl_file_name'),
            'format_type': item.get('format_type'),
            'obj_category': item.get('obj_category'),
            'source_display': item.get('source_display'),
            'preview_url': item.get('preview_url'),
        }

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
        current_files = await self.list(directory)
        file_names = {file.name for file in source_files}
        return [file for file in current_files if file.name in file_names]

    async def make_directory(self, name: str, parent: FileObject | None = None) -> FileObject:
        """
        创建夸克目录。

        :param name: 目录名称
        :param parent: 父目录，为空时在空间根目录创建
        :return:
        """
        parent_id = parent.file_id if parent is not None else self.locator.root_id or '0'
        parent_path = parent.path if parent is not None else self.locator.root_path
        item = await self._client.make_directory(parent_id, name)
        directory = build_quark_file(self.locator, item, parent_path)
        self._files[directory.file_id] = directory
        return directory

    async def copy(self, files: Iterable[FileObject], target: FileObject | None = None) -> None:
        """
        在夸克个人空间内复制文件。

        :param files: 待复制对象
        :param target: 目标目录，为空时使用空间根目录
        :return:
        """
        file_ids = [file.file_id for file in files]
        if not file_ids:
            return
        target_id = target.file_id if target is not None else self.locator.root_id or '0'
        await self._client.copy_files(file_ids, target_id)

    async def move(self, files: Iterable[FileObject], target: FileObject | None = None) -> None:
        """
        在夸克个人空间内移动文件。

        :param files: 待移动对象
        :param target: 目标目录，为空时使用空间根目录
        :return:
        """
        file_ids = [file.file_id for file in files]
        if not file_ids:
            return
        target_id = target.file_id if target is not None else self.locator.root_id or '0'
        await self._client.move_files(file_ids, target_id)

    async def rename(self, file: FileObject, new_name: str) -> FileObject:
        """
        重命名夸克文件或目录。

        :param file: 待重命名对象
        :param new_name: 新名称
        :return:
        """
        await self._client.rename_file(file.file_id, new_name)
        renamed_file = FileObject(
            space=file.space,
            file_id=file.file_id,
            name=new_name,
            path=f'{file.path.rsplit("/", 1)[0]}/{new_name}',
            is_directory=file.is_directory,
            size=file.size,
            parent_id=file.parent_id,
            created_at=file.created_at,
            modified_at=file.modified_at,
            hash_value=file.hash_value,
            extra=file.extra,
        )
        self._files[renamed_file.file_id] = renamed_file
        return renamed_file

    async def remove(self, files: Iterable[FileObject]) -> None:
        """
        删除夸克文件或目录。

        :param files: 待删除对象
        :return:
        """
        file_ids = [file.file_id for file in files]
        if not file_ids:
            return
        await self._client.remove_files(file_ids)
        for file_id in file_ids:
            self._files.pop(file_id, None)

    async def create_share(
        self,
        files: Iterable[FileObject],
        title: str,
        expires_in_days: int,
        password: str = '',
    ) -> ShareLink:
        """
        创建夸克网盘分享链接。

        :param files: 待分享文件
        :param title: 分享标题
        :param expires_in_days: 有效期天数
        :param password: 分享提取码
        :return:
        """
        if password:
            raise ValueError('夸克网盘创建分享时不支持指定提取码')
        file_ids = [file.file_id for file in files]
        return await self._client.create_share(file_ids, title, expires_in_days)

    async def list_shares(self, page: int, per_page: int) -> tuple[list[ShareLink], int]:
        """获取夸克网盘分享列表。"""
        return await self._client.list_shares(page, per_page)

    async def get_share(self, share_id: str) -> ShareLink | None:
        """获取夸克网盘分享详情。"""
        return await self._client.get_share(share_id)

    async def cancel_shares(self, share_ids: Iterable[str]) -> None:
        """取消夸克网盘分享链接。"""
        await self._client.cancel_shares(list(share_ids))
