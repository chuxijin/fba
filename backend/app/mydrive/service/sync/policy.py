#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from backend.app.mydrive.model.space import MyDriveSpace
from backend.app.mydrive.service.filesystem.models import SpaceType
from backend.common.exception import errors


def validate_sync_spaces(source: MyDriveSpace, target: MyDriveSpace) -> None:
    """验证同步来源与目标空间权限。"""
    if source.provider != target.provider:
        raise errors.ForbiddenError(msg='同步来源和目标必须属于同一 Provider')
    if target.space_type != SpaceType.PERSONAL.value:
        raise errors.ForbiddenError(msg='同步目标仅允许个人文件空间')
    if not source.is_enabled or not target.is_enabled:
        raise errors.ForbiddenError(msg='同步来源或目标文件空间已停用')
    if source.space_type not in {item.value for item in SpaceType}:
        raise errors.ForbiddenError(msg='不支持的同步来源文件空间类型')
    if source.space_type in {SpaceType.GROUP.value, SpaceType.FRIEND.value} and source.account_id != target.account_id:
        raise errors.ForbiddenError(msg='群组或好友空间只能同步到关联账户的个人空间')
