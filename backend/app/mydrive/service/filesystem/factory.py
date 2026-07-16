#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.mydrive.service.drives.baidu.personal_space import BaiduPersonalSpace
from backend.app.mydrive.service.drives.baidu.relationship_space import BaiduRelationshipSpace
from backend.app.mydrive.service.drives.baidu.share_space import BaiduShareSpace
from backend.app.mydrive.crud.crud_account import mydrive_account_dao
from backend.app.mydrive.model.space import MyDriveSpace
from backend.app.mydrive.service.filesystem.models import SpaceType
from backend.app.mydrive.service.filesystem.spaces import FileSpace
from backend.app.mydrive.service.drives.quark.personal_space import QuarkPersonalSpace
from backend.app.mydrive.service.drives.quark.share_space import QuarkShareSpace
from backend.app.mydrive.service.drives.thunder.personal_space import ThunderPersonalSpace
from backend.common.exception import errors


async def create_file_space(db: AsyncSession, space: MyDriveSpace) -> FileSpace:
    """
    根据挂载记录创建文件空间。

    :param db: 数据库会话
    :param space: 文件空间挂载记录
    :return:
    """
    if not space.is_enabled:
        raise errors.ForbiddenError(msg='文件空间已停用')
    if space.account_id is None:
        raise errors.ForbiddenError(msg='文件空间缺少网盘账户')

    account = await mydrive_account_dao.get(db, space.account_id, space.owner_id)
    if account is None:
        raise errors.NotFoundError(msg='文件空间关联网盘账户不存在')
    if space.provider == 'thunder':
        return _create_thunder_space(space, account.id, account.credential)
    cookie = str(account.credential.get('cookie') or '').strip()
    if not cookie:
        raise errors.ForbiddenError(msg='网盘账户缺少 Cookie 凭证')

    if space.provider == 'baidu':
        return _create_baidu_space(space, account.id, cookie)
    if space.provider == 'quark':
        return _create_quark_space(space, account.id, cookie)
    raise errors.ForbiddenError(msg=f'暂不支持 {space.provider} 文件空间')


def _create_quark_space(space: MyDriveSpace, account_id: int, cookie: str) -> FileSpace:
    """
    创建夸克文件空间。

    :param space: 文件空间挂载记录
    :param account_id: MyDrive 账户 ID
    :param cookie: 夸克网盘 Cookie
    :return:
    """
    if space.space_type == SpaceType.PERSONAL.value:
        return QuarkPersonalSpace(
            account_id=account_id,
            cookie=cookie,
            root_id=space.root_id or '0',
            root_path=space.root_path,
        )
    if space.space_type == SpaceType.SHARE_LINK.value:
        share_id = str(space.source_ref.get('share_id') or space.source_key).strip()
        if not share_id:
            raise errors.ForbiddenError(msg='夸克分享空间缺少分享标识')
        return QuarkShareSpace(
            account_id=account_id,
            cookie=cookie,
            share_id=share_id,
            passcode=str(space.source_ref.get('passcode') or ''),
            root_id=space.root_id or '0',
            root_path=space.root_path,
        )
    raise errors.ForbiddenError(msg=f'暂不支持夸克 {space.space_type} 文件空间')


def _create_baidu_space(space: MyDriveSpace, account_id: int, cookie: str) -> FileSpace:
    """
    创建百度文件空间。

    :param space: 文件空间挂载记录
    :param account_id: MyDrive 账户 ID
    :param cookie: 百度网盘 Cookie
    :return:
    """
    if space.space_type == SpaceType.PERSONAL.value:
        return BaiduPersonalSpace(
            account_id=account_id,
            cookie=cookie,
            root_id=space.root_id,
            root_path=space.root_path,
        )
    if space.space_type == SpaceType.SHARE_LINK.value:
        url = str(space.source_ref.get('url') or space.source_key).strip()
        if not url:
            raise errors.ForbiddenError(msg='百度分享空间缺少分享链接')
        return BaiduShareSpace(
            account_id=account_id,
            cookie=cookie,
            url=url,
            passcode=str(space.source_ref.get('passcode') or ''),
            root_id=space.root_id or '',
            root_path=space.root_path,
            sekey=str(space.source_ref.get('sekey') or ''),
            bdstoken=str(space.source_ref.get('bdstoken') or ''),
        )
    if space.space_type in {SpaceType.FRIEND.value, SpaceType.GROUP.value}:
        source_id = str(space.source_ref.get('source_id') or space.source_key).strip()
        from_uk = str(space.source_ref.get('from_uk') or '').strip()
        message_id = str(space.source_ref.get('message_id') or '').strip()
        root_id = str(space.root_id or space.source_ref.get('root_id') or '').strip()
        if not all((source_id, from_uk, message_id, root_id)):
            raise errors.ForbiddenError(msg='百度关系分享空间缺少定位信息')
        return BaiduRelationshipSpace(
            account_id=account_id,
            cookie=cookie,
            space_type=SpaceType(space.space_type),
            source_id=source_id,
            from_uk=from_uk,
            message_id=message_id,
            root_id=root_id,
            root_path=space.root_path,
        )
    raise errors.ForbiddenError(msg=f'暂不支持百度 {space.space_type} 文件空间')


def _create_thunder_space(space: MyDriveSpace, account_id: int, credential: dict) -> FileSpace:
    """
    创建迅雷文件空间。

    :param space: 文件空间挂载记录
    :param account_id: MyDrive 账户 ID
    :param credential: 迅雷授权凭证
    :return:
    """
    if space.space_type != SpaceType.PERSONAL.value:
        raise errors.ForbiddenError(msg=f'暂不支持迅雷 {space.space_type} 文件空间')
    return ThunderPersonalSpace(
        account_id=account_id,
        credential=credential,
        root_id=space.root_id or '',
        root_path=space.root_path,
    )
