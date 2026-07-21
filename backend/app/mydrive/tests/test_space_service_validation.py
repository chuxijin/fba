#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio
import json
from types import SimpleNamespace

import pytest

from backend.app.mydrive.schema.file import MyDriveFileReference
from backend.app.mydrive.schema.space import CreateMyDriveSpaceParam
from backend.app.mydrive.service.filesystem.models import FileObject, SpaceLocator, SpaceType
from backend.app.mydrive.service.filesystem.spaces import FileSpace
from backend.app.mydrive.service.space_service import MyDriveSpaceService
from backend.common.exception import errors


class FakeFileSpace(FileSpace):
    """文件空间替身。"""

    def __init__(self, files: list[FileObject], root_path: str = '/') -> None:
        """
        初始化文件空间替身。

        :param files: 根目录文件
        :param root_path: 空间根目录路径
        """
        self._locator = SpaceLocator(provider='quark', space_type=SpaceType.PERSONAL, root_path=root_path)
        self._files = files

    @property
    def locator(self) -> SpaceLocator:
        """获取文件空间定位信息。"""
        return self._locator

    async def list(self, directory: FileObject | None = None) -> list[FileObject]:
        """返回根目录文件。"""
        return self._files

    async def get(self, file_id: str) -> FileObject | None:
        """不返回缓存文件。"""
        return None


class FakeNestedFileSpace(FileSpace):
    """嵌套目录文件空间替身。"""

    def __init__(self) -> None:
        """初始化嵌套目录文件空间替身。"""
        self._locator = SpaceLocator(provider='quark', space_type=SpaceType.PERSONAL)
        self._folder = FileObject(
            space=self._locator,
            file_id='folder-1',
            name='folder',
            path='/folder',
            is_directory=True,
        )
        self._file = FileObject(
            space=self._locator,
            file_id='file-1',
            name='course.pdf',
            path='/folder/course.pdf',
            parent_id='folder-1',
        )

    @property
    def locator(self) -> SpaceLocator:
        """获取文件空间定位信息。"""
        return self._locator

    async def list(self, directory: FileObject | None = None) -> list[FileObject]:
        """按真实目录返回文件。"""
        if directory is None:
            return [self._folder]
        if directory.file_id == self._folder.file_id:
            return [self._file]
        return []

    async def get(self, file_id: str) -> FileObject | None:
        """不返回缓存文件。"""
        return None


def test_resolve_file_uses_remote_file_metadata() -> None:
    """文件操作应使用远端读取的文件对象。"""
    remote_file = FileObject(
        space=SpaceLocator(provider='quark', space_type=SpaceType.PERSONAL),
        file_id='remote-file',
        name='actual.pdf',
        path='/actual.pdf',
        extra={'remote': True},
    )
    file_space = FakeFileSpace([remote_file])
    request_file = MyDriveFileReference(
        file_id='remote-file',
        name='forged.pdf',
        path='/actual.pdf',
        extra={'remote': False},
    )

    resolved_file = asyncio.run(MyDriveSpaceService._resolve_file(file_space, request_file))

    assert resolved_file is remote_file


def test_resolve_file_rejects_forged_path() -> None:
    """文件操作应拒绝未在远端目录中的伪造路径。"""
    remote_file = FileObject(
        space=SpaceLocator(provider='quark', space_type=SpaceType.PERSONAL),
        file_id='remote-file',
        name='actual.pdf',
        path='/actual.pdf',
    )
    file_space = FakeFileSpace([remote_file])
    request_file = MyDriveFileReference(file_id='remote-file', name='actual.pdf', path='/forged.pdf')

    with pytest.raises(errors.NotFoundError, match='文件不存在'):
        asyncio.run(MyDriveSpaceService._resolve_file(file_space, request_file))


def test_resolve_file_rejects_relative_path() -> None:
    """文件操作应拒绝挂载根目录外的相对路径。"""
    file_space = FakeFileSpace([], root_path='/MyDrive')
    request_file = MyDriveFileReference(file_id='remote-file', name='actual.pdf', path='/../outside.pdf')

    with pytest.raises(errors.ForbiddenError, match='相对路径片段'):
        asyncio.run(MyDriveSpaceService._resolve_file(file_space, request_file))


def test_resolve_file_discovers_nested_parent_without_request_parent_id() -> None:
    """嵌套文件应从远端根目录逐级解析父目录。"""
    file_space = FakeNestedFileSpace()
    request_file = MyDriveFileReference(
        file_id='file-1',
        name='course.pdf',
        path='/folder/course.pdf',
        parent_id='forged-parent-id',
    )

    resolved_file = asyncio.run(MyDriveSpaceService._resolve_file(file_space, request_file))

    assert resolved_file.path == '/folder/course.pdf'


def test_normalize_personal_space_uses_account_source_and_capabilities() -> None:
    """个人空间应使用账户作为来源并固定可写能力。"""
    account = SimpleNamespace(id=12, provider='quark')
    obj = CreateMyDriveSpaceParam(
        provider='quark',
        space_type='personal',
        name='夸克个人盘',
        source_key='untrusted-source',
        account_id=12,
        capabilities=['remove'],
    )

    values = MyDriveSpaceService._normalize_space_values(obj, account)

    assert values['source_key'] == 'account:12'
    assert values['source_ref'] == {}
    assert values['capabilities'] == [
        'copy',
        'create_share',
        'get',
        'list',
        'make_directory',
        'manage_shares',
        'move',
        'remove',
        'rename',
    ]


def test_normalize_personal_space_distinguishes_root_directory() -> None:
    """个人空间应允许同账号挂载不同根目录。"""
    account = SimpleNamespace(id=12, provider='quark')
    obj = CreateMyDriveSpaceParam(
        provider='quark',
        space_type='personal',
        name='夸克课程目录',
        source_key='untrusted-source',
        account_id=12,
        root_id='folder-1',
        root_path='/课程',
    )

    values = MyDriveSpaceService._normalize_space_values(obj, account)

    assert values['source_key'] == 'account:12:root_id:folder-1'
    assert values['source_ref'] == {}


def test_normalize_thunder_personal_space_does_not_declare_share_capability() -> None:
    """迅雷个人空间不应声明尚未实现的分享能力。"""
    account = SimpleNamespace(id=12, provider='thunder')
    obj = CreateMyDriveSpaceParam(
        provider='thunder',
        space_type='personal',
        name='迅雷个人盘',
        source_key='untrusted-source',
        account_id=12,
    )

    values = MyDriveSpaceService._normalize_space_values(obj, account)

    assert 'create_share' not in values['capabilities']


def test_normalize_quark_share_space_uses_share_source_and_read_only_capabilities() -> None:
    """夸克分享空间应使用分享标识并固定只读转存能力。"""
    account = SimpleNamespace(id=12, provider='quark')
    obj = CreateMyDriveSpaceParam(
        provider='quark',
        space_type='share_link',
        name='夸克分享',
        source_key='share-123',
        account_id=12,
        source_ref={'passcode': '1234'},
        capabilities=['remove'],
    )

    values = MyDriveSpaceService._normalize_space_values(obj, account)

    assert values['source_key'] == 'share-123'
    assert values['source_ref'] == {'passcode': '1234', 'share_id': 'share-123'}
    assert values['capabilities'] == ['get', 'list', 'transfer_to_target']


def test_normalize_baidu_share_space_extracts_passcode_from_url() -> None:
    """百度分享空间应支持粘贴带提取码的分享链接。"""
    account = SimpleNamespace(id=12, provider='baidu')
    obj = CreateMyDriveSpaceParam(
        provider='baidu',
        space_type='share_link',
        name='百度分享',
        source_key='https://pan.baidu.com/s/1SUedoHcTNuh3F3uLTsMw5w?pwd=buvv',
        account_id=12,
        source_ref={},
    )

    values = MyDriveSpaceService._normalize_space_values(obj, account)

    assert values['source_key'] == 'https://pan.baidu.com/s/1SUedoHcTNuh3F3uLTsMw5w'
    assert values['source_ref'] == {
        'passcode': 'buvv',
        'url': 'https://pan.baidu.com/s/1SUedoHcTNuh3F3uLTsMw5w',
    }


def test_normalize_baidu_share_space_keeps_explicit_passcode() -> None:
    """单独填写的百度提取码优先级高于链接查询参数。"""
    account = SimpleNamespace(id=12, provider='baidu')
    obj = CreateMyDriveSpaceParam(
        provider='baidu',
        space_type='share_link',
        name='百度分享',
        source_key='https://pan.baidu.com/s/1share?pwd=url1',
        account_id=12,
        source_ref={'passcode': 'form', 'url': 'https://pan.baidu.com/s/1share?pwd=url1'},
    )

    values = MyDriveSpaceService._normalize_space_values(obj, account)

    assert values['source_key'] == 'https://pan.baidu.com/s/1share'
    assert values['source_ref'] == {'passcode': 'form', 'url': 'https://pan.baidu.com/s/1share'}


def test_normalize_baidu_friend_space_uses_relationship_reference() -> None:
    """百度好友空间应固化分享消息定位信息和只读能力。"""
    account = SimpleNamespace(id=12, provider='baidu')
    obj = CreateMyDriveSpaceParam(
        provider='baidu',
        space_type='friend',
        name='好友课程',
        source_key='friend-1',
        account_id=12,
        source_ref={'from_uk': 'friend-1', 'message_id': 'message-1', 'root_id': 'root-1'},
    )

    values = MyDriveSpaceService._normalize_space_values(obj, account)

    assert values['source_key'] == 'friend-1'
    assert values['root_id'] == 'root-1'
    assert values['source_ref'] == {
        'source_id': 'friend-1',
        'from_uk': 'friend-1',
        'message_id': 'message-1',
        'root_id': 'root-1',
    }
    assert values['capabilities'] == ['get', 'list', 'transfer_to_target']


def test_validate_provider_rejects_mismatched_account() -> None:
    """空间 Provider 必须与关联账户一致。"""
    account = SimpleNamespace(provider='baidu')

    with pytest.raises(errors.ForbiddenError, match='必须与关联账户一致'):
        MyDriveSpaceService._validate_provider(account, 'quark')


def test_paginate_files_uses_openlist_page_shape() -> None:
    """目录列表应按 OpenList 风格分页。"""
    files = [
        FileObject(
            space=SpaceLocator(provider='quark', space_type=SpaceType.PERSONAL),
            file_id=str(index),
            name=f'file-{index}',
            path=f'/file-{index}',
        )
        for index in range(3)
    ]

    result = MyDriveSpaceService._paginate_files(files, '/', page=2, per_page=2)

    assert [file.file_id for file in result['items']] == ['2']
    assert result['total'] == 3
    assert result['page'] == 2
    assert result['per_page'] == 2
    assert result['path'] == '/'


def test_virtual_file_hides_mount_root_path() -> None:
    """子目录挂载不应在响应中暴露真实根目录路径。"""
    file_space = FakeFileSpace([], root_path='/MyDrive')
    remote_file = FileObject(
        space=file_space.locator,
        file_id='file-1',
        name='course.pdf',
        path='/MyDrive/course.pdf',
    )

    file = MyDriveSpaceService._to_virtual_file(file_space, remote_file)

    assert file.path == '/course.pdf'


def test_virtual_file_converts_transferred_file_path() -> None:
    """转存返回文件应转换为挂载内虚拟路径。"""
    file_space = FakeFileSpace([], root_path='/课程')
    remote_file = FileObject(
        space=file_space.locator,
        file_id='file-1',
        name='course.pdf',
        path='/课程/course.pdf',
        parent_id='folder-1',
    )

    file = MyDriveSpaceService._to_virtual_file(file_space, remote_file)

    assert file.file_id == 'file-1'
    assert file.path == '/course.pdf'


def test_preview_directory_maps_virtual_path_to_provider_path() -> None:
    """路径选择器目录 ID 应使用挂载根目录转换为驱动路径。"""
    file_space = FakeFileSpace([], root_path='/MyDrive')

    directory = MyDriveSpaceService._build_preview_directory(file_space, 'folder-1', '/courses')

    assert directory is not None
    assert directory.file_id == 'folder-1'
    assert directory.path == '/MyDrive/courses'


def test_normalize_virtual_path_rejects_traversal() -> None:
    """目录列表应拒绝路径穿越。"""
    with pytest.raises(errors.ForbiddenError, match='相对路径片段'):
        MyDriveSpaceService._normalize_virtual_path('/course/../private')


def test_directory_cache_round_trip(monkeypatch: pytest.MonkeyPatch) -> None:
    """目录缓存应保存并恢复完整文件列表。"""
    cache: dict[str, str] = {}

    async def get(key: str) -> str | None:
        """读取内存缓存。"""
        return cache.get(key)

    async def set_value(key: str, value: str, ex: int) -> None:
        """写入内存缓存。"""
        assert ex == 60
        cache[key] = value

    monkeypatch.setattr('backend.app.mydrive.service.space_service.redis_client.get', get)
    monkeypatch.setattr('backend.app.mydrive.service.space_service.redis_client.set', set_value)
    file = FileObject(
        space=SpaceLocator(provider='quark', space_type=SpaceType.PERSONAL),
        file_id='file-1',
        name='course.pdf',
        path='/course.pdf',
        extra={'share_file_token': 'token'},
    )

    asyncio.run(MyDriveSpaceService._set_cached_files(1, '/', [file]))
    cached_files = asyncio.run(MyDriveSpaceService._get_cached_files(1, '/'))

    assert json.loads(cache['mydrive:list:1:/'])[0]['file_id'] == 'file-1'
    assert cached_files is not None
    assert cached_files[0].extra == {'share_file_token': 'token'}


def test_invalidate_list_cache_removes_only_affected_directories(monkeypatch: pytest.MonkeyPatch) -> None:
    """目录写操作只应清除关联目录与子树缓存。"""
    deleted_keys: list[str] = []
    deleted_prefixes: list[str] = []

    async def delete(*keys: str) -> None:
        """记录删除键。"""
        deleted_keys.extend(keys)

    async def delete_by_prefix(prefix: str) -> None:
        """记录删除前缀。"""
        deleted_prefixes.append(prefix)

    monkeypatch.setattr('backend.app.mydrive.service.space_service.redis_client.delete', delete)
    monkeypatch.setattr('backend.app.mydrive.service.space_service.redis_client.delete_by_prefix', delete_by_prefix)

    asyncio.run(MyDriveSpaceService._invalidate_list_cache(1, directories={'/', '/target'}, trees={'/source'}))

    assert set(deleted_keys) == {'mydrive:list:1:/', 'mydrive:list:1:/target'}
    assert deleted_prefixes == ['mydrive:list:1:/source']


def test_list_cache_lock_uses_nx_ttl_and_releases_matching_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """目录回源锁应使用 TTL，并仅按令牌释放。"""
    set_calls: list[tuple[str, str, bool, int]] = []
    eval_calls: list[tuple[str, int, str, str]] = []

    async def set_value(key: str, value: str, *, nx: bool, ex: int) -> bool:
        """模拟成功加锁。"""
        set_calls.append((key, value, nx, ex))
        return True

    async def eval_value(script: str, keys: int, key: str, token: str) -> int:
        """记录安全解锁脚本。"""
        eval_calls.append((script, keys, key, token))
        return 1

    monkeypatch.setattr('backend.app.mydrive.service.space_service.redis_client.set', set_value)
    monkeypatch.setattr('backend.app.mydrive.service.space_service.redis_client.eval', eval_value)

    token = asyncio.run(MyDriveSpaceService._acquire_list_cache_lock(1, '/courses'))

    assert token is not None
    assert set_calls == [('mydrive:list-lock:1:/courses', token, True, 30)]
    asyncio.run(MyDriveSpaceService._release_list_cache_lock(1, '/courses', token))
    assert eval_calls[0][1:] == (1, 'mydrive:list-lock:1:/courses', token)
    assert "redis.call('get', KEYS[1]) == ARGV[1]" in eval_calls[0][0]
