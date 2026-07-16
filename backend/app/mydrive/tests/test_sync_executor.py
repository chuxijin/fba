#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio
from collections.abc import Iterable
from pathlib import PurePosixPath

from backend.app.mydrive.model.space import MyDriveSpace
from backend.app.mydrive.service.filesystem.models import FileObject, ShareLink, SpaceLocator, SpaceType
from backend.app.mydrive.service.filesystem.spaces import ShareableFileSpace
from backend.app.mydrive.service.sync.executor import MyDriveSyncExecutor
from backend.app.mydrive.service.sync.rules import SyncRule


class FakePersonalSpace(ShareableFileSpace):
    """内存个人文件空间。"""

    def __init__(self, account_id: str) -> None:
        """
        初始化内存个人文件空间。

        :param account_id: 账户 ID
        :return:
        """
        self._locator = SpaceLocator(provider='baidu', space_type=SpaceType.PERSONAL, account_id=account_id)
        self.files: list[FileObject] = []
        self.removed_share_ids: list[str] = []

    @property
    def locator(self) -> SpaceLocator:
        """获取文件空间定位信息。"""
        return self._locator

    async def list(self, directory: FileObject | None = None) -> list[FileObject]:
        """
        列出目录文件。

        :param directory: 待列出的目录
        :return:
        """
        return list(self.files)

    async def get(self, file_id: str) -> FileObject | None:
        """
        获取文件对象。

        :param file_id: 文件 ID
        :return:
        """
        return next((file for file in self.files if file.file_id == file_id), None)

    async def make_directory(self, name: str, parent: FileObject | None = None) -> FileObject:
        """
        创建目录。

        :param name: 目录名称
        :param parent: 父目录
        :return:
        """
        directory = FileObject(space=self.locator, file_id=f'dir-{name}', name=name, path=f'/{name}', is_directory=True)
        self.files.append(directory)
        return directory

    async def copy(self, files: Iterable[FileObject], target: FileObject | None = None) -> None:
        """
        复制文件。

        :param files: 待复制文件
        :param target: 目标目录
        :return:
        """
        self.files.extend(
            FileObject(
                space=self.locator,
                file_id=f'copy-{file.file_id}',
                name=file.name,
                path=f'/{file.name}',
                size=file.size,
            )
            for file in files
        )

    async def move(self, files: Iterable[FileObject], target: FileObject | None = None) -> None:
        """
        移动文件。

        :param files: 待移动文件
        :param target: 目标目录
        :return:
        """

    async def rename(self, file: FileObject, new_name: str) -> FileObject:
        """
        重命名文件。

        :param file: 待重命名文件
        :param new_name: 新名称
        :return:
        """
        renamed = FileObject(space=self.locator, file_id=file.file_id, name=new_name, path=f'/{new_name}', size=file.size)
        self.files = [renamed if item.file_id == file.file_id else item for item in self.files]
        return renamed

    async def remove(self, files: Iterable[FileObject]) -> None:
        """
        删除文件。

        :param files: 待删除文件
        :return:
        """
        file_ids = {file.file_id for file in files}
        self.files = [file for file in self.files if file.file_id not in file_ids]

    async def create_share(
        self,
        files: Iterable[FileObject],
        title: str,
        expires_in_days: int,
        password: str = '',
    ) -> ShareLink:
        """
        创建分享链接。

        :param files: 待分享文件
        :param title: 分享标题
        :param expires_in_days: 有效期天数
        :param password: 分享提取码
        :return:
        """
        return ShareLink(provider='baidu', share_id='temporary', title=title, url='https://pan.baidu.com/s/temporary')

    async def list_shares(self, page: int, per_page: int) -> tuple[list[ShareLink], int]:
        """
        获取分享列表。

        :param page: 页码
        :param per_page: 每页数量
        :return:
        """
        return [], 0

    async def get_share(self, share_id: str) -> ShareLink | None:
        """
        获取分享详情。

        :param share_id: 分享 ID
        :return:
        """
        return None

    async def cancel_shares(self, share_ids: Iterable[str]) -> None:
        """
        取消分享链接。

        :param share_ids: 分享 ID
        :return:
        """
        self.removed_share_ids.extend(share_ids)


def test_cross_account_share_reference_uses_target_account() -> None:
    """跨账户临时分享应使用目标账户构建来源空间。"""
    executor = MyDriveSyncExecutor()
    target_space = MyDriveSpace(
        owner_id=1,
        provider='baidu',
        space_type='personal',
        name='target',
        source_key='account:2',
        account_id=2,
    )
    source = FakePersonalSpace('1')
    target = FakePersonalSpace('2')
    source_file = FileObject(space=source.locator, file_id='source-file', name='course.mp4', path='/course.mp4', size=1)

    async def run() -> None:
        share = await source.create_share([source_file], 'sync', 1)
        reference = executor._get_temporary_share_ref(share.provider, share.share_id, share.url, share.password)
        assert target_space.account_id == 2
        assert reference == {'url': 'https://pan.baidu.com/s/temporary', 'passcode': ''}
        await source.cancel_shares([share.share_id])

    asyncio.run(run())
    assert source.removed_share_ids == ['temporary']


def test_relative_path_uses_sync_root() -> None:
    """同步排除规则应使用挂载内相对路径。"""
    executor = MyDriveSyncExecutor()

    assert executor._relative_path('/source/nested/course.mp4', '/source') == 'nested/course.mp4'
    assert executor._relative_path('/source/course.mp4', '/source') == 'course.mp4'


def test_ensure_directory_creates_missing_target_path() -> None:
    """同步执行前应逐级创建缺失目标目录。"""

    class HierarchicalSpace(FakePersonalSpace):
        """按父目录维护目录树。"""

        async def list(self, directory: FileObject | None = None) -> list[FileObject]:
            """返回当前父目录下的项目。"""
            parent_path = directory.path if directory is not None else '/'
            return [file for file in self.files if file.parent_id == parent_path]

        async def make_directory(self, name: str, parent: FileObject | None = None) -> FileObject:
            """创建目录并记录父目录。"""
            parent_path = parent.path if parent is not None else '/'
            path = str(PurePosixPath(parent_path) / name)
            directory = FileObject(
                space=self.locator,
                file_id=f'dir-{path}',
                name=name,
                path=path,
                parent_id=parent_path,
                is_directory=True,
            )
            self.files.append(directory)
            return directory

    executor = MyDriveSyncExecutor()
    target = HierarchicalSpace('1')

    directory = asyncio.run(executor._ensure_directory(target, '/01.公考名师（重要）/01.资料+数量'))

    assert directory is not None
    assert directory.path == '/01.公考名师（重要）/01.资料+数量'
    assert [file.path for file in target.files] == [
        '/01.公考名师（重要）',
        '/01.公考名师（重要）/01.资料+数量',
    ]


def test_overwrite_sync_preserves_current_level_excluded_items(monkeypatch) -> None:
    """覆盖同步应仅处理当前层，且保留被排除的目标项目。"""
    executor = MyDriveSyncExecutor()
    locator = SpaceLocator(provider='baidu', space_type=SpaceType.PERSONAL, account_id='1')
    source_items = [
        FileObject(space=locator, file_id='source-a', name='A', path='/source/A'),
        FileObject(space=locator, file_id='source-b', name='B', path='/source/B'),
        FileObject(space=locator, file_id='source-c', name='C', path='/source/C', is_directory=True),
    ]
    target_items = [
        FileObject(space=locator, file_id='target-a', name='A', path='/target/A'),
        FileObject(space=locator, file_id='target-b', name='B', path='/target/B'),
        FileObject(space=locator, file_id='target-c', name='C', path='/target/C', is_directory=True),
    ]

    class ListSpace:
        """目录列表替身。"""

        async def list(self, directory: FileObject | None = None) -> list[FileObject]:
            """按目录返回预置项目。"""
            return source_items if directory is None else target_items

    removed_items: list[FileObject] = []
    transferred_items: list[FileObject] = []

    async def remove_items(*args, **kwargs) -> None:
        """记录覆盖删除项目。"""
        removed_items.extend(args[3])

    async def copy_files(*args, **kwargs) -> list[FileObject]:
        """记录覆盖转存项目。"""
        transferred_items.extend(args[5])
        return []

    monkeypatch.setattr(executor, '_remove_items', remove_items)
    monkeypatch.setattr(executor, '_copy_files', copy_files)

    asyncio.run(executor._overwrite_directory(
        object(),
        1,
        ListSpace(),
        ListSpace(),
        MyDriveSpace(owner_id=1, provider='baidu', space_type='personal', name='target', source_key='account:1'),
        None,
        FileObject(space=locator, file_id='target-root', name='target', path='/target', is_directory=True),
        '/source',
        '/target',
        [SyncRule(rule_type='exclude', pattern='A')],
    ))

    assert [item.name for item in removed_items] == ['B', 'C']
    assert [item.name for item in transferred_items] == ['B', 'C']


def test_full_sync_preserves_excluded_target_items(monkeypatch) -> None:
    """完全同步不应删除被排除规则命中的目标项目。"""
    executor = MyDriveSyncExecutor()
    locator = SpaceLocator(provider='baidu', space_type=SpaceType.PERSONAL, account_id='1')
    source_items = [FileObject(space=locator, file_id='source-b', name='B', path='/source/B')]
    target_items = [
        FileObject(space=locator, file_id='target-a', name='A', path='/target/A'),
        FileObject(space=locator, file_id='target-b', name='B', path='/target/B'),
    ]

    class ListSpace:
        """目录列表替身。"""

        async def list(self, directory: FileObject | None = None) -> list[FileObject]:
            """按目录返回预置项目。"""
            return source_items if directory is None else target_items

    removed_items: list[FileObject] = []

    async def remove_items(*args, **kwargs) -> None:
        """记录完全同步删除项目。"""
        removed_items.extend(args[3])

    async def copy_files(*args, **kwargs) -> list[FileObject]:
        """跳过文件复制。"""
        return []

    monkeypatch.setattr(executor, '_remove_items', remove_items)
    monkeypatch.setattr(executor, '_copy_files', copy_files)
    monkeypatch.setattr(executor, '_is_cancel_requested', lambda db, task_id: asyncio.sleep(0, result=False))

    asyncio.run(executor._sync_directory(
        object(),
        1,
        ListSpace(),
        ListSpace(),
        MyDriveSpace(owner_id=1, provider='baidu', space_type='personal', name='target', source_key='account:1'),
        None,
        FileObject(space=locator, file_id='target-root', name='target', path='/target', is_directory=True),
        '/source',
        '/target',
        'full',
        [SyncRule(rule_type='exclude', pattern='A')],
        '/source',
        '/target',
    ))

    assert removed_items == []
