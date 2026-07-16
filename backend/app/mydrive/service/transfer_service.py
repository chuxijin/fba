#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Iterable

from backend.app.mydrive.service.filesystem.capabilities import FileCapability
from backend.app.mydrive.service.filesystem.exceptions import CapabilityNotSupportedError, InvalidTransferError
from backend.app.mydrive.service.filesystem.models import FileObject, SpaceType
from backend.app.mydrive.service.filesystem.spaces import TransferSource, WritableFileSpace


async def transfer_files(
    source: TransferSource,
    files: Iterable[FileObject],
    target: WritableFileSpace,
    target_directory: FileObject | None = None,
) -> list[FileObject]:
    """
    将外部文件单向转存到个人文件空间。

    :param source: 只读外部源空间
    :param files: 待转存文件
    :param target: 可写个人目标空间
    :param target_directory: 目标目录，为空时使用空间根目录
    :return: 目标空间中的文件对象
    """
    if source.locator.space_type not in {SpaceType.SHARE_LINK, SpaceType.GROUP, SpaceType.FRIEND}:
        raise InvalidTransferError('仅支持链接、群组或好友空间作为外部同步源')

    if target.locator.space_type not in {SpaceType.PERSONAL, SpaceType.OPENLIST}:
        raise InvalidTransferError('仅支持个人空间或 OpenList 空间作为同步目标')

    if not source.supports(FileCapability.TRANSFER_TO_TARGET):
        raise CapabilityNotSupportedError(FileCapability.TRANSFER_TO_TARGET, source.locator.key)

    if not target.supports(FileCapability.MAKE_DIRECTORY):
        raise CapabilityNotSupportedError(FileCapability.MAKE_DIRECTORY, target.locator.key)

    if target_directory is None:
        return await source.transfer_to(files, target)
    return await source.transfer_to(files, target, target_directory)
