#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
import json
from pathlib import PurePosixPath
import time
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
import uuid

from typing import Any

from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.mydrive.crud.crud_account import mydrive_account_dao
from backend.app.mydrive.crud.crud_space import mydrive_space_dao
from backend.app.mydrive.model.account import MyDriveAccount
from backend.app.mydrive.model.space import MyDriveSpace
from backend.app.mydrive.schema.file import MyDriveFileReference
from backend.app.mydrive.schema.space import CreateMyDriveSpaceParam, PreviewMyDriveSpaceParam, UpdateMyDriveSpaceParam
from backend.app.mydrive.service.filesystem.capabilities import FileCapability
from backend.app.mydrive.service.filesystem.exceptions import CapabilityNotSupportedError, MyDriveError
from backend.app.mydrive.service.filesystem.factory import create_file_space
from backend.app.mydrive.service.filesystem.models import FileObject, ShareLink, SpaceLocator, SpaceType
from backend.app.mydrive.service.filesystem.spaces import FileSpace, ShareableFileSpace, TransferSource, WritableFileSpace
from backend.app.mydrive.service.metrics import inc_directory_cache
from backend.app.mydrive.service.drives.baidu.client import BaiduRequestError
from backend.app.mydrive.service.drives.quark.client import QuarkRequest, QuarkRequestError
from backend.app.mydrive.service.drives.thunder.client import ThunderRequestError
from backend.app.mydrive.service.transfer_service import transfer_files
from backend.common.exception import errors
from backend.common.log import log
from backend.database.redis import redis_client


MYDRIVE_LIST_CACHE_TTL = 60
MYDRIVE_LIST_CACHE_LOCK_TTL = 30
MYDRIVE_LIST_CACHE_LOCK_WAIT_SECONDS = 1
MYDRIVE_LIST_CACHE_LOCK_RETRY_INTERVAL = 0.05


class MyDriveSpaceService:
    """文件空间服务"""

    @staticmethod
    async def get(db: AsyncSession, *, pk: int, owner_id: int) -> MyDriveSpace:
        """
        获取文件空间。

        :param db: 数据库会话
        :param pk: 文件空间 ID
        :param owner_id: 所属用户 ID
        :return:
        """
        space = await mydrive_space_dao.get(db, pk, owner_id)
        if space is None:
            raise errors.NotFoundError(msg='文件空间不存在')
        return space

    @staticmethod
    async def get_select(*, owner_id: int, space_type: str | None = None) -> Select:
        """
        获取文件空间查询语句。

        :param owner_id: 所属用户 ID
        :param space_type: 文件空间类型
        :return:
        """
        return await mydrive_space_dao.get_select(owner_id, space_type)

    @staticmethod
    async def create(db: AsyncSession, *, owner_id: int, obj: CreateMyDriveSpaceParam) -> MyDriveSpace:
        """
        创建文件空间。

        :param db: 数据库会话
        :param owner_id: 所属用户 ID
        :param obj: 创建参数
        :return:
        """
        MyDriveSpaceService._validate_space_type(obj.space_type)
        account = await MyDriveSpaceService._validate_account(db, owner_id, obj.account_id, obj.space_type)
        MyDriveSpaceService._validate_provider(account, obj.provider)
        values = MyDriveSpaceService._normalize_space_values(obj, account)

        existing = await mydrive_space_dao.get_by_source_key(
            db,
            owner_id,
            values['provider'],
            values['space_type'],
            values['source_key'],
        )
        if existing is not None:
            raise errors.ConflictError(msg='文件空间已存在')
        await MyDriveSpaceService._validate_remote_space(db, owner_id, values)
        space = MyDriveSpace(owner_id=owner_id, **values)
        db.add(space)
        await db.flush()
        return space

    @staticmethod
    async def update(
        db: AsyncSession,
        *,
        pk: int,
        owner_id: int,
        obj: UpdateMyDriveSpaceParam,
    ) -> int:
        """
        更新文件空间。

        :param db: 数据库会话
        :param pk: 文件空间 ID
        :param owner_id: 所属用户 ID
        :param obj: 更新参数
        :return:
        """
        space = await MyDriveSpaceService.get(db, pk=pk, owner_id=owner_id)
        if obj.capabilities is not None:
            MyDriveSpaceService._validate_capabilities(space.space_type, obj.capabilities)
        return await mydrive_space_dao.update_model(db, space.id, obj)

    @staticmethod
    async def preview_files(
        db: AsyncSession,
        *,
        owner_id: int,
        obj: PreviewMyDriveSpaceParam,
    ) -> dict[str, Any]:
        """
        预览未创建文件空间目录。

        :param db: 数据库会话
        :param owner_id: 所属用户 ID
        :param obj: 预览参数
        :return:
        """
        MyDriveSpaceService._validate_space_type(obj.space_type)
        account = await MyDriveSpaceService._validate_account(db, owner_id, obj.account_id, obj.space_type)
        MyDriveSpaceService._validate_provider(account, obj.provider)
        values = MyDriveSpaceService._normalize_space_values(
            CreateMyDriveSpaceParam(
                account_id=obj.account_id,
                name='preview',
                provider=obj.provider,
                root_id=obj.root_id,
                root_path=obj.root_path,
                source_key=obj.source_key,
                source_ref=obj.source_ref,
                space_type=obj.space_type,
            ),
            account,
        )
        candidate = MyDriveSpace(owner_id=owner_id, **values)
        file_space = await create_file_space(db, candidate)
        try:
            try:
                virtual_path = MyDriveSpaceService._normalize_virtual_path(obj.path)
                directory = MyDriveSpaceService._build_preview_directory(file_space, obj.file_id, virtual_path)
                if directory is None:
                    directory = await MyDriveSpaceService._resolve_virtual_directory(file_space, virtual_path)
                files = await file_space.list(directory)
                virtual_files = [MyDriveSpaceService._to_virtual_file(file_space, file) for file in files]
                return MyDriveSpaceService._paginate_files(virtual_files, virtual_path, 1, 200)
            except (BaiduRequestError, QuarkRequestError, ThunderRequestError) as exc:
                log.warning(
                    'MyDrive 文件空间预览失败 provider={} type={} path={} file_id={} error={}',
                    obj.provider,
                    obj.space_type,
                    obj.path,
                    obj.file_id or '',
                    exc,
                )
                raise errors.GatewayError(msg=f'无法预览文件空间目录：{exc}') from exc
        finally:
            await file_space.aclose()

    @staticmethod
    async def delete(db: AsyncSession, *, pk: int, owner_id: int) -> int:
        """
        删除文件空间。

        :param db: 数据库会话
        :param pk: 文件空间 ID
        :param owner_id: 所属用户 ID
        :return:
        """
        space = await MyDriveSpaceService.get(db, pk=pk, owner_id=owner_id)
        return await mydrive_space_dao.delete_model(db, space.id)

    @staticmethod
    async def list_files(
        db: AsyncSession,
        *,
        pk: int,
        owner_id: int,
        path: str = '/',
        file_id: str | None = None,
        page: int = 1,
        per_page: int = 200,
        refresh: bool = False,
    ) -> dict[str, Any]:
        """
        实时列出挂载空间目录内容。

        :param db: 数据库会话
        :param pk: 文件空间 ID
        :param owner_id: 所属用户 ID
        :param path: 挂载内目录路径
        :param file_id: 目录 ID
        :param page: 页码
        :param per_page: 每页文件数
        :param refresh: 是否强制刷新目录缓存
        :return:
        """
        space = await MyDriveSpaceService.get(db, pk=pk, owner_id=owner_id)
        virtual_path = MyDriveSpaceService._normalize_virtual_path(path)
        cache_path = MyDriveSpaceService._get_list_cache_path(virtual_path, file_id)
        cached_files = None
        if not refresh:
            cached_files = await MyDriveSpaceService._get_cached_files(pk, cache_path)
        if cached_files is not None:
            inc_directory_cache(outcome='hit')
            return MyDriveSpaceService._paginate_files(cached_files, virtual_path, page, per_page)

        inc_directory_cache(outcome='refresh' if refresh else 'miss')
        lock_token = await MyDriveSpaceService._acquire_list_cache_lock(pk, cache_path)
        try:
            if lock_token is None and not refresh:
                cached_files = await MyDriveSpaceService._wait_for_cached_files(pk, cache_path)
                if cached_files is not None:
                    inc_directory_cache(outcome='coalesced')
                    return MyDriveSpaceService._paginate_files(cached_files, virtual_path, page, per_page)

            file_space = await create_file_space(db, space)
            try:
                directory = MyDriveSpaceService._build_preview_directory(file_space, file_id, virtual_path)
                if directory is None:
                    directory = await MyDriveSpaceService._resolve_virtual_directory(file_space, virtual_path)
                try:
                    files = await file_space.list(directory)
                except (BaiduRequestError, QuarkRequestError, ThunderRequestError) as exc:
                    log.warning(
                        'MyDrive 文件空间目录读取失败 space_id={} provider={} type={} path={} file_id={} root_id={} error={}',
                        space.id,
                        space.provider,
                        space.space_type,
                        virtual_path,
                        file_id or '',
                        space.root_id or '',
                        exc,
                    )
                    raise errors.GatewayError(msg=f'无法读取文件空间目录：{exc}') from exc
                virtual_files = [MyDriveSpaceService._to_virtual_file(file_space, file) for file in files]
                await MyDriveSpaceService._set_cached_files(pk, cache_path, virtual_files)
                return MyDriveSpaceService._paginate_files(virtual_files, virtual_path, page, per_page)
            finally:
                await file_space.aclose()
        finally:
            if lock_token is not None:
                await MyDriveSpaceService._release_list_cache_lock(pk, cache_path, lock_token)

    @staticmethod
    async def search_files(
        db: AsyncSession,
        *,
        pk: int,
        owner_id: int,
        keyword: str,
        path: str = '/',
        recursive: bool = False,
        page: int = 1,
        per_page: int = 200,
    ) -> dict[str, Any]:
        """
        搜索文件空间文件。

        :param db: 数据库会话
        :param pk: 文件空间 ID
        :param owner_id: 所属用户 ID
        :param keyword: 搜索关键词
        :param path: 挂载内目录路径
        :param recursive: 是否递归搜索
        :param page: 页码
        :param per_page: 每页文件数
        :return:
        """
        space = await MyDriveSpaceService.get(db, pk=pk, owner_id=owner_id)
        virtual_path = MyDriveSpaceService._normalize_virtual_path(path)
        file_space = await create_file_space(db, space)
        try:
            search = getattr(file_space, 'search', None)
            if search is None:
                raise errors.ForbiddenError(msg='当前文件空间不支持搜索')
            remote_path = MyDriveSpaceService._to_remote_path(file_space, virtual_path)
            try:
                files = await search(keyword, remote_path, recursive)
            except (BaiduRequestError, QuarkRequestError, ThunderRequestError) as exc:
                log.warning(
                    'MyDrive 文件空间搜索失败 space_id={} provider={} type={} path={} keyword={} error={}',
                    space.id,
                    space.provider,
                    space.space_type,
                    virtual_path,
                    keyword,
                    exc,
                )
                raise errors.GatewayError(msg=f'无法搜索文件空间：{exc}') from exc
            virtual_files = [MyDriveSpaceService._to_virtual_file(file_space, file) for file in files]
            return MyDriveSpaceService._paginate_files(virtual_files, virtual_path, page, per_page)
        finally:
            await file_space.aclose()

    @staticmethod
    async def make_directory(
        db: AsyncSession,
        *,
        pk: int,
        owner_id: int,
        name: str,
        parent: MyDriveFileReference | None = None,
    ) -> FileObject:
        """
        在个人文件空间创建目录。

        :param db: 数据库会话
        :param pk: 文件空间 ID
        :param owner_id: 所属用户 ID
        :param name: 目录名称
        :param parent: 父目录
        :return:
        """
        parent_path = MyDriveSpaceService._get_directory_path(parent)
        async with MyDriveSpaceService._writable_space(db, pk=pk, owner_id=owner_id) as file_space:
            directory = await file_space.make_directory(
                name,
                await MyDriveSpaceService._resolve_file(file_space, parent, directory_required=True),
            )
        await MyDriveSpaceService._invalidate_list_cache(pk, directories={parent_path})
        return directory

    @staticmethod
    async def copy_files(
        db: AsyncSession,
        *,
        pk: int,
        owner_id: int,
        files: list[MyDriveFileReference],
        target: MyDriveFileReference | None = None,
    ) -> None:
        """
        在个人文件空间复制文件。

        :param db: 数据库会话
        :param pk: 文件空间 ID
        :param owner_id: 所属用户 ID
        :param files: 待复制文件
        :param target: 目标目录
        :return:
        """
        target_path = MyDriveSpaceService._get_directory_path(target)
        async with MyDriveSpaceService._writable_space(db, pk=pk, owner_id=owner_id) as file_space:
            await file_space.copy(
                await MyDriveSpaceService._resolve_files(file_space, files),
                await MyDriveSpaceService._resolve_file(file_space, target, directory_required=True),
            )
        await MyDriveSpaceService._invalidate_list_cache(pk, directories={target_path})

    @staticmethod
    async def move_files(
        db: AsyncSession,
        *,
        pk: int,
        owner_id: int,
        files: list[MyDriveFileReference],
        target: MyDriveFileReference | None = None,
    ) -> None:
        """
        在个人文件空间移动文件。

        :param db: 数据库会话
        :param pk: 文件空间 ID
        :param owner_id: 所属用户 ID
        :param files: 待移动文件
        :param target: 目标目录
        :return:
        """
        target_path = MyDriveSpaceService._get_directory_path(target)
        async with MyDriveSpaceService._writable_space(db, pk=pk, owner_id=owner_id) as file_space:
            resolved_files = await MyDriveSpaceService._resolve_files(file_space, files)
            source_directories = {
                MyDriveSpaceService._get_parent_path(MyDriveSpaceService._to_virtual_file(file_space, file).path)
                for file in resolved_files
            }
            directory_trees = {
                MyDriveSpaceService._to_virtual_file(file_space, file).path
                for file in resolved_files
                if file.is_directory
            }
            await file_space.move(
                resolved_files,
                await MyDriveSpaceService._resolve_file(file_space, target, directory_required=True),
            )
        await MyDriveSpaceService._invalidate_list_cache(
            pk,
            directories={target_path, *source_directories},
            trees=directory_trees,
        )

    @staticmethod
    async def rename_file(
        db: AsyncSession,
        *,
        pk: int,
        owner_id: int,
        file: MyDriveFileReference,
        name: str,
    ) -> FileObject:
        """
        重命名个人文件空间文件。

        :param db: 数据库会话
        :param pk: 文件空间 ID
        :param owner_id: 所属用户 ID
        :param file: 待重命名文件
        :param name: 新名称
        :return:
        """
        async with MyDriveSpaceService._writable_space(db, pk=pk, owner_id=owner_id) as file_space:
            resolved_file = await MyDriveSpaceService._resolve_file(file_space, file)
            if resolved_file is None:
                raise errors.NotFoundError(msg='文件不存在')
            renamed_file = await file_space.rename(resolved_file, name)
            virtual_file = MyDriveSpaceService._to_virtual_file(file_space, resolved_file)
        await MyDriveSpaceService._invalidate_list_cache(
            pk,
            directories={MyDriveSpaceService._get_parent_path(virtual_file.path)},
            trees={virtual_file.path} if resolved_file.is_directory else set(),
        )
        return renamed_file

    @staticmethod
    async def remove_files(
        db: AsyncSession,
        *,
        pk: int,
        owner_id: int,
        files: list[MyDriveFileReference],
    ) -> None:
        """
        删除个人文件空间文件。

        :param db: 数据库会话
        :param pk: 文件空间 ID
        :param owner_id: 所属用户 ID
        :param files: 待删除文件
        :return:
        """
        async with MyDriveSpaceService._writable_space(db, pk=pk, owner_id=owner_id) as file_space:
            resolved_files = await MyDriveSpaceService._resolve_files(file_space, files)
            await file_space.remove(resolved_files)
            directory_trees = {
                MyDriveSpaceService._to_virtual_file(file_space, file).path
                for file in resolved_files
                if file.is_directory
            }
            parent_directories = {
                MyDriveSpaceService._get_parent_path(MyDriveSpaceService._to_virtual_file(file_space, file).path)
                for file in resolved_files
            }
        await MyDriveSpaceService._invalidate_list_cache(
            pk,
            directories=parent_directories,
            trees=directory_trees,
        )

    @staticmethod
    async def transfer_files(
        db: AsyncSession,
        *,
        pk: int,
        owner_id: int,
        files: list[MyDriveFileReference],
        target_space_id: int,
    ) -> list[FileObject]:
        """
        将外部空间文件转存到个人文件空间。

        :param db: 数据库会话
        :param pk: 源文件空间 ID
        :param owner_id: 所属用户 ID
        :param files: 待转存文件
        :param target_space_id: 目标个人文件空间 ID
        :return:
        """
        source_space = await MyDriveSpaceService.get(db, pk=pk, owner_id=owner_id)
        target_space = await MyDriveSpaceService.get(db, pk=target_space_id, owner_id=owner_id)
        source = await create_file_space(db, source_space)
        target = await create_file_space(db, target_space)
        try:
            if not isinstance(source, TransferSource):
                raise errors.ForbiddenError(msg='当前文件空间不支持转存')
            if not isinstance(target, WritableFileSpace):
                raise errors.ForbiddenError(msg='目标文件空间不支持写入')
            resolved_files = await MyDriveSpaceService._resolve_files(source, files)
            transferred_files = await transfer_files(source, resolved_files, target)
        except (CapabilityNotSupportedError, MyDriveError, ValueError) as exc:
            raise errors.ForbiddenError(msg=str(exc)) from exc
        finally:
            await source.aclose()
            await target.aclose()
        await MyDriveSpaceService._invalidate_list_cache(target_space_id, directories={'/'})
        return transferred_files

    @staticmethod
    async def save_share_files(
        db: AsyncSession,
        *,
        owner_id: int,
        target_space_id: int,
        account_id: int,
        provider: str,
        source_key: str,
        source_ref: dict[str, Any],
        root_id: str | None,
        root_path: str,
        files: list[MyDriveFileReference],
        target: MyDriveFileReference | None,
    ) -> list[FileObject]:
        """
        将临时分享文件保存到个人文件空间。

        :param db: 数据库会话
        :param owner_id: 所属用户 ID
        :param target_space_id: 目标个人文件空间 ID
        :param account_id: 目标网盘账户 ID
        :param provider: 网盘驱动标识
        :param source_key: 分享来源标识
        :param source_ref: 分享来源信息
        :param root_id: 分享根目录 ID
        :param root_path: 分享根目录路径
        :param files: 待保存文件
        :param target: 目标目录
        :return:
        """
        target_space = await MyDriveSpaceService.get(db, pk=target_space_id, owner_id=owner_id)
        if target_space.space_type != SpaceType.PERSONAL.value:
            raise errors.ForbiddenError(msg='仅支持保存到个人文件空间')
        if target_space.account_id != account_id or target_space.provider != provider:
            raise errors.ForbiddenError(msg='保存分享必须使用当前个人空间的同 Provider 账户')

        values = MyDriveSpaceService._normalize_space_values(
            CreateMyDriveSpaceParam(
                account_id=account_id,
                name='temporary-share',
                provider=provider,
                root_id=root_id,
                root_path=root_path,
                source_key=source_key,
                source_ref=source_ref,
                space_type=SpaceType.SHARE_LINK.value,
            ),
            await MyDriveSpaceService._validate_account(db, owner_id, account_id, SpaceType.SHARE_LINK.value),
        )
        source_space = MyDriveSpace(owner_id=owner_id, **values)
        source = await create_file_space(db, source_space)
        destination = await create_file_space(db, target_space)
        try:
            if not isinstance(source, TransferSource):
                raise errors.ForbiddenError(msg='当前分享不支持保存')
            if not isinstance(destination, WritableFileSpace):
                raise errors.ForbiddenError(msg='当前个人空间不支持写入')
            source_files = await MyDriveSpaceService._resolve_files(source, files)
            target_directory = await MyDriveSpaceService._resolve_file(destination, target) if target else None
            saved_files = await transfer_files(source, source_files, destination, target_directory)
            saved_files = [MyDriveSpaceService._to_virtual_file(destination, file) for file in saved_files]
        except (CapabilityNotSupportedError, MyDriveError, ValueError) as exc:
            raise errors.ForbiddenError(msg=str(exc)) from exc
        finally:
            await source.aclose()
            await destination.aclose()
        target_path = MyDriveSpaceService._get_directory_path(target)
        await MyDriveSpaceService._invalidate_list_cache(target_space_id, directories={'/', target_path})
        return saved_files

    @staticmethod
    async def invalidate_space_cache(pk: int) -> None:
        """清除文件空间全部目录缓存。"""
        await MyDriveSpaceService._invalidate_list_cache(pk, directories={'/'}, trees={'/'})

    @staticmethod
    async def create_share(
        db: AsyncSession,
        *,
        pk: int,
        owner_id: int,
        files: list[MyDriveFileReference],
        title: str,
        expires_in_days: int,
        password: str,
    ) -> ShareLink:
        """
        为个人文件空间创建分享链接。

        :param db: 数据库会话
        :param pk: 文件空间 ID
        :param owner_id: 所属用户 ID
        :param files: 待分享文件
        :param title: 分享标题
        :param expires_in_days: 有效期天数
        :param password: 分享提取码
        :return:
        """
        if expires_in_days not in {0, 1, 7, 30}:
            raise errors.ForbiddenError(msg='有效期仅支持 0、1、7、30 天')
        if password and len(password) != 4:
            raise errors.ForbiddenError(msg='分享提取码必须为 4 位')

        space = await MyDriveSpaceService.get(db, pk=pk, owner_id=owner_id)
        file_space = await create_file_space(db, space)
        try:
            if not isinstance(file_space, ShareableFileSpace):
                raise errors.ForbiddenError(msg='当前文件空间不支持创建分享链接')
            resolved_files = await MyDriveSpaceService._resolve_files(file_space, files)
            return await file_space.create_share(resolved_files, title, expires_in_days, password)
        except (MyDriveError, ValueError) as exc:
            raise errors.ForbiddenError(msg=str(exc)) from exc
        finally:
            await file_space.aclose()

    @staticmethod
    async def list_shares(
        db: AsyncSession, *, pk: int, owner_id: int, page: int, per_page: int
    ) -> dict[str, Any]:
        """
        获取个人创建的分享链接。

        :param db: 数据库会话
        :param pk: 文件空间 ID
        :param owner_id: 所属用户 ID
        :param page: 页码
        :param per_page: 每页数量
        :return:
        """
        space = await MyDriveSpaceService.get(db, pk=pk, owner_id=owner_id)
        file_space = await create_file_space(db, space)
        try:
            if not isinstance(file_space, ShareableFileSpace):
                raise errors.ForbiddenError(msg='当前文件空间不支持管理分享链接')
            shares, total = await file_space.list_shares(page, per_page)
            return {'items': shares, 'total': total, 'page': page, 'per_page': per_page}
        finally:
            await file_space.aclose()

    @staticmethod
    async def get_share(db: AsyncSession, *, pk: int, owner_id: int, share_id: str) -> ShareLink:
        """
        获取个人分享详情。

        :param db: 数据库会话
        :param pk: 文件空间 ID
        :param owner_id: 所属用户 ID
        :param share_id: 分享 ID
        :return:
        """
        space = await MyDriveSpaceService.get(db, pk=pk, owner_id=owner_id)
        file_space = await create_file_space(db, space)
        try:
            if not isinstance(file_space, ShareableFileSpace):
                raise errors.ForbiddenError(msg='当前文件空间不支持管理分享链接')
            share = await file_space.get_share(share_id)
            if share is None:
                raise errors.NotFoundError(msg='分享链接不存在或已失效')
            return share
        finally:
            await file_space.aclose()

    @staticmethod
    async def cancel_shares(
        db: AsyncSession, *, pk: int, owner_id: int, share_ids: list[str]
    ) -> None:
        """
        取消个人分享链接。

        :param db: 数据库会话
        :param pk: 文件空间 ID
        :param owner_id: 所属用户 ID
        :param share_ids: 分享 ID 列表
        :return:
        """
        space = await MyDriveSpaceService.get(db, pk=pk, owner_id=owner_id)
        file_space = await create_file_space(db, space)
        try:
            if not isinstance(file_space, ShareableFileSpace):
                raise errors.ForbiddenError(msg='当前文件空间不支持管理分享链接')
            await file_space.cancel_shares(share_ids)
        finally:
            await file_space.aclose()

    @staticmethod
    def _normalize_virtual_path(path: str) -> str:
        """规范化挂载内目录路径。"""
        if not path.startswith('/'):
            raise errors.ForbiddenError(msg='目录路径必须以 / 开头')
        path_parts = PurePosixPath(path).parts
        if '.' in path_parts or '..' in path_parts:
            raise errors.ForbiddenError(msg='目录路径不能包含相对路径片段')
        normalized_path = str(PurePosixPath(path))
        if normalized_path == '.':
            return '/'
        return normalized_path

    @staticmethod
    async def _resolve_virtual_directory(file_space: FileSpace, virtual_path: str) -> FileObject | None:
        """将挂载内目录路径解析为远端目录对象。"""
        if virtual_path == '/':
            return None

        current_directory: FileObject | None = None
        for directory_name in virtual_path.strip('/').split('/'):
            directories = await file_space.list(current_directory)
            current_directory = next(
                (item for item in directories if item.name == directory_name and item.is_directory),
                None,
            )
            if current_directory is None:
                raise errors.NotFoundError(msg='目录不存在或已变更')
        return current_directory

    @staticmethod
    def _build_preview_directory(
        file_space: FileSpace,
        file_id: str | None,
        virtual_path: str,
    ) -> FileObject | None:
        """
        根据预览请求构造目录对象。

        :param file_space: 文件空间
        :param file_id: 目录 ID
        :param virtual_path: 虚拟目录路径
        :return:
        """
        if not file_id:
            return None
        return FileObject(
            space=file_space.locator,
            file_id=file_id,
            name=virtual_path.rsplit('/', 1)[-1] or '/',
            path=MyDriveSpaceService._to_remote_path(file_space, virtual_path),
            is_directory=True,
        )

    @staticmethod
    def _to_remote_path(file_space: FileSpace, virtual_path: str) -> str:
        """将挂载内虚拟路径转换为驱动实际路径。"""
        root_path = MyDriveSpaceService._normalize_file_path(file_space.locator.root_path)
        if virtual_path == '/':
            return root_path
        if root_path == '/':
            return virtual_path
        return MyDriveSpaceService._normalize_file_path(str(PurePosixPath(root_path) / virtual_path.lstrip('/')))

    @staticmethod
    def _to_virtual_file(file_space: FileSpace, file: FileObject) -> FileObject:
        """将远端文件对象转换为挂载内文件对象。"""
        root_path = MyDriveSpaceService._normalize_file_path(file_space.locator.root_path)
        virtual_path = file.path.removeprefix(root_path).strip('/')
        path = f'/{virtual_path}' if virtual_path else '/'
        return FileObject(
            space=file.space,
            file_id=file.file_id,
            name=file.name,
            path=path,
            is_directory=file.is_directory,
            size=file.size,
            parent_id=file.parent_id,
            created_at=file.created_at,
            modified_at=file.modified_at,
            hash_value=file.hash_value,
            extra=file.extra,
        )

    @staticmethod
    def _paginate_files(
        files: list[FileObject],
        path: str,
        page: int,
        per_page: int,
    ) -> dict[str, Any]:
        """分页返回目录文件。"""
        start_index = (page - 1) * per_page
        return {
            'items': files[start_index : start_index + per_page],
            'total': len(files),
            'page': page,
            'per_page': per_page,
            'path': path,
        }

    @staticmethod
    def _get_directory_path(file: MyDriveFileReference | None) -> str:
        """获取目标目录的虚拟路径。"""
        if file is None:
            return '/'
        return MyDriveSpaceService._normalize_virtual_path(file.path)

    @staticmethod
    def _get_parent_path(path: str) -> str:
        """获取虚拟文件的父目录路径。"""
        normalized_path = MyDriveSpaceService._normalize_virtual_path(path)
        return MyDriveSpaceService._normalize_virtual_path(str(PurePosixPath(normalized_path).parent))

    @staticmethod
    async def _get_cached_files(pk: int, path: str) -> list[FileObject] | None:
        """获取目录缓存。"""
        try:
            cached_value = await redis_client.get(MyDriveSpaceService._list_cache_key(pk, path))
            if not cached_value:
                return None
            return [MyDriveSpaceService._deserialize_file(item) for item in json.loads(cached_value)]
        except Exception as exc:
            inc_directory_cache(outcome='read_error')
            log.warning('读取 MyDrive 目录缓存失败: {}', exc)
            return None

    @staticmethod
    async def _set_cached_files(pk: int, path: str, files: list[FileObject]) -> None:
        """缓存目录文件列表。"""
        try:
            serialized_files = [MyDriveSpaceService._serialize_file(file) for file in files]
            await redis_client.set(
                MyDriveSpaceService._list_cache_key(pk, path),
                json.dumps(serialized_files, ensure_ascii=False),
                ex=MYDRIVE_LIST_CACHE_TTL,
            )
            inc_directory_cache(outcome='write')
        except Exception as exc:
            inc_directory_cache(outcome='write_error')
            log.warning('写入 MyDrive 目录缓存失败: {}', exc)

    @staticmethod
    async def _invalidate_list_cache(pk: int, *, directories: set[str], trees: set[str] | None = None) -> None:
        """按目录清除文件空间缓存。"""
        try:
            for path in directories:
                await redis_client.delete(MyDriveSpaceService._list_cache_key(pk, path))
            for path in trees or set():
                await redis_client.delete_by_prefix(MyDriveSpaceService._list_cache_key(pk, path))
            inc_directory_cache(outcome='invalidate')
        except Exception as exc:
            inc_directory_cache(outcome='invalidate_error')
            log.warning('清除 MyDrive 目录缓存失败: {}', exc)

    @staticmethod
    def _list_cache_prefix(pk: int) -> str:
        """获取文件空间目录缓存前缀。"""
        return f'mydrive:list:{pk}'

    @staticmethod
    def _get_list_cache_path(path: str, file_id: str | None) -> str:
        """
        获取目录缓存路径标识。

        :param path: 虚拟目录路径
        :param file_id: 目录 ID
        :return:
        """
        if not file_id:
            return path
        return f'{path}:file:{file_id}'

    @staticmethod
    def _list_cache_key(pk: int, path: str) -> str:
        """获取目录缓存键。"""
        return f'{MyDriveSpaceService._list_cache_prefix(pk)}:{path}'

    @staticmethod
    def _list_cache_lock_key(pk: int, path: str) -> str:
        """获取目录回源锁键。"""
        return f'mydrive:list-lock:{pk}:{path}'

    @staticmethod
    async def _acquire_list_cache_lock(pk: int, path: str) -> str | None:
        """尝试获取目录缓存回源锁。"""
        token = uuid.uuid4().hex
        try:
            acquired = await redis_client.set(
                MyDriveSpaceService._list_cache_lock_key(pk, path),
                token,
                nx=True,
                ex=MYDRIVE_LIST_CACHE_LOCK_TTL,
            )
            if acquired:
                return token
            inc_directory_cache(outcome='lock_contended')
        except Exception as exc:
            inc_directory_cache(outcome='lock_error')
            log.warning('获取 MyDrive 目录缓存回源锁失败: {}', exc)
        return None

    @staticmethod
    async def _wait_for_cached_files(pk: int, path: str) -> list[FileObject] | None:
        """等待其他请求回填目录缓存。"""
        deadline = time.monotonic() + MYDRIVE_LIST_CACHE_LOCK_WAIT_SECONDS
        while time.monotonic() < deadline:
            await asyncio.sleep(MYDRIVE_LIST_CACHE_LOCK_RETRY_INTERVAL)
            cached_files = await MyDriveSpaceService._get_cached_files(pk, path)
            if cached_files is not None:
                return cached_files
        return None

    @staticmethod
    async def _release_list_cache_lock(pk: int, path: str, token: str) -> None:
        """仅释放当前请求持有的目录回源锁。"""
        try:
            await redis_client.eval(
                "if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('del', KEYS[1]) else return 0 end",
                1,
                MyDriveSpaceService._list_cache_lock_key(pk, path),
                token,
            )
        except Exception as exc:
            inc_directory_cache(outcome='unlock_error')
            log.warning('释放 MyDrive 目录缓存回源锁失败: {}', exc)

    @staticmethod
    def _serialize_file(file: FileObject) -> dict[str, Any]:
        """序列化文件对象用于目录缓存。"""
        return {
            'file_id': file.file_id,
            'name': file.name,
            'path': file.path,
            'is_directory': file.is_directory,
            'size': file.size,
            'parent_id': file.parent_id,
            'created_at': file.created_at.isoformat() if file.created_at else None,
            'modified_at': file.modified_at.isoformat() if file.modified_at else None,
            'hash_value': file.hash_value,
            'extra': file.extra,
        }

    @staticmethod
    def _deserialize_file(value: dict[str, Any]) -> FileObject:
        """从目录缓存恢复文件对象。"""
        return FileObject(
            space=SpaceLocator(provider='cached', space_type=SpaceType.PERSONAL),
            file_id=str(value['file_id']),
            name=str(value['name']),
            path=str(value['path']),
            is_directory=bool(value['is_directory']),
            size=value.get('size'),
            parent_id=value.get('parent_id'),
            created_at=MyDriveSpaceService._parse_cached_datetime(value.get('created_at')),
            modified_at=MyDriveSpaceService._parse_cached_datetime(value.get('modified_at')),
            hash_value=value.get('hash_value'),
            extra=value.get('extra') or {},
        )

    @staticmethod
    def _parse_cached_datetime(value: Any) -> datetime | None:
        """解析缓存时间字段。"""
        if not value:
            return None
        try:
            return datetime.fromisoformat(str(value))
        except ValueError:
            return None

    @staticmethod
    async def _resolve_file(
        file_space: FileSpace,
        file: MyDriveFileReference | None,
        *,
        directory_required: bool = False,
    ) -> FileObject | None:
        """从远端目录重新解析请求文件。"""
        if file is None:
            return None

        path = MyDriveSpaceService._normalize_virtual_path(file.path)
        parent_path = MyDriveSpaceService._normalize_virtual_path(str(PurePosixPath(path).parent))
        parent = await MyDriveSpaceService._resolve_virtual_directory(file_space, parent_path)
        candidates = await file_space.list(parent)

        resolved_file = next(
            (
                item
                for item in candidates
                if item.file_id == file.file_id and MyDriveSpaceService._to_virtual_file(file_space, item).path == path
            ),
            None,
        )
        if resolved_file is None:
            raise errors.NotFoundError(msg='文件不存在或已不在当前目录')
        if directory_required and not resolved_file.is_directory:
            raise errors.ForbiddenError(msg='目标必须是目录')
        return resolved_file

    @staticmethod
    async def _resolve_directory(
        file_space: FileSpace,
        directory_path: str,
        root_path: str,
    ) -> FileObject | None:
        """从空间根目录逐级解析远端目录。"""
        if directory_path == root_path:
            return None

        relative_path = directory_path.removeprefix(root_path).strip('/')
        current_directory: FileObject | None = None
        for directory_name in relative_path.split('/'):
            directories = await file_space.list(current_directory)
            current_directory = next(
                (item for item in directories if item.name == directory_name and item.is_directory),
                None,
            )
            if current_directory is None:
                raise errors.NotFoundError(msg='文件所在目录不存在或已变更')
        return current_directory

    @staticmethod
    async def _resolve_files(
        file_space: FileSpace,
        files: list[MyDriveFileReference],
    ) -> list[FileObject]:
        """从远端目录重新解析请求文件列表。"""
        resolved_files = [await MyDriveSpaceService._resolve_file(file_space, file) for file in files]
        return [file for file in resolved_files if file is not None]

    @staticmethod
    def _normalize_file_path(path: str) -> str:
        """规范化文件绝对路径。"""
        normalized_path = str(PurePosixPath(path))
        if not normalized_path.startswith('/'):
            raise errors.ForbiddenError(msg='文件路径必须是绝对路径')
        return normalized_path

    @staticmethod
    def _is_path_within_root(path: str, root_path: str) -> bool:
        """判断文件路径是否位于空间根目录内。"""
        if root_path == '/':
            return True
        return path == root_path or path.startswith(f'{root_path}/')

    @staticmethod
    @asynccontextmanager
    async def _writable_space(
        db: AsyncSession,
        *,
        pk: int,
        owner_id: int,
    ) -> AsyncIterator[WritableFileSpace]:
        """创建并校验可写文件空间。"""
        space = await MyDriveSpaceService.get(db, pk=pk, owner_id=owner_id)
        file_space = await create_file_space(db, space)
        try:
            if not isinstance(file_space, WritableFileSpace):
                raise errors.ForbiddenError(msg='当前文件空间不支持写入')
            yield file_space
        finally:
            await file_space.aclose()

    @staticmethod
    def _validate_space_type(space_type: str) -> None:
        """
        验证文件空间类型。

        :param space_type: 文件空间类型
        :return:
        """
        valid_types = {item.value for item in SpaceType}
        if space_type not in valid_types:
            raise errors.ForbiddenError(msg=f'不支持的文件空间类型: {space_type}')

    @staticmethod
    async def _validate_account(
        db: AsyncSession,
        owner_id: int,
        account_id: int | None,
        space_type: str,
    ) -> MyDriveAccount | None:
        """
        验证文件空间关联账户。

        :param db: 数据库会话
        :param owner_id: 所属用户 ID
        :param account_id: 网盘账户 ID
        :param space_type: 文件空间类型
        :return:
        """
        account_required_types = {
            SpaceType.PERSONAL.value,
            SpaceType.SHARE_LINK.value,
            SpaceType.GROUP.value,
            SpaceType.FRIEND.value,
            SpaceType.OPENLIST.value,
        }
        if space_type in account_required_types and account_id is None:
            raise errors.ForbiddenError(msg='该文件空间必须关联网盘账户')
        if account_id is None:
            return None
        account = await mydrive_account_dao.get(db, account_id, owner_id)
        if account is None:
            raise errors.NotFoundError(msg='关联网盘账户不存在')
        return account

    @staticmethod
    def _validate_provider(account: MyDriveAccount | None, provider: str) -> None:
        """验证文件空间与账户的 Provider 一致。"""
        if account is not None and account.provider != provider:
            raise errors.ForbiddenError(msg='文件空间 Provider 必须与关联账户一致')

    @staticmethod
    def _normalize_space_values(
        obj: CreateMyDriveSpaceParam,
        account: MyDriveAccount | None,
    ) -> dict[str, Any]:
        """规范化文件空间挂载参数。"""
        values = obj.model_dump()
        space_type = SpaceType(obj.space_type)
        values['root_path'] = MyDriveSpaceService._normalize_file_path(obj.root_path)

        if space_type == SpaceType.PERSONAL:
            if account is None:
                raise errors.ForbiddenError(msg='个人文件空间必须关联网盘账户')
            values['source_key'] = MyDriveSpaceService._build_personal_source_key(
                account_id=account.id,
                root_id=values.get('root_id'),
                root_path=values['root_path'],
            )
            values['source_ref'] = {}
        elif space_type == SpaceType.SHARE_LINK:
            values['source_ref'] = MyDriveSpaceService._normalize_share_source_ref(obj.provider, obj.source_key, obj.source_ref)
            values['source_key'] = MyDriveSpaceService._get_share_source_key(obj.provider, values['source_ref'])
        elif space_type in {SpaceType.FRIEND, SpaceType.GROUP}:
            values['source_ref'] = MyDriveSpaceService._normalize_relationship_source_ref(
                obj.provider,
                obj.space_type,
                obj.source_key,
                obj.source_ref,
            )
            values['source_key'] = str(values['source_ref']['source_id'])
            if not values['root_id']:
                values['root_id'] = str(values['source_ref']['root_id'])

        values['capabilities'] = sorted(MyDriveSpaceService._get_space_capabilities(space_type, values['provider']))
        return values

    @staticmethod
    def _build_personal_source_key(*, account_id: int, root_id: str | None, root_path: str) -> str:
        """构建个人空间来源唯一标识。"""
        normalized_root_id = str(root_id or '').strip()
        normalized_root_path = MyDriveSpaceService._normalize_file_path(root_path)
        if not normalized_root_id and normalized_root_path == '/':
            return f'account:{account_id}'
        if normalized_root_id:
            return f'account:{account_id}:root_id:{normalized_root_id}'
        return f'account:{account_id}:root_path:{normalized_root_path}'

    @staticmethod
    def _normalize_share_source_ref(provider: str, source_key: str, source_ref: dict[str, Any]) -> dict[str, Any]:
        """规范化分享链接来源参数。"""
        normalized_ref = dict(source_ref)
        if provider == 'quark':
            try:
                share_value = str(normalized_ref.get('share_id') or source_key).strip()
                parsed_url = urlsplit(share_value)
                query_params = dict(parse_qsl(parsed_url.query, keep_blank_values=True))
                normalized_ref['share_id'] = QuarkRequest.normalize_share_id(share_value)
                if not str(normalized_ref.get('passcode') or '').strip():
                    normalized_ref['passcode'] = str(
                        query_params.get('pwd') or query_params.get('passcode') or ''
                    ).strip()
            except QuarkRequestError as exc:
                raise errors.ForbiddenError(msg=str(exc)) from exc
            return normalized_ref
        if provider == 'baidu':
            url = str(normalized_ref.get('url') or source_key).strip()
            if not url:
                raise errors.ForbiddenError(msg='百度分享空间缺少分享链接')
            url, passcode = MyDriveSpaceService._normalize_baidu_share_url(url)
            normalized_ref['url'] = url
            if passcode and not str(normalized_ref.get('passcode') or '').strip():
                normalized_ref['passcode'] = passcode
            return normalized_ref
        raise errors.ForbiddenError(msg=f'暂不支持 {provider} 分享链接空间')

    @staticmethod
    def _normalize_baidu_share_url(url: str) -> tuple[str, str]:
        """规范化百度分享链接并提取查询参数中的提取码。"""
        parsed_url = urlsplit(url)
        query_pairs = parse_qsl(parsed_url.query, keep_blank_values=True)
        passcode = ''
        retained_pairs: list[tuple[str, str]] = []

        for key, value in query_pairs:
            if key == 'pwd':
                passcode = value.strip()
                continue
            retained_pairs.append((key, value))

        normalized_url = urlunsplit((
            parsed_url.scheme,
            parsed_url.netloc,
            parsed_url.path,
            urlencode(retained_pairs),
            '',
        ))
        return normalized_url, passcode

    @staticmethod
    def _get_share_source_key(provider: str, source_ref: dict[str, Any]) -> str:
        """获取规范化分享来源唯一标识。"""
        if provider == 'quark':
            return str(source_ref['share_id'])
        return str(source_ref['url'])

    @staticmethod
    def _normalize_relationship_source_ref(
        provider: str,
        space_type: str,
        source_key: str,
        source_ref: dict[str, Any],
    ) -> dict[str, Any]:
        """规范化好友或群组分享来源参数。"""
        if provider != 'baidu':
            raise errors.ForbiddenError(msg=f'暂不支持 {provider} 好友或群组空间')
        normalized_ref = dict(source_ref)
        source_id = str(normalized_ref.get('source_id') or source_key).strip()
        from_uk = str(normalized_ref.get('from_uk') or '').strip()
        message_id = str(normalized_ref.get('message_id') or '').strip()
        root_id = str(normalized_ref.get('root_id') or '').strip()
        if not all((source_id, from_uk, message_id, root_id)):
            raise errors.ForbiddenError(msg=f'{space_type} 空间缺少分享定位信息')
        return {
            'source_id': source_id,
            'from_uk': from_uk,
            'message_id': message_id,
            'root_id': root_id,
        }

    @staticmethod
    def _get_space_capabilities(space_type: SpaceType, provider: str) -> frozenset[str]:
        """获取文件空间固有能力。"""
        if space_type in {SpaceType.SHARE_LINK, SpaceType.GROUP, SpaceType.FRIEND}:
            return frozenset({FileCapability.LIST.value, FileCapability.GET.value, FileCapability.TRANSFER_TO_TARGET.value})
        capabilities = {
            FileCapability.LIST.value,
            FileCapability.GET.value,
            FileCapability.MAKE_DIRECTORY.value,
            FileCapability.COPY.value,
            FileCapability.MOVE.value,
            FileCapability.RENAME.value,
            FileCapability.REMOVE.value,
        }
        if provider in {'baidu', 'quark'}:
            capabilities.add(FileCapability.CREATE_SHARE.value)
            capabilities.add(FileCapability.MANAGE_SHARES.value)
        return frozenset(capabilities)

    @staticmethod
    async def _validate_remote_space(db: AsyncSession, owner_id: int, values: dict[str, Any]) -> None:
        """验证远端文件空间可访问。"""
        candidate = MyDriveSpace(owner_id=owner_id, **values)
        file_space = await create_file_space(db, candidate)
        try:
            try:
                await file_space.list()
            except (BaiduRequestError, QuarkRequestError, ThunderRequestError) as exc:
                raise errors.ForbiddenError(msg=f'无法访问文件空间：{exc}') from exc
        finally:
            await file_space.aclose()

    @staticmethod
    def _validate_capabilities(space_type: str, capabilities: list[str]) -> None:
        """
        验证文件空间能力。

        :param space_type: 文件空间类型
        :param capabilities: 文件空间能力
        :return:
        """
        valid_capabilities = {item.value for item in FileCapability}
        invalid_capabilities = set(capabilities) - valid_capabilities
        if invalid_capabilities:
            raise errors.ForbiddenError(msg=f'存在不支持的文件空间能力: {", ".join(sorted(invalid_capabilities))}')

        external_source_types = {SpaceType.SHARE_LINK.value, SpaceType.GROUP.value, SpaceType.FRIEND.value}
        write_capabilities = {
            FileCapability.MAKE_DIRECTORY.value,
            FileCapability.COPY.value,
            FileCapability.MOVE.value,
            FileCapability.RENAME.value,
            FileCapability.REMOVE.value,
        }
        if space_type in external_source_types and write_capabilities.intersection(capabilities):
            raise errors.ForbiddenError(msg='外部文件空间不允许声明写入能力')


mydrive_space_service: MyDriveSpaceService = MyDriveSpaceService()
